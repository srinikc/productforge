"""
Portfolio manager (GLOBAL tier) — register many projects, supervise their runs.

Model: ONE supervisor process coordinates N per-project controllers (child
`run_pipeline.py` processes). Projects stay isolated (own folder/lock/state).
Pre-dashboard "single pane": registry + state + status table.

Files:
  products/portfolio-registry.json  project -> {idea, tier, priority, status, added_at}
  products/portfolio-state.json     project -> {status, pid, run_id, started_at, rc}
  products/.locks/portfolio.lock    supervisor pid lock
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(REPO, "products")
def _forge_path(new_name, legacy_name):
    """Prefer product-forge/portfolio/<new>; fall back to legacy products/<file>."""
    forge = os.path.join(REPO, "data", "portfolio")
    os.makedirs(forge, exist_ok=True)
    new = os.path.join(forge, new_name)
    legacy = os.path.join(PRODUCTS, legacy_name)
    if not os.path.exists(new) and os.path.exists(legacy):
        return legacy
    return new


REG = _forge_path("portfolio-registry.json", "portfolio-registry.json")
STATE = _forge_path("portfolio-state.json", "portfolio-state.json")
LOCK = os.path.join(PRODUCTS, ".locks", "portfolio.lock")
DB = _forge_path("portfolio.db", "portfolio.db")


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS jobs("
              "project TEXT PRIMARY KEY, tier TEXT, priority INTEGER, status TEXT, "
              "worker TEXT, enqueued_at TEXT, started_at TEXT, finished_at TEXT, rc INTEGER)")
    c.commit()
    return c


def enqueue(project: str, tier: str = "", priority: int = 100, item_id: str = "",
            item_ids: Optional[List[str]] = None):
    """Queue a project run (optionally tied to backlog item(s)). Back-compat: tier kept."""
    ids = ",".join([i for i in ([item_id] if item_id else []) + list(item_ids or []) if i])
    c = _db()
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN item_ids TEXT", )
        c.commit()
    except Exception:
        pass
    c.execute("INSERT INTO jobs(project,tier,priority,status,enqueued_at,item_ids) "
              "VALUES(?,?,?,?,?,?) "
              "ON CONFLICT(project) DO UPDATE SET tier=excluded.tier, "
              "priority=excluded.priority, item_ids=excluded.item_ids, "
              "status=CASE WHEN jobs.status='running' THEN 'running' ELSE 'queued' END",
              (project, tier, priority, "queued", datetime.now().isoformat(), ids))
    c.commit()
    c.close()
    return {"project": project, "priority": priority, "item_ids": ids, "status": "queued"}


def claim(worker: str) -> Optional[Dict]:
    c = _db()
    c.execute("BEGIN IMMEDIATE")
    row = c.execute("SELECT project,tier FROM jobs WHERE status='queued' "
                    "ORDER BY priority ASC, enqueued_at ASC LIMIT 1").fetchone()
    if not row:
        c.commit()
        c.close()
        return None
    project, tier = row
    c.execute("UPDATE jobs SET status='running', worker=?, started_at=? WHERE project=?",
              (worker, datetime.now().isoformat(), project))
    c.commit()
    c.close()
    return {"project": project, "tier": tier or ""}


def finish(project: str, rc: int):
    c = _db()
    c.execute("UPDATE jobs SET status=?, rc=?, finished_at=? WHERE project=?",
              ("completed" if rc == 0 else "failed", rc, datetime.now().isoformat(), project))
    c.commit()
    c.close()


def requeue_stale():
    c = _db()
    c.execute("UPDATE jobs SET status='queued' WHERE status='running'")
    c.commit()
    c.close()


def queue_rows() -> List[tuple]:
    c = _db()
    rows = c.execute("SELECT project,status,priority,worker,rc FROM jobs "
                     "ORDER BY priority, enqueued_at").fetchall()
    c.close()
    return rows


def worker_loop(once: bool = False, dry: bool = False, poll: int = 5,
                max_jobs: int = 0) -> int:
    """Worker (substrate B): claim a job from the queue and run it, repeatedly.

    Claiming/ordering/finishing go through core.job_manager (paused-resume first, then
    priority, then FIFO; future-scheduled and paused-blocked jobs are skipped).
    """
    wid = f"w{os.getpid()}"
    done = 0
    while True:
        job = None
        try:
            from core import job_manager as jm
            job = jm.claim(wid)
        except Exception:
            job = claim(wid)   # fallback to the legacy claimer
        if not job:
            if once or (max_jobs and done >= max_jobs):
                break
            time.sleep(poll)
            continue
        p = job["project"]
        try:
            from core.capacity import can_start
            cap = can_start(p)
            if not cap["ok"]:
                print(f"  [worker {wid}] no slot ({cap['reason']}); requeue {p}")
                requeue(p)
                if once:
                    break
                time.sleep(poll)
                continue
        except Exception:
            pass
        if dry:
            print(f"  [worker {wid}] dry-claim {p} (tier={job.get('tier')})")
            _jm_finish(p, 0)
            done += 1
        else:
            os.makedirs(os.path.join(PRODUCTS, p), exist_ok=True)
            cmd = [sys.executable, "-u", "scripts/run_pipeline.py", "--project", p]
            if job.get("tier"):
                cmd += ["--tier", job["tier"]]
            if job.get("run_id"):
                cmd += ["--run-id", job["run_id"]]
            logf = open(os.path.join(PRODUCTS, p, "pipeline-run.log"), "a", encoding="utf-8")
            rc = subprocess.call(cmd, cwd=REPO, stdout=logf, stderr=subprocess.STDOUT)
            _jm_finish(p, rc)
            print(f"  [worker {wid}] {p} rc={rc}")
            done += 1
        if once or (max_jobs and done >= max_jobs):
            break
    return 0


def _jm_finish(project: str, rc: int):
    """Finish via JobManager when available (auto-queues blocked paused jobs)."""
    try:
        from core import job_manager as jm
        res = jm.finish(project, rc)
        if res.get("auto_queued"):
            print(f"  [job] auto-queued paused job(s): {res['auto_queued']}")
    except Exception:
        finish(project, rc)



def _rj(p, d):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def _wj(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def register(project: str, idea: str = "", tier: str = "", priority: int = 100) -> Dict:
    """Add/refresh a project in the portfolio registry and seed its project.json."""
    reg = _rj(REG, {})
    pdir = os.path.join(PRODUCTS, project)
    os.makedirs(pdir, exist_ok=True)
    pj = os.path.join(pdir, "project.json")
    defaults = {}
    if idea:
        defaults["idea"] = idea
    if tier:
        defaults["model_tier"] = tier
    try:
        from core.project_store import ensure as _ps_ensure
        cfg = _ps_ensure(project, "products", **defaults)
    except Exception:
        cfg = _rj(pj, {}) or {}
        cfg.setdefault("name", project)
        cfg.update(defaults)
        _wj(pj, cfg)
    reg[project] = {**(reg.get(project) or {}), "idea": idea or cfg.get("idea", ""),
                    "tier": tier or cfg.get("model_tier", ""), "priority": priority,
                    "status": (reg.get(project) or {}).get("status", "queued"),
                    "added_at": datetime.now().isoformat()}
    _wj(REG, reg)
    try:
        enqueue(project, reg[project].get("tier", ""), priority)
    except Exception:
        pass
    return reg[project]


def projects() -> Dict[str, Dict]:
    return _rj(REG, {})


def state() -> Dict[str, Dict]:
    return _rj(STATE, {})


def set_state(project: str, **kw):
    st = state()
    st[project] = {**(st.get(project) or {}), **kw, "updated_at": datetime.now().isoformat()}
    _wj(STATE, st)
    return st[project]


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True, timeout=10).stdout
        return str(pid) in out
    except Exception:
        return False


def _sup_lock_path() -> str:
    return os.path.join(os.path.dirname(LOCK), f"portfolio-{os.getpid()}.lock")


def supervisor_running() -> bool:
    try:
        from core.capacity import live_supervisors
        return bool(live_supervisors())
    except Exception:
        return _pid_alive(_rj(LOCK, {}).get("pid"))


def _acquire_supervisor_lock() -> bool:
    try:
        from core.capacity import can_start_supervisor
        c = can_start_supervisor()
        if not c["ok"]:
            print(f"[capacity] cannot start supervisor: {c['reason']}")
            return False
    except Exception:
        pass
    _wj(_sup_lock_path(), {"pid": os.getpid(),
                           "started_at": datetime.now().isoformat()})
    return True


def _release_supervisor_lock():
    try:
        os.remove(_sup_lock_path())
    except Exception:
        pass


def requeue(project: str):
    c = _db()
    c.execute("UPDATE jobs SET status='queued', worker='' WHERE project=?", (project,))
    c.commit()
    c.close()


def control(project: str, action: str) -> Dict:
    pdir = os.path.join(PRODUCTS, project)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "control.json"), "w", encoding="utf-8") as f:
        json.dump({"action": "stop" if action == "exit" else action,
                   "updated_at": datetime.now().isoformat()}, f)
    return {"project": project, "action": action}


def status_rows() -> List[Dict[str, Any]]:
    reg, st = projects(), state()
    rows = []
    for p in sorted(set(list(reg) + list(st))):
        ps = _rj(os.path.join(PRODUCTS, p, "pipeline-state.json"), {}) or {}
        gng = _rj(os.path.join(REPO, "test-framework", "results", p, "go-no-go.json"), {}) or {}
        rows.append({
            "project": p,
            "status": (st.get(p) or {}).get("status") or (reg.get(p) or {}).get("status") or "?",
            "pid": (st.get(p) or {}).get("pid", ""),
            "stage": ps.get("current_stage", ""),
            "rag": (gng.get("decision") or "").lower() or
                   ({k: v for k, v in (("red", "no-go"), ("yellow", "go-with-risk"), ("green", "go"))}.get("", "")),
            "tier": (reg.get(p) or {}).get("tier", ""),
            "priority": (reg.get(p) or {}).get("priority", ""),
        })
    return rows


def run_supervisor(max_concurrent: int = 1, watch: bool = True, dry: bool = False,
                   poll: int = 5) -> int:
    """One supervisor: launch/wave project runs (slots), watch registry for new adds."""
    if not _acquire_supervisor_lock():
        print("Another supervisor is already running (products/.locks/portfolio.lock).")
        return 2
    procs: Dict[str, subprocess.Popen] = {}
    terminal = {"completed", "failed", "skipped"}
    idle = 0
    print(f"Portfolio supervisor pid={os.getpid()} | max_concurrent={max_concurrent} "
          f"| watch={watch} | dry={dry}")
    try:
        while True:
            reg, st = projects(), state()
            # reap finished children
            for p in list(procs):
                rc = procs[p].poll()
                if rc is not None:
                    set_state(p, status=("completed" if rc == 0 else "failed"), rc=rc, pid="")
                    print(f"  [done] {p} rc={rc}")
                    procs.pop(p)
            # launch queued projects up to slots
            for p in sorted(reg, key=lambda x: reg[x].get("priority", 100)):
                if len(procs) >= max_concurrent:
                    break
                cur = (st.get(p) or {}).get("status")
                if cur in ("running", "completed"):
                    continue
                try:
                    from core.capacity import can_start
                    cap = can_start(p)
                    if not cap["ok"]:
                        continue  # no free slot (globally) -> wait
                except Exception:
                    pass
                cmd = [sys.executable, "-u", "scripts/run_pipeline.py", "--project", p]
                if reg[p].get("tier"):
                    cmd += ["--tier", reg[p]["tier"]]
                if dry:
                    set_state(p, status="completed", note="dry-run")
                    print(f"  [dry] would run: {' '.join(cmd)}")
                    continue
                os.makedirs(os.path.join(PRODUCTS, p), exist_ok=True)
                logf = open(os.path.join(PRODUCTS, p, "pipeline-run.log"), "a", encoding="utf-8")
                pr = subprocess.Popen(cmd, cwd=REPO, stdout=logf, stderr=subprocess.STDOUT)
                procs[p] = pr
                set_state(p, status="running", pid=pr.pid,
                          started_at=datetime.now().isoformat())
                print(f"  [start] {p} pid={pr.pid}")
            # live table
            print("\n".join([f"  {r['project']:<18} {r['status']:<14} pid={r['pid']!s:<7} "
                             f"stage={r['stage']:<4} tier={r['tier']}"
                             for r in status_rows()]))
            if not watch:
                stt = state()
                if not procs and all((stt.get(p) or {}).get("status") in terminal for p in reg):
                    break
                idle += 1
                if idle > 1000:  # safety (avoid infinite no-watch loop)
                    print("  [supervisor] no-watch idle limit reached; exiting")
                    break
            time.sleep(poll)
    except KeyboardInterrupt:
        print("\n[supervisor] interrupted")
    finally:
        _release_supervisor_lock()
    return 0
