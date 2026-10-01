"""Worker / queue API (API-3): queue + capacity view and pause/resume control.

Maps to ``core.run_entry`` / ``core.job_manager`` (the queue SSOT) and ``core.capacity`` (limits).
Reads are authenticated; controls are operator-gated. No shadow store.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from . import _common

router = APIRouter(prefix="/workers", tags=["workers"])


def _reason(job: Dict[str, Any]) -> str:
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
def queue(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import run_entry
    st = run_entry.queue_status()
    for job in st.get("jobs", []):
        job["reason"] = _reason(job)
    return from_request(request, st, resource="worker")


@router.get("/capacity", dependencies=[Depends(authenticate)])
def capacity(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import capacity as _capacity
    return from_request(request, _capacity.status(), resource="worker")


@router.post("/queue/{project}/pause", dependencies=[Depends(require_operator)])
def pause(project: str, request: Request,
          ctx: Dict[str, Any] = Depends(require_operator)):
    from core import job_manager
    _common.project_dir(project)
    return from_request(request, job_manager.pause_request(project, by=str(ctx.get("actor") or "api")),
                        resource="worker", resource_id=project)


@router.post("/queue/{project}/resume", dependencies=[Depends(require_operator)])
def resume(project: str, request: Request,
           ctx: Dict[str, Any] = Depends(require_operator)):
    from core import job_manager
    _common.project_dir(project)
    return from_request(request, job_manager.resume(project),
                        resource="worker", resource_id=project)
