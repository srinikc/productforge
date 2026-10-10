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
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import contextlib
import os
import sqlite3
from datetime import datetime, timedelta

REPO = str(_PF_ROOT)
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
    # PFSSOT-P5 (BI-PF-0366): assignment lease
    "assignment_id": "TEXT", "lease_id": "TEXT", "lease_expires_at": "TEXT",
    "attempt": "INTEGER",
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
            with contextlib.suppress(Exception):
                c.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")
    c.commit()
    return c


def _now() -> str:
    return datetime.now().isoformat()


def _row(c, project: str) -> dict | None:
    r = c.execute("SELECT * FROM jobs WHERE project=?", (project,)).fetchone()
    if not r:
        return None
    cols = [d[0] for d in c.execute("SELECT * FROM jobs LIMIT 1").description]
    return dict(zip(cols, r, strict=False))


def enqueue(project: str, *, run_id: str = "", tier: str = "", priority: int = 100,
            item_id: str = "", item_ids: list[str] | None = None,
            source: str = "cli", actor: str = "", not_before: str = "",
            job_id: str = "") -> dict:
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


def claim(worker: str) -> dict | None:
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
            d = dict(zip(cols, r, strict=False))
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


def finish(project: str, rc: int) -> dict:
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
    # BI-PF-0234: terminal events MUST carry a run_id (row.run_id -> run lock ->
    # audit-trail/pipeline-state) so dashboards/status can correlate them.
    _rid = str((row or {}).get("run_id") or "")
    if not _rid:
        try:
            from core.lock_manager import LockManager
            _info = LockManager(PRODUCTS).get_lock_info(project)
            _rid = str(getattr(_info, "run_id", "") or "")
        except Exception:
            _rid = ""
    if not _rid:
        try:
            from core.audit_trail import current_run_id as _cur
            _rid = _cur(project) or ""
        except Exception:
            _rid = ""
    try:
        from core import events as _ev
        _ev.emit(os.path.join(PRODUCTS, project),
                 "run_completed" if rc == 0 else "run_failed",
                 run_id=_rid, project=project, rc=rc)
    except Exception:
        pass
    try:
        from core import run_status as _rs
        _rs.update(os.path.join(PRODUCTS, project),
                   "run_completed" if rc == 0 else "run_failed", run_id=_rid)
    except Exception:
        pass
    return {"job": row or {}, "auto_queued": resumed, "verification": verified}


# ── PFSSOT-P5 (BI-PF-0366): worker-scoped claim + lease over the canonical backlog ──
_LEASE_SECONDS_DEFAULT = 3600
RECOVERY_POLICIES = ("RESUME", "RETRY", "REASSIGN", "MARK_FAILED", "REQUIRE_REVIEW")


def _lease_seconds() -> int:
    try:
        from core import env_flags
        return int(env_flags.get("PF_LEASE_SECONDS", _LEASE_SECONDS_DEFAULT) or _LEASE_SECONDS_DEFAULT)
    except Exception:
        return _LEASE_SECONDS_DEFAULT


def _recovery_policy() -> str:
    try:
        from core import env_flags
        p = str(env_flags.get("PF_LEASE_RECOVERY", "REQUIRE_REVIEW") or "REQUIRE_REVIEW").upper()
        return p if p in RECOVERY_POLICIES else "REQUIRE_REVIEW"
    except Exception:
        return "REQUIRE_REVIEW"


def _active_assignments(scope: str, project: str | None) -> int:
    """Count open items currently leased to a worker (for the assignment concurrency cap)."""
    from core import backlog
    return sum(1 for it in backlog.list_open(scope, project, order=False)
               if str((it.get("execution") or {}).get("worker_id") or ""))


def claim_next(scope: str = "product_forge", project: str | None = None, worker: str = "",
               lease_seconds: int = 0, epic: str = "") -> dict:
    """Atomically claim the highest ELIGIBLE backlog item for ``worker`` and attach a per-ITEM lease.

    Single claimer path (IS-PF-0034): eligibility comes from ``core.scheduler`` (P4, read-only, stage=execute);
    the atomic transition uses this module's SQLite ``BEGIN IMMEDIATE`` as a cross-process mutex; the item's
    ``execution{}`` lease is written via ``core.backlog.set_execution`` (single writer).

    BI-PF-0419: keyed by ITEM and independent of the project pipeline-run queue (``jobs``) - so N items in one
    project can run in parallel. Returns the assignment package or ``{claimed: False, reason}``.

    BI-PF-0427: the *worker path* (worker API + coordinator) is product_forge-only; that boundary guard lives in
    the API layer (``api/routers/engineering.py``), not here - this remains the scope-parameterized mechanism.

    ``epic=<id>`` restricts the claim to that epic's children (BI-PF-1222).
    """
    from core import backlog, capacity, scheduler
    nxt = scheduler.next_eligible(scope, project, stage="execute", epic=epic or None)
    if not nxt.get("found"):
        return {"claimed": False, "reason": "no eligible item"}
    item_id = str(nxt["item"])
    secs = int(lease_seconds or _lease_seconds())
    now = datetime.now()
    expires = (now + timedelta(seconds=secs)).isoformat()
    assignment_id = f"ASG-{item_id}"
    lease_id = f"LSE-{item_id}-{int(now.timestamp())}"

    c = _db()
    try:
        c.execute("BEGIN IMMEDIATE")  # cross-process mutex (also serializes with pipeline-run claims)
        it = backlog.get_epic(scope, project, item_id) or {}
        ex = it.get("execution") or {}
        if str(ex.get("worker_id") or ""):  # atomic re-check: another worker won the race
            c.commit()
            return {"claimed": False, "reason": f"already claimed ({ex.get('worker_id')})"}
        cap = capacity.can_assign(_active_assignments(scope, project))
        if not cap.get("ok"):
            c.commit()
            return {"claimed": False, "reason": cap.get("reason") or "no assignment slot"}
        # write the lease while holding the mutex (backlog is the single writer of execution{})
        backlog.set_execution(scope, project, item_id, worker_id=worker, assignment_id=assignment_id,
                              lease_id=lease_id, assigned_at=now.isoformat(),
                              lease_expires_at=expires, started_at=now.isoformat(),
                              last_heartbeat_at=now.isoformat())
        c.commit()
    finally:
        c.close()
    out: dict = {"claimed": True, "item": item_id, "project": project or str(it.get("project") or scope),
                 "worker_id": worker, "assignment_id": assignment_id, "lease_id": lease_id,
                 "lease_expires_at": expires, "title": nxt.get("title")}
    for k in ("pidl_context", "execution_policy"):
        if nxt.get(k) is not None:
            out[k] = nxt[k]
    return out


def _stuck_minutes() -> int:
    """Minutes without a heartbeat before an assignment is treated as stuck (env ``PF_STUCK_MINUTES``)."""
    try:
        from core import env_flags
        v = env_flags.get("PF_STUCK_MINUTES", "15")
    except Exception:
        import os
        v = os.getenv("PF_STUCK_MINUTES", "15")
    try:
        return max(1, int(float(v)))
    except Exception:
        return 15


def _cleanup_worktree(scope: str, project: str | None, item_id: str) -> bool:
    """Best-effort removal of the assignment worktree (the branch is kept) after release/fail/recover.

    BI-PF-1238: self-heal the stale worktree left by an aborted/stuck worker so no manual cleanup is needed.
    """
    import os
    try:
        from core import vcs
        from core.paths import ROOT, PRODUCTS_DIR
        proj_dir = os.path.join(str(PRODUCTS_DIR), project) if (scope == "project" and project) else str(ROOT)
        vcs.VCSManager(proj_dir).remove_worktree(f"assign-{item_id}")
        return True
    except Exception:
        return False


def renew_lease(scope: str, project: str | None, item_id: str, lease_seconds: int = 0) -> dict:
    """Extend the lease on an active assignment (heartbeat). Per-item (BI-PF-0419): the lease lives in
    the item's ``execution{}`` only - the project pipeline-run queue (``jobs``) is untouched."""
    from core import backlog
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"renewed": False, "reason": "item not found"}
    ex = it.get("execution") or {}
    if not str(ex.get("lease_id") or ""):
        return {"renewed": False, "reason": "no lease"}
    secs = int(lease_seconds or _lease_seconds())
    now = datetime.now()
    expires = (now + timedelta(seconds=secs)).isoformat()
    backlog.set_execution(scope, project, item_id, lease_expires_at=expires,
                          last_heartbeat_at=now.isoformat())
    return {"renewed": True, "item": item_id, "lease_expires_at": expires}


def release(scope: str, project: str | None, item_id: str, reason: str = "released",
            terminal: bool = False) -> dict:
    """Release an assignment: clear the per-item lease; return the item to READY (or terminal)."""
    from core import backlog
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"released": False, "reason": "item not found"}
    backlog.set_execution(scope, project, item_id, worker_id="", assignment_id="", lease_id="",
                          lease_expires_at="", completed_at=datetime.now().isoformat() if terminal else "")
    _cleanup_worktree(scope, project, item_id)
    return {"released": True, "item": item_id, "reason": reason, "terminal": terminal}


def _elapsed_seconds(it: dict) -> int:
    """Wall-clock seconds from execution.started_at to now (0 if unknown/invalid). BI-PF-123x."""
    ex = it.get("execution") or {}
    s = str(ex.get("started_at") or "")
    if not s:
        return 0
    try:
        return max(0, int((datetime.now() - datetime.fromisoformat(s)).total_seconds()))
    except Exception:
        return 0


def complete(scope: str, project: str | None, item_id: str, *, status: str = "verifying",
             note: str = "") -> dict:
    """Worker reports an assignment DONE: set the execution status and clear the lease (BI-PF-0419).

    Records the run duration on ``execution.duration_seconds`` (BI-PF-123x) for time tracking.
    Delivery (gates/PR/merge) is orchestrated separately (BI-PF-0421); this only closes the execution lease.
    """
    from core import backlog
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"ok": False, "reason": "item not found"}
    dur = _elapsed_seconds(it)
    attempt = int((it.get("execution") or {}).get("attempt") or 0) + 1
    backlog.set_status(scope, project, item_id, status, note=note or "assignment complete")
    backlog.set_execution(scope, project, item_id, worker_id="", assignment_id="", lease_id="",
                          lease_expires_at="", completed_at=datetime.now().isoformat(),
                          duration_seconds=dur, attempt=attempt)
    return {"ok": True, "item": item_id, "status": status, "duration_seconds": dur}


def fail(scope: str, project: str | None, item_id: str, reason: str = "") -> dict:
    """Worker reports an assignment FAILED: mark blocked and clear the lease (BI-PF-0419)."""
    from core import backlog
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"ok": False, "reason": "item not found"}
    dur = _elapsed_seconds(it)
    attempt = int((it.get("execution") or {}).get("attempt") or 0) + 1
    backlog.set_status(scope, project, item_id, "blocked", note=reason or "assignment failed")
    backlog.set_execution(scope, project, item_id, worker_id="", assignment_id="", lease_id="",
                          lease_expires_at="", completed_at=datetime.now().isoformat(),
                          duration_seconds=dur, attempt=attempt)
    _cleanup_worktree(scope, project, item_id)
    return {"ok": True, "item": item_id, "status": "blocked", "duration_seconds": dur}


def recover_expired(scope: str = "product_forge", project: str | None = None,
                    policy: str = "") -> dict:
    """Find leases past expiry and apply the recovery policy (default REQUIRE_REVIEW). Never blind re-run."""
    from core import backlog
    pol = str(policy or _recovery_policy()).upper()
    if pol not in RECOVERY_POLICIES:
        pol = "REQUIRE_REVIEW"
    now = datetime.now().isoformat()
    recovered = []
    for it in backlog.list_open(scope, project, order=False):
        ex = it.get("execution") or {}
        exp = str(ex.get("lease_expires_at") or "")
        if not exp or str(ex.get("completed_at") or ""):
            continue
        item_id = str(it.get("id"))
        hb = str(ex.get("last_heartbeat_at") or ex.get("started_at") or ex.get("assigned_at") or "")
        expired = exp <= now
        stuck = False
        if not expired and hb:
            try:
                stuck = (datetime.now() - datetime.fromisoformat(hb)).total_seconds() > _stuck_minutes() * 60
            except Exception:
                stuck = False
        if not expired and not stuck:
            continue
        # apply policy
        if pol == "MARK_FAILED":
            backlog.set_status(scope, project, item_id, "failed", note="lease expired")
        elif pol in ("RETRY", "REASSIGN", "RESUME"):
            backlog.set_readiness(scope, project, item_id, False, reasons=[])  # stays recoverable
        else:  # REQUIRE_REVIEW (default)
            why = "lease expired" if expired else "stuck (no heartbeat)"
            backlog.set_status(scope, project, item_id, "blocked", note=f"{why}; review required")
        backlog.set_execution(scope, project, item_id, worker_id="", assignment_id="", lease_id="",
                              lease_expires_at="", last_heartbeat_at="")
        _cleanup_worktree(scope, project, item_id)
        recovered.append({"item": item_id, "policy": pol, "expired_at": exp,
                          "reason": "expired" if expired else "stuck"})
    return {"policy": pol, "recovered": recovered, "count": len(recovered)}


def pause_request(project: str, by: str = "", reason: str = "") -> dict:
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


def mark_paused(project: str) -> dict:
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


def resume(project: str) -> dict:
    c = _db()
    try:
        c.execute("UPDATE jobs SET state='queued', status='queued', resume_after=NULL WHERE project=?",
                  (project,))
        c.commit()
        row = _row(c, project)
    finally:
        c.close()
    return row or {}


def cancel(project: str) -> dict:
    c = _db()
    try:
        c.execute("UPDATE jobs SET state='cancelled', status='cancelled', finished_at=? "
                  "WHERE project=?", (_now(), project))
        c.commit()
        row = _row(c, project)
    finally:
        c.close()
    return row or {}


def set_parallel(n: int, actor: str = "") -> dict:
    """Raise/lower max_parallel_projects with a capacity/cost warning (soft) and hard ceiling."""
    from core import capacity
    cfg = capacity.load() if hasattr(capacity, "load") else {}
    cur = int(cfg.get("max_parallel_projects") or 0)
    int(cfg.get("global_budget", {}).get("hard_tokens") or 0) if isinstance(
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
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["max_parallel_projects"] = int(n)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"max_parallel_projects": n, "previous": cur, "warning": warn, "actor": actor}


def run_now_on_priority(project: str, *, by: str = "", item_id: str = "",
                        victim: str = "") -> dict:
    """Free a slot for a priority job by pausing the least-urgent running job."""
    c = _db()
    try:
        rows = c.execute("SELECT * FROM jobs WHERE state='running'").fetchall()
        cols = [d[0] for d in c.execute("SELECT * FROM jobs LIMIT 1").description]
        running = [dict(zip(cols, r, strict=False)) for r in rows]
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


def status() -> dict:
    """Full queue view for CLI/API/UI: queued/scheduled/running/paused + why each waits."""
    c = _db()
    try:
        rows = c.execute("SELECT * FROM jobs ORDER BY priority, enqueued_at").fetchall()
        cols = [d[0] for d in c.execute("SELECT * FROM jobs LIMIT 1").description]
        jobs = [dict(zip(cols, r, strict=False)) for r in rows]
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
