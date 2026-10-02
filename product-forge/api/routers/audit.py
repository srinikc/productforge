"""Final audit API: production-readiness acceptance criteria (plan section 42) + full lifecycle E2E.

Read-models over ``core.audit`` (mechanical acceptance audit) and ``core.e2e_lifecycle`` (full lifecycle).
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/acceptance", dependencies=[Depends(authenticate)])
def acceptance(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import audit
    return from_request(request, audit.run(), resource="audit")


@router.get("/readiness", dependencies=[Depends(authenticate)])
def readiness(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import audit
    return from_request(request, audit.summary(), resource="audit")


@router.post("/e2e", dependencies=[Depends(require_operator)])
def e2e(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    from core import e2e_lifecycle
    res = e2e_lifecycle.run(project=str(body.get("project") or ""),
                            dry=bool(body.get("dry", True)), keep=bool(body.get("keep") or False))
    return from_request(request, res, resource="audit", resource_id=str(res.get("project") or ""))
