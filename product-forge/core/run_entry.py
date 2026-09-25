"""Guarded run entry — the ONE way a project run is started.

Every entry point (CLI ``scripts/run_pipeline.py``, the dashboard ``/api/run``, or
any code path) must call :func:`begin_run` before executing, and :func:`end_run`
when finished. This guarantees, in one place:

  * exactly ONE instance per project (via ``core.run_guard``),
  * the project lock carries the run id,
  * approvals/audit/artifacts get a stamped run id,
  * already-approved stages are reconciled (resume skips them; user data never cleared).

`execute_pipeline()` refuses to run unless a lock is held, so no path can bypass this.
"""
import os
from typing import Dict, Optional

from core.lock_manager import LockManager


def begin_run(project: str, products_dir: str = "products",
              run_id: str = "", wait_seconds: int = 20,
              stop_existing: bool = True) -> Dict:
    """Stop any other instance, acquire the lock (with run_id), reconcile prior work.

    Returns ``{ok, run_id, lock_holder, stopped_run, marked_completed, reason}``.
    """
    from core import run_guard, run_state
    from core.pipeline_executor import new_run_id

    rid = run_id or new_run_id()
    project_dir = os.path.join(products_dir, project)
    report: Dict = {"project": project, "run_id": rid, "ok": False,
                    "lock_holder": "", "stopped_run": "", "marked_completed": []}

    # Backend log (product-forge/logs/pipeline-backend.log) + run log.
    try:
        from core import log_router as _lr
        _lr.log_event(_lr.backend_log_path(), run_id=rid, event="begin_run",
                      message=f"project={project} products_dir={products_dir}")
        _lr.log_event(_lr.run_log_path(project_dir, rid), run_id=rid, event="run_start",
                      message=f"project={project}")
        _lr.update_index(project_dir, rid)
    except Exception:
        pass
    try:
        from core import events as _ev
        _ev.emit(project_dir, "run_started", run_id=rid, project=project)
    except Exception:
        pass

    if not stop_existing:
        lm = LockManager(products_dir)
        lock = lm.acquire_lock(project, holder=f"run-{os.getpid()}", run_id=rid)
        if lock is None:
            report["reason"] = "already running"
            return report
        report.update(ok=True, lock_holder=lock.holder)
    else:
        rep = run_guard.ensure_single_run(project, products_dir, wait_seconds=wait_seconds,
                                          run_id=rid)
        if not rep.get("acquired"):
            report["reason"] = "could not acquire run lock"
            return report
        report.update(ok=True, lock_holder=f"run-{os.getpid()}",
                      stopped_run=rep.get("stopped_run", ""))

    # preserve-first reconciliation + run registration (never clears user data)
    try:
        bf = run_state.backfill_run_ids(project_dir)
        if bf.get("stamped") or bf.get("legacy"):
            report["backfilled"] = bf
        rc = run_state.reconcile(project_dir, run_id=rid,
                                 stopped_run=report.get("stopped_run", ""))
        report["marked_completed"] = rc.get("marked_completed", [])
    except Exception as e:
        report["reconcile_error"] = str(e)
    return report


def end_run(project: str, products_dir: str = "products",
            lock_holder: str = "run-%d" % os.getpid()) -> None:
    """Release the project lock (best-effort)."""
    try:
        LockManager(products_dir).release_lock(project, lock_holder)
    except Exception:
        pass
    try:
        from core import log_router as _lr
        project_dir = os.path.join(products_dir, project)
        _lr.log_event(_lr.backend_log_path(), event="end_run", message=f"project={project}")
        _lr.update_index(project_dir)
    except Exception:
        pass


def active(project: str, products_dir: str = "products") -> Dict:
    """Who (if anyone) is running this project now."""
    from core import run_guard
    return run_guard.active_run(project, products_dir)


def enqueue(project: str, products_dir: str = "products", tier: str = "",
            priority: int = 100, item_id: str = "", item_ids: Optional[list] = None,
            scheduled_at: str = "", source: str = "cli", actor: str = "") -> Dict:
    """THE single enqueue path — intake Execute/Schedule, dashboard, API, CLI all call this.

    Puts the run on the (enhanced) portfolio queue via the JobManager; the worker starts
    it when a slot frees (config/capacity.json max_parallel_projects). Does NOT execute.
    """
    from core import job_manager as jm
    from core.pipeline_executor import new_run_id
    rid = new_run_id()
    try:
        from core import portfolio
        portfolio.register(project, tier=tier)
    except Exception:
        pass
    entry = jm.enqueue(project, run_id=rid, tier=tier, priority=priority,
                       item_id=item_id, item_ids=item_ids, source=source, actor=actor,
                       not_before=scheduled_at)
    try:
        from core import run_state
        run_state.record_run(os.path.join(products_dir, project), rid, stages_completed=[])
    except Exception:
        pass
    try:
        from core import log_router as _lr
        _lr.log_event(_lr.backend_log_path(), run_id=rid, event="enqueue",
                      message=f"project={project} priority={priority} source={source} "
                              f"item={item_id or '-'} scheduled_at={scheduled_at or '-'}")
    except Exception:
        pass
    entry = dict(entry or {})
    entry.update({"run_id": rid, "queued": True})
    return entry


def queue_status(products_dir: str = "products") -> Dict:
    """Current queue + running/paused jobs (for API/UI/CLI)."""
    from core import job_manager as jm
    return jm.status()


def run_now_on_priority(project: str, *, by: str = "operator", item_id: str = "",
                        victim: str = "", products_dir: str = "products") -> Dict:
    """Free a slot for a priority job by pausing the least-urgent running job.

    Thin wrapper over the JobManager (single source of queue truth).
    """
    from core import job_manager as jm
    return jm.run_now_on_priority(project, by=by, item_id=item_id, victim=victim)
