"""Validation API (API-3): canonical run verification + verification-policy coverage.

Read-models over ``core.close_loop`` (the scope-aware, run-bound verified/not decision) and
``core.verification_policy`` (internal/external/not_run classification). No shadow store.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from . import _common

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("", dependencies=[Depends(authenticate)])
def validation(project: str, request: Request, scope: str = "", run_id: str = "",
               ctx: Dict[str, Any] = Depends(authenticate)):
    from core import close_loop
    d = _common.project_dir(project)
    return from_request(request, close_loop.verify_run(d, scope=scope, run_id=run_id),
                        resource="validation", resource_id=project)


@router.get("/policy", dependencies=[Depends(authenticate)])
def policy(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import verification_policy
    d = _common.project_dir(project)
    return from_request(request, verification_policy.summary(d),
                        resource="validation", resource_id=project)
