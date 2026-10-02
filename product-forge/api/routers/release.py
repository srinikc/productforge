"""Release API (ENG-10): release readiness + fail-closed release gate.

Read-models over ``core.release`` (which composes ``validation_engine`` RELEASE profile, ``bom``,
``build_manager``, ``deploy_providers``, ``merge_gate``). The mechanical gate only; licensing/
entitlement decisions are human-governed (REL-0).
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/release", tags=["release"])


def _scope_project(scope: str, project: str):
    s = str(scope or "product_forge").strip()
    p = str(project or "").strip() or None
    if s not in ("product_forge", "project"):
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project")
    if s == "project" and not p:
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


@router.get("/readiness", dependencies=[Depends(authenticate)])
def readiness(request: Request, scope: str = "product_forge", project: str = "", target: str = "",
              run_id: str = "", ctx: dict[str, Any] = Depends(authenticate)):
    from core import release
    s, p = _scope_project(scope, project)
    return from_request(request, release.readiness(s, p or "", target=target, run_id=run_id),
                        resource="release", resource_id=p or s)


@router.get("/gate", dependencies=[Depends(authenticate)])
def gate(request: Request, scope: str = "product_forge", project: str = "", target: str = "",
         run_id: str = "", ctx: dict[str, Any] = Depends(authenticate)):
    from core import release
    s, p = _scope_project(scope, project)
    return from_request(request, release.gate(s, p or "", target=target, run_id=run_id),
                        resource="release", resource_id=p or s)


@router.get("/evidence", dependencies=[Depends(authenticate)])
def evidence(request: Request, limit: int = 50, ctx: dict[str, Any] = Depends(authenticate)):
    from core import release
    return from_request(request, release.list_evidence(limit=limit), resource="release")


@router.post("/gate", dependencies=[Depends(require_operator)])
def evaluate_gate(body: dict[str, Any], request: Request,
                  ctx: dict[str, Any] = Depends(require_operator)):
    from core import release
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    g = release.gate(s, p or "", target=str(body.get("target") or ""),
                     run_id=str(body.get("run_id") or ""))
    if body.get("record"):
        release.record_evidence(g)
    return from_request(request, g, resource="release", resource_id=p or s)
