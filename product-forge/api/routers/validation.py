"""Validation API (API-3): canonical run verification + verification-policy coverage.

Read-models over ``core.close_loop`` (the scope-aware, run-bound verified/not decision) and
``core.verification_policy`` (internal/external/not_run classification). No shadow store.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
from . import _common

router = APIRouter(prefix="/validation", tags=["validation"])


def _scope_project(scope: str, project: str):
    s = str(scope or "project").strip()
    p = str(project or "").strip() or None
    if s not in ("product_forge", "project"):
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project")
    if s == "project" and not p:
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


@router.get("", dependencies=[Depends(authenticate)])
def validation(project: str, request: Request, scope: str = "", run_id: str = "",
               ctx: dict[str, Any] = Depends(authenticate)):
    from core import close_loop
    d = _common.project_dir(project)
    return from_request(request, close_loop.verify_run(d, scope=scope, run_id=run_id),
                        resource="validation", resource_id=project)


@router.get("/policy", dependencies=[Depends(authenticate)])
def policy(project: str, request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import verification_policy
    d = _common.project_dir(project)
    return from_request(request, verification_policy.summary(d),
                        resource="validation", resource_id=project)


# ── ENG-6: Common Validation Engine (profiles) ──────────────────────────────

@router.get("/profiles", dependencies=[Depends(authenticate)])
def validation_profiles(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import validation_engine
    return from_request(request, validation_engine.profiles(), resource="validation")


@router.get("/runs", dependencies=[Depends(authenticate)])
def validation_runs(request: Request, scope: str = "project", project: str = "", profile: str = "",
                    ctx: dict[str, Any] = Depends(authenticate)):
    from core import validation_engine
    s, p = _scope_project(scope, project)
    return from_request(request, validation_engine.list_runs(s, p, profile=profile),
                        resource="validation", resource_id=project)


@router.post("/run", dependencies=[Depends(require_operator)])
def run_validation(body: dict[str, Any], request: Request,
                   ctx: dict[str, Any] = Depends(require_operator)):
    from core import validation_engine
    s, p = _scope_project(str(body.get("scope") or "project"), str(body.get("project") or ""))
    prof = str(body.get("profile") or "FEATURE_PR")
    if validation_engine.profile(prof) is None:
        raise ApiError("VALIDATION_FAILED", "unknown validation profile", details={"profile": prof})
    if s == "product_forge":
        from core.paths import ROOT
        d = ROOT
    else:
        d = _common.project_dir(p)
    res = validation_engine.run(p or s, d, profile_name=prof, target=str(body.get("target") or ""),
                                base=str(body.get("base") or ""), run_id=str(body.get("run_id") or ""),
                                scope=s)
    return from_request(request, res, resource="validation", resource_id=str(res.get("run_id") or ""))
