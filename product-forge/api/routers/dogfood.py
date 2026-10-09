"""DOGFOOD Phase 1 API (BI-PF-0458): on-demand, auto-mode product-generation dogfood.

API-first surface over ``core.dogfood_run`` (composes ``core.run_entry`` + project seeding + observability).
Reads are ``authenticate``; starting a run is ``require_operator``. No store/engine here.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/dogfood", tags=["dogfood"])


@router.post("/run", dependencies=[Depends(require_operator)])
def dogfood_run(body: Dict[str, Any], request: Request,
                ctx: Dict[str, Any] = Depends(require_operator)):
    from core import dogfood_run as dr
    project = str(body.get("project") or "").strip()
    idea = str(body.get("idea") or "").strip()
    if not project or not idea:
        raise ApiError("VALIDATION_FAILED", "project and idea are required")
    res = dr.start(idea, project, tier=str(body.get("tier") or "kctier"),
                   auto=bool(body.get("auto", True)), caps=body.get("caps") or {},
                   target=str(body.get("target") or ""))
    return from_request(request, res, resource="dogfood", status="accepted",
                        resource_id=str(res.get("run_id") or project))


@router.get("/runs/{run_id}", dependencies=[Depends(authenticate)])
def dogfood_status(run_id: str, request: Request, project: str = "",
                   ctx: Dict[str, Any] = Depends(authenticate)):
    from core import dogfood_run as dr
    if not project:
        raise ApiError("VALIDATION_FAILED", "project is required")
    return from_request(request, dr.status(project, run_id=run_id), resource="dogfood", resource_id=run_id)
