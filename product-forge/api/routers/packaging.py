"""Packaging API (REL-0): edition-specific package manifest build/validate + editions.

Read/build surface over ``core.packaging`` (which composes ``bom``/``build_manager``/``licensing``/
``deploy_providers``/``release_manager``). Commercial/licensing decisions remain human-governed.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/packaging", tags=["packaging"])


def _scope_project(scope: str, project: str):
    s = str(scope or "product_forge").strip()
    p = str(project or "").strip() or None
    if s not in ("product_forge", "project"):
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project")
    if s == "project" and not p:
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


@router.get("/editions", dependencies=[Depends(authenticate)])
def list_editions(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import packaging
    return from_request(request, {"editions": packaging.editions(), "distinctions": list(packaging.DISTINCTIONS)},
                        resource="packaging")


@router.get("/manifest", dependencies=[Depends(authenticate)])
def get_manifest(request: Request, scope: str = "product_forge", project: str = "",
                 ctx: dict[str, Any] = Depends(authenticate)):
    from core import packaging
    s, p = _scope_project(scope, project)
    return from_request(request, packaging.load(s, p or ""), resource="packaging", resource_id=p or s)


@router.get("/validate", dependencies=[Depends(authenticate)])
def validate(request: Request, scope: str = "product_forge", project: str = "",
             edition: str = "community", ctx: dict[str, Any] = Depends(authenticate)):
    from core import packaging
    s, p = _scope_project(scope, project)
    m = packaging.build(s, p or "", edition=edition)
    return from_request(request, {**packaging.validate(m), "edition": m.get("edition")},
                        resource="packaging", resource_id=p or s)


@router.post("/build", dependencies=[Depends(require_operator)])
def build(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    from core import packaging
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    ed = str(body.get("edition") or "community")
    if packaging._resolve_edition(ed) is None:
        raise ApiError("VALIDATION_FAILED", "unknown edition", details={"edition": ed,
                                                                        "editions": list(packaging.EDITIONS)})
    return from_request(request, packaging.write(s, p or "", edition=ed),
                        resource="packaging", resource_id=p or s)
