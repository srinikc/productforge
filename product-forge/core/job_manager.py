"""Job Manager — the orchestration layer over the existing portfolio queue.

This ENHANCES the existing queue (same SQLite file `product-forge/portfolio/portfolio.db`,
same worker substrate, same `scripts/run_pipeline.py` launch); it does not replace it.
One writer for job state. Every launch (CLI, dashboard, intake Execute/Schedule) goes
through :func:`enqueue`; the worker only *claims* through :func:`claim`.

States:
  queued        waiting for a slot (priority ordered)
  scheduled     waiting until `not_before` (a due time)
  pause_pending operator asked to pause; the run finishes its current agent, then parks
  paused        parked at a safe checkpoint (resumable)
  running       executing (child process alive)
  done / failed / cancelled   terminal

Ordering when a slot frees (lowest `rank`, then priority, then enqueued_at):
  1. paused jobs whose `resume_after` blocker is finished (or none)  [resume first]
  2. queued jobs by priority
  3. (FIFO tie-break)

Key ids aligned end-to-end on every job:
  job_id(=project row) · run_id · backlog item(s) · intake IN-id · source · actor
"""
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(REPO, "products")

# Reuse the exact DB the existing queue uses.
try:
    from core import portfolio as _pf
    DB = _pf.DB
except Exception:
    DB = os.path.join(REPO, "data", "portfolio", "portfolio.db")

STATES = ("queued", "scheduled", "pause_pending", "paused", "running",
          "done", "failed", "cancelled")

_NEW_COLS = {
    "state": "TEXT", "not_before": "TEXT", "resume_after": "TEXT", "paused_by": "TEXT",
    "run_id": "TEXT", "source": "TEXT", "actor": "TEXT", "job_id": "TEXT",
    "paused_at": "TEXT", "resumed_at": "TEXT", "priority": "INTEGER",
    "item_ids": "TEXT", "enqueued_at": "TEXT", "started_at": "TEXT",
    "finished_at": "TEXT", "worker": "TEXT", "rc": "INTEGER", "tier": "TEXT",
}


def _db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS jobs("
              "project TEXT PRIMARY KEY, tier TEXT, priority INTEGER, status TEXT, "
              "worker TEXT, enqueued_at TEXT, started_at TEXT, finished_at TEXT, rc INTEGER)")
    # migration-safe: add any missing columns
    have = {r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()}
    for col, typ in _NEW_COLS.items():
        if col not in have:
            try:
                c.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")
            except Exception:
                pass
    c.commit()
    return c


def _now() -> str:
    return datetime.now().isoformat()


def _row(c, project: str) -> Optional[Dict]:
    r = c.execute("SELECT * FROM jobs WHERE project=?", (project,)).fetchone()
    if not r:
        return None
    cols = [d[0] for d in c.execute("SELECT * FROM jobs LIMIT 1").description]
    return dict(zip(cols, r))


def enqueue(project: str, *, run_id: str = "", tier: str = "", priority: int = 100,
            item_id: str = "", item_ids: Optional[List[str]] = None,
            source: str = "cli", actor: str = "", not_before: str = "",
            job_id: str = "") -> Dict:
    """Put a run on the queue. Not-before makes it `scheduled`; else `queued`."""
    ids = ",".join([i for i in ([item_id] if item_id else []) + list(item_ids or []) if i])
    state = "scheduled" if not_before else "queued"
    c = _db()
    try:
        c.execute(
            "INSERT INTO jobs(project,tier,priority,status,enqueued_at,item_ids,state,"
            "not_before,run_id,source,actor,job_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(project) DO UPDATE SET tier=excluded.tier, priority=excluded.priority,"
            "item_ids=excluded.item_ids, state=CASE WHEN jobs.state='running' THEN 'running' "
            "ELSE excluded.state END, not_before=excluded.not_before, run_id=excluded.run_id,"
            "source=excluded.source, actor=excluded.actor, job_id=excluded.job_id",
            (project, tier, priority, state, _now(), ids, state, not_before or None,
             run_id, source, actor, job_id or f"JOB-{project}"))
        c.commit()
        row = _row(c, project)
    finally:
        c.close()
    return row or {}


def _resume_ready(c, resume_after: str) -> bool:
    """A paused job resumes when its blocker has finished (or is gone)."""
    if not resume_after:
        return True
    b = c.execute("SELECT state FROM jobs WHERE project=?", (resume_after,)).fetchone()
    if not b:
        return True
    return str(b[0]) in ("done", "failed", "cancelled")


def claim(worker: str) -> Optional[Dict]:
    """Claim the next runnable job: paused-resume first, then queued by priority/FIFO."""
    c = _db()
    try:
        c.execute("BEGIN IMMEDIATE")
        rows = c.execute("SELECT * FROM jobs WHERE state IN ('queued','paused','scheduled')"
                         ).fetchall()
        cols = [d[0] for d in c.execute("SELECT * FROM jobs LIMIT 1").description]
        now = _now()
        cands = []
        for r in rows:
            d = dict(zip(cols, r))
            st = d.get("state")
            if st == "scheduled" and (d.get("not_before") or "") > now:
                continue
            if st == "paused" and not _resume_ready(c, d.get("resume_after") or ""):
                continue
            # rank: paused first (0), then everything else (1)
            rank = 0 if st == "paused" else 1
            cands.append((rank, int(d.get("priority") or 100), d.get("enqueued_at") or "", d))
        if not cands:
            c.commit()
            return None
        cands.sort(key=lambda x: (x[0], x[1], x[2]))
        d = cands[0][3]
        c.execute("UPDATE jobs SET state='running', status='running', worker=?, started_at=?, "
                  "resumed_at=CASE WHEN state='paused' THEN ? ELSE resumed_at END WHERE project=?",
                  (worker, now, now, d["project"]))
        c.commit()
        return {"project": d["project"], "tier": d.get("tier") or "", "run_id": d.get("run_id") or "",
                "state": "running", "resumed": d.get("state") == "paused"}
    finally:
        c.close()


def finish(project: str, rc: int) -> Dict:
    c = _db()
    try:
        st = "done" if rc == 0 else "failed"
        c.execute("UPDATE jobs SET state=?, status=?, rc=?, finished_at=? WHERE project=?",
                  (st, st, rc, _now(), project))
        c.commit()
        # auto-resume any paused job blocked on this one
        resumed = []
        for r in c.execute("SELECT project FROM jobs WHERE state='paused' AND resume_after=?",
                           (project,)).fetchall():
            c.execute("UPDATE jobs SET state='queued', status='queued' WHERE project=?", (r[0],))
            resumed.append(r[0])
        c.commit()
        row = _row(c, project)
    finally:
        c.close()
    # Close-on-verify: if the run succeeded and is tied to backlog item(s), verify and
    # auto-close the backlog + intake items (attaching final + QA report links).
    verified = None
    try:
        item_ids = [i.strip() for i in str((row or {}).get("item_ids") or "").split(",") if i.strip()]
        if rc == 0 and item_ids:
            from core import close_loop
            proj_dir = os.path.join(PRODUCTS, project)
            verified = close_loop.verify_and_close(proj_dir,
                                                   run_id=str((row or {}).get("run_id") or ""),
                                                   item_ids=item_ids)
    except Exception:
        verified = None
    try:
        from core import events as _ev
        _ev.emit(os.path.join(PRODUCTS, project),
                 "run_completed" if rc == 0 else "run_failed",
                 run_id=str((row or {}).get("run_id") or ""), project=project, rc=rc)
    except Exception:
        pass
    return {"job": row or {}, "auto_queued": resumed, "verification": verified}


def pause_request(project: str, by: str = "", reason: str = "") -> Dict:
    """Ask a run to park at its next safe checkpoint (finishes current agent first)."""
    c = _db()
    try:
        c.execute("UPDATE jobs SET state='pause_pending', paused_by=? WHERE project=? "
                  "AND state='running'", (by or reason, project))
        c.commit()
        row = _row(c, project)
    finally:
        c.close()
    return row or {}


def mark_paused(project: str) -> Dict:
    """Called by the runner once it has checkpointed and parked."""
    c = _db()
    try:
        c.execute("UPDATE jobs SET state='paused', status='paused', paused_at=? WHERE project=?",
                  (_now(), project))
        c.commit()
        row = _row(c, project)
    finally:
        c.close()
    return row or {}


def resume(project: str) -> Dict:
    c = _db()
    try:
        c.execute("UPDATE jobs SET state='queued', status='queued', resume_after=NULL WHERE project=?",
                  (project,))
        c.commit()
        row = _row(c, project)
    finally:
        c.close()
    return row or {}


def cancel(project: str) -> Dict:
    c = _db()
    try:
        c.execute("UPDATE jobs SET state='cancelled', status='cancelled', finished_at=? "
                  "WHERE project=?", (_now(), project))
        c.commit()
        row = _row(c, project)
    finally:
        c.close()
    return row or {}


def set_parallel(n: int, actor: str = "") -> Dict:
    """Raise/lower max_parallel_projects with a capacity/cost warning (soft) and hard ceiling."""
    from core import capacity
    cfg = capacity.load() if hasattr(capacity, "load") else {}
    cur = int(cfg.get("max_parallel_projects") or 0)
    hard = int(cfg.get("global_budget", {}).get("hard_tokens") or 0) if isinstance(
        cfg.get("global_budget"), dict) else 0
    warn = ""
    if n > cur and n >= 6:
        warn = (f"increasing to {n} parallel projects raises LLM cost/provider load; "
                f"verify provider rate limits and global budget.")
    # persist
    import json
    path = os.path.join(REPO, "config", "capacity.json")
    data = {}
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        data = {}
    data["max_parallel_projects"] = int(n)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"max_parallel_projects": n, "previous": cur, "warning": warn, "actor": actor}


def run_now_on_priority(project: str, *, by: str = "", item_id: str = "",
                        victim: str = "") -> Dict:
    """Free a slot for a priority job by pausing the least-urgent running job."""
    c = _db()
    try:
        rows = c.execute("SELECT * FROM jobs WHERE state='running'").fetchall()
        cols = [d[0] for d in c.execute("SELECT * FROM jobs LIMIT 1").description]
        running = [dict(zip(cols, r)) for r in rows]
    finally:
        c.close()
    if not running:
        return {"ok": True, "note": "no running job; will run when a slot frees",
                "enqueued": enqueue(project, item_id=item_id, priority=10, source="priority",
                                    actor=by)}
    if victim:
        v = next((r for r in running if r["project"] == victim), None)
    else:
        # least urgent = highest priority number
        v = sorted(running, key=lambda r: -int(r.get("priority") or 100))[0]
    if not v:
        return {"ok": False, "reason": "no victim running job found"}
    pause_request(v["project"], by=by, reason=f"priority:{project}")
    c = _db()
    try:
        c.execute("UPDATE jobs SET resume_after=? WHERE project=?", (project, v["project"]))
        c.commit()
    finally:
        c.close()
    enq = enqueue(project, item_id=item_id, priority=10, source="priority", actor=by)
    return {"ok": True, "paused": v["project"], "resume_after": project, "enqueued": enq,
            "note": f"{v['project']} will park at its next checkpoint; {project} runs next, "
                    f"then {v['project']} auto-resumes."}


def status() -> Dict:
    """Full queue view for CLI/API/UI: queued/scheduled/running/paused + why each waits."""
    c = _db()
    try:
        rows = c.execute("SELECT * FROM jobs ORDER BY priority, enqueued_at").fetchall()
        cols = [d[0] for d in c.execute("SELECT * FROM jobs LIMIT 1").description]
        jobs = [dict(zip(cols, r)) for r in rows]
    finally:
        c.close()
    from core.capacity import status as _cap
    cap = _cap()
    out = {"limits": cap.get("limits"), "running_count": cap.get("running_count"),
           "jobs": [], "by_state": {}}
    for j in jobs:
        st = j.get("state") or j.get("status") or "queued"
        out["by_state"][st] = out["by_state"].get(st, 0) + 1
        out["jobs"].append({
            "project": j.get("project"), "state": st, "priority": j.get("priority"),
            "source": j.get("source"), "actor": j.get("actor"), "run_id": j.get("run_id"),
            "job_id": j.get("job_id"), "item_ids": j.get("item_ids"),
            "not_before": j.get("not_before"), "resume_after": j.get("resume_after"),
            "worker": j.get("worker"), "rc": j.get("rc"),
        })
    return out
