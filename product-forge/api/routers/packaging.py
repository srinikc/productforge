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


@router.get("/eap", dependencies=[Depends(authenticate)])
def get_eap(request: Request, scope: str = "product_forge", project: str = "", edition: str = "community",
            ctx: dict[str, Any] = Depends(authenticate)):
    from core import packaging
    s, p = _scope_project(scope, project)
    return from_request(request, packaging.eap_build(s, p or "", edition=edition),
                        resource="packaging", resource_id=p or s)


@router.get("/eap/registry", dependencies=[Depends(authenticate)])
def get_eap_registry(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import packaging
    return from_request(request, packaging.eap_registry(), resource="packaging")


@router.get("/eap/validate", dependencies=[Depends(authenticate)])
def validate_eap(request: Request, scope: str = "product_forge", project: str = "", edition: str = "community",
                 ctx: dict[str, Any] = Depends(authenticate)):
    from core import packaging
    s, p = _scope_project(scope, project)
    eap = packaging.eap_build(s, p or "", edition=edition)
    return from_request(request, {**packaging.eap_validate(eap), "compatibility": packaging.eap_compatible(eap),
                                  "edition": eap.get("edition")}, resource="packaging", resource_id=p or s)


@router.post("/eap", dependencies=[Depends(require_operator)])
def write_eap(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    from core import packaging
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    ed = str(body.get("edition") or "community")
    if packaging._resolve_edition(ed) is None:
        raise ApiError("VALIDATION_FAILED", "unknown edition", details={"edition": ed,
                                                                        "editions": list(packaging.EDITIONS)})
    return from_request(request, packaging.eap_write(s, p or "", edition=ed), resource="packaging",
                        resource_id=p or s)


@router.post("/rdc/compose", dependencies=[Depends(require_operator)])
def rdc_compose_endpoint(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    from core import rdc
    eap = body.get("eap") or {}
    target_os = str(body.get("target_os") or "linux")
    target_arch = str(body.get("target_arch") or "amd64")
    edition = str(body.get("edition") or "community")
    license_tier = str(body.get("license_tier") or "")
    dry_run = bool(body.get("dry_run", False))
    res = rdc.compose(eap=eap, target_os=target_os, target_arch=target_arch,
                      edition=edition, license_tier=license_tier, dry_run=dry_run)
    if not res.get("ok"):
        raise ApiError("VALIDATION_FAILED", res.get("error", "rdc compose failed"), details=res)
    return from_request(request, res, resource="packaging")


@router.post("/rdc/validate", dependencies=[Depends(require_operator)])
def rdc_validate_endpoint(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    from core import rdc
    edition = str(body.get("edition") or "community")
    files = list(body.get("files") or [])
    res = rdc.validate_ip(edition=edition, files=files)
    if not res.get("valid"):
        raise ApiError("VALIDATION_FAILED", res.get("error", "IP leakage detected"), details=res)
    return from_request(request, res, resource="packaging")
