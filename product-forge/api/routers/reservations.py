"""Shared-path reservation API (ENG-8): advisory holds + common-code detection.

Maps to ``core.reservations`` (allowlist detection, git-hotspot heuristic, runtime reservations).
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.get("", dependencies=[Depends(authenticate)])
def list_reservations(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import reservations
    return from_request(request, reservations.list_active(), resource="reservation")


@router.get("/shared-paths", dependencies=[Depends(authenticate)])
def shared_paths(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import reservations
    return from_request(request, {"config": reservations.shared_config(),
                                  "hotspots": reservations.hotspots()},
                        resource="reservation")


@router.post("", dependencies=[Depends(require_operator)])
def acquire(body: dict[str, Any], request: Request,
            ctx: dict[str, Any] = Depends(require_operator)):
    from core import reservations
    resource = str(body.get("resource") or "")
    if not resource:
        raise ApiError("VALIDATION_FAILED", "resource required")
    res = reservations.acquire(resource, holder_task=str(body.get("task_id") or ""),
                               holder_worker=str(body.get("worker") or ""),
                               run_id=str(body.get("run_id") or ""),
                               ttl_s=int(body.get("ttl_s") or 3600))
    if not res.get("ok"):
        raise ApiError("CONFLICT", res.get("reason") or "reserved", details={"holder": res.get("holder")})
    return from_request(request, res["reservation"], resource="reservation",
                        resource_id=res["reservation"]["id"])


@router.post("/release", dependencies=[Depends(require_operator)])
def release(body: dict[str, Any], request: Request,
            ctx: dict[str, Any] = Depends(require_operator)):
    from core import reservations
    resource = str(body.get("resource") or "")
    if not resource:
        raise ApiError("VALIDATION_FAILED", "resource required")
    reservations.release(resource)
    return from_request(request, {"resource": resource, "released": True}, resource="reservation")
