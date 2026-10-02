"""Worker / queue API (API-3): queue + capacity view and pause/resume control.

Maps to ``core.run_entry`` / ``core.job_manager`` (the queue SSOT) and ``core.capacity`` (limits).
Reads are authenticated; controls are operator-gated. No shadow store.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from . import _common

router = APIRouter(prefix="/workers", tags=["workers"])


def _reason(job: dict[str, Any]) -> str:
    state = job.get("state")
    if state == "scheduled" and job.get("not_before"):
        return f"waiting until {job['not_before']}"
    if state == "paused" and job.get("resume_after"):
        return f"waiting on {job['resume_after']}"
    if state == "pause_pending":
        return "parking at next checkpoint"
    if state == "queued":
        return "waiting for a free slot"
    return ""


@router.get("/queue", dependencies=[Depends(authenticate)])
def queue(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import run_entry
    st = run_entry.queue_status()
    for job in st.get("jobs", []):
        job["reason"] = _reason(job)
    return from_request(request, st, resource="worker")


@router.get("/capacity", dependencies=[Depends(authenticate)])
def capacity(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import capacity as _capacity
    return from_request(request, _capacity.status(), resource="worker")


@router.get("/metrics", dependencies=[Depends(authenticate)])
def metrics(request: Request, scope: str = "product_forge", project: str = "", run_id: str = "",
            ctx: dict[str, Any] = Depends(authenticate)):
    """Worker timing (active vs human-wait) + token/cost totals (reuses worker-results store)."""
    from core import worker
    if scope not in ("product_forge", "project"):
        from ..errors import ApiError
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project")
    p = project or None
    return from_request(request, worker.run_totals(scope, p, run_id=run_id),
                        resource="worker", resource_id=project or scope)


@router.get("/results", dependencies=[Depends(authenticate)])
def results(request: Request, scope: str = "product_forge", project: str = "", task_id: str = "",
            ctx: dict[str, Any] = Depends(authenticate)):
    from core import worker
    p = project or None
    rows = worker.list_results(scope, p, task_id=task_id)
    out = [{"task_id": r.get("task_id"), "worker_id": r.get("worker_id"), "status": r.get("status"),
            "timing": r.get("timing") or {}, "usage": r.get("usage") or {}} for r in rows]
    return from_request(request, out, resource="worker", resource_id=project or scope)


@router.post("/queue/{project}/pause", dependencies=[Depends(require_operator)])
def pause(project: str, request: Request,
          ctx: dict[str, Any] = Depends(require_operator)):
    from core import job_manager
    _common.project_dir(project)
    return from_request(request, job_manager.pause_request(project, by=str(ctx.get("actor") or "api")),
                        resource="worker", resource_id=project)


@router.post("/queue/{project}/resume", dependencies=[Depends(require_operator)])
def resume(project: str, request: Request,
           ctx: dict[str, Any] = Depends(require_operator)):
    from core import job_manager
    _common.project_dir(project)
    return from_request(request, job_manager.resume(project),
                        resource="worker", resource_id=project)
