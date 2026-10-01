"""Engineering architecture API (ENG-0): the requirement -> deploy flow over the API-1..API-3 contracts.

Read-model over ``core.engineering_flow`` (``config/engineering-flow.json``): each step with its canonical
owner file, the ``/api/v1`` route that exposes it, and its status (exists | partial | planned). No engine.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/engineering", tags=["engineering"])


@router.get("", dependencies=[Depends(authenticate)])
def engineering(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    return from_request(request, engineering_flow.load(), resource="engineering")


@router.get("/stages", dependencies=[Depends(authenticate)])
def stages(request: Request, phase: str = "", status: str = "",
           ctx: Dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    steps: List[Dict[str, Any]] = engineering_flow.flow()
    if phase:
        steps = [s for s in steps if str(s.get("phase")) == phase]
    if status:
        steps = [s for s in steps if str(s.get("status")) == status]
    return from_request(request, steps, resource="engineering")


@router.get("/stages/{stage_id}", dependencies=[Depends(authenticate)])
def stage(stage_id: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    s = engineering_flow.stage(stage_id)
    if not s:
        raise ApiError("NOT_FOUND", "engineering stage not found")
    return from_request(request, s, resource="engineering", resource_id=stage_id)


@router.get("/coverage", dependencies=[Depends(authenticate)])
def coverage(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    return from_request(request, engineering_flow.coverage(), resource="engineering")
