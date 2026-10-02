"""Runs API (API-2): create/start/stop runs via the canonical run entry.

Long-running actions return a run identity; progress is observable via events and run-status. Execution is
owned by ``core.run_entry`` (the ONE way a run starts) — this router never executes a pipeline inline.
"""

import os
from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(tags=["runs"])


def _products_dir() -> str:
    from core import paths
    return paths.PRODUCTS_DIR


def _project_dir(project: str) -> str:
    p = str(project or "").strip()
    if not p or "/" in p or "\\" in p or p in (".", ".."):
        raise ApiError("VALIDATION_FAILED", "invalid project")
    d = os.path.join(_products_dir(), p)
    if not os.path.isdir(d):
        raise ApiError("NOT_FOUND", "project not found")
    return d


def _emit(project: str, event_type: str, **fields) -> None:
    try:
        from core import events
        events.emit(_project_dir(project), event_type, **fields)
    except Exception:
        pass


@router.get("/runs", dependencies=[Depends(authenticate)])
def list_runs(request: Request, project: str, ctx: dict[str, Any] = Depends(authenticate)):
    from core import run_status
    d = _project_dir(project)
    return from_request(request, run_status.summary(d), resource="run")


@router.get("/runs/time-cost", dependencies=[Depends(authenticate)])
def run_time_cost(request: Request, project: str, run_id: str = "",
                  ctx: dict[str, Any] = Depends(authenticate)):
    """Per-run worker time (active vs human-wait) + token/cost totals (reuses worker-results)."""
    from core import worker
    _project_dir(project)
    return from_request(request, worker.run_totals("project", project, run_id=run_id),
                        resource="run", resource_id=project)


@router.get("/runs/active", dependencies=[Depends(authenticate)])
def active_run(request: Request, project: str, ctx: dict[str, Any] = Depends(authenticate)):
    from core import run_entry
    d = _project_dir(project)
    return from_request(request, run_entry.active(os.path.basename(d), os.path.basename(_products_dir())),
                        resource="run")


@router.post("/runs/start", dependencies=[Depends(authenticate)])
def start_run(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import run_entry
    project = str(body.get("project") or "")
    _project_dir(project)
    actor = str(ctx.get("actor") or "")
    if body.get("now"):
        res = run_entry.run_now_on_priority(project, by=actor or "api",
                                            item_id=str(body.get("item_id") or ""),
                                            products_dir=_products_dir())
    else:
        res = run_entry.enqueue(project, _products_dir(), tier=str(body.get("tier") or ""),
                                priority=int(body.get("priority") or 100),
                                item_id=str(body.get("item_id") or ""),
                                source="api", actor=actor)
    rid = str((res or {}).get("run_id") or ((res or {}).get("enqueued") or {}).get("run_id") or "")
    _emit(project, "run_started", run_id=rid, source="api")
    return from_request(request, res, resource="run", status="accepted", resource_id=rid)


@router.post("/runs/stop", dependencies=[Depends(authenticate)])
def stop_run(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import job_manager
    project = str(body.get("project") or "")
    d = _project_dir(project)
    # 1) settle any queued/scheduled job for this project (queue SSOT = job_manager).
    cancelled: dict[str, Any] = {}
    try:
        cancelled = job_manager.cancel(project) or {}
    except Exception:
        cancelled = {}
    # 2) signal a live executor through the canonical cross-process control channel (control.json).
    signaled = False
    try:
        from core import portfolio, run_guard
        if run_guard.active_run(os.path.basename(d), os.path.basename(_products_dir())).get("active"):
            portfolio.control(project, "stop")
            signaled = True
    except Exception:
        signaled = False
    return from_request(request, {"project": project, "status": "stop_requested",
                                  "cancelled": bool(cancelled), "signaled": signaled},
                        resource="run")
