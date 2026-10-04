"""Backlog API (API-2): inspect/update the canonical backlog via core.backlog services."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
from ..pagination import paginate

router = APIRouter(prefix="/backlog", tags=["backlog"])


def _scope_project(request: Request, scope: str, project: str):
    s = str(scope or "product_forge").strip()
    p = str(project or "").strip() or None
    if s not in ("product_forge", "project"):
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project",
                       details={"scope": s})
    if s == "project" and not p:
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


@router.get("", dependencies=[Depends(authenticate)])
def list_backlog(request: Request, scope: str = "product_forge", project: str = "",
                 status: str = "", limit: int = 50, cursor: str = "",
                 ctx: dict[str, Any] = Depends(authenticate)):
    from core import backlog
    s, p = _scope_project(request, scope, project)
    items: list[dict[str, Any]] = backlog.list_items(s, p, status=status) if status else \
        (backlog.list_open(s, p) + backlog.list_closed(s, p))
    page, links = paginate(items, limit=limit, cursor=cursor)
    return from_request(request, page, resource="backlog", links=links)


@router.get("/stats", dependencies=[Depends(authenticate)])
def stats(request: Request, scope: str = "product_forge", project: str = "",
          ctx: dict[str, Any] = Depends(authenticate)):
    from core import backlog
    s, p = _scope_project(request, scope, project)
    return from_request(request, backlog.stats(s, p), resource="backlog")


@router.get("/items/{item_id}", dependencies=[Depends(authenticate)])
def get_item(item_id: str, request: Request, scope: str = "product_forge", project: str = "",
             ctx: dict[str, Any] = Depends(authenticate)):
    from core import backlog
    s, p = _scope_project(request, scope, project)
    it = backlog.get(s, p, item_id)
    if not it:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, it, resource="backlog", resource_id=item_id)


@router.post("/items", dependencies=[Depends(require_operator)])
def add_item(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    title = str(body.get("title") or "").strip()
    if not title:
        raise ApiError("VALIDATION_FAILED", "title required")
    it = backlog.add_epic(s, p, title, body=str(body.get("body") or ""),
                          source="api", type_=str(body.get("type") or "feature"),
                          origin="api", tag=str(body.get("tag") or ""))
    return from_request(request, it, resource="backlog", resource_id=str(it.get("id") or ""))


@router.post("/items/{item_id}/status", dependencies=[Depends(require_operator)])
def set_status(item_id: str, body: dict[str, Any], request: Request,
               ctx: dict[str, Any] = Depends(require_operator)):
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    status = str(body.get("status") or "").strip()
    if not status:
        raise ApiError("VALIDATION_FAILED", "status required")
    try:
        res = backlog.set_status(s, p, item_id, status, note=str(body.get("note") or ""))
    except Exception as e:
        raise ApiError("CONFLICT", f"status change refused: {type(e).__name__}") from e
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


# ── PFSSOT-P1 (BI-PF-0362): first-class execution fields (analysis/priority/deps/execution) ──
@router.post("/items/{item_id}/analysis", dependencies=[Depends(require_operator)])
def set_analysis(item_id: str, body: dict[str, Any], request: Request,
                 ctx: dict[str, Any] = Depends(require_operator)):
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    try:
        res = backlog.set_analysis(s, p, item_id, status=str(body.get("status") or ""),
                                   architecture_fit=str(body.get("architecture_fit") or ""),
                                   implementation_strategy=str(body.get("implementation_strategy") or ""),
                                   analysis=body.get("analysis") or None,
                                   analyzed_by=str(body.get("analyzed_by") or "api"))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/priority", dependencies=[Depends(require_operator)])
def set_priority(item_id: str, body: dict[str, Any], request: Request,
                 ctx: dict[str, Any] = Depends(require_operator)):
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = backlog.set_priority(s, p, item_id, priority=body.get("priority"),
                               priority_rank=body.get("priority_rank"),
                               priority_class=str(body.get("priority_class") or ""),
                               moscow=str(body.get("moscow") or ""))
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.get("/grooming/guidelines", dependencies=[Depends(authenticate)])
def grooming_guidelines(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import grooming
    return from_request(request, grooming.guidelines(), resource="backlog")


@router.post("/items/{item_id}/groom", dependencies=[Depends(require_operator)])
def groom_item(item_id: str, body: dict[str, Any], request: Request,
               ctx: dict[str, Any] = Depends(require_operator)):
    """AI grooming by default; pass mode='deterministic' (or ai=false) for the no-AI path."""
    from core import grooming
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    mode = str(body.get("mode") or "")
    if body.get("ai") is False and not mode:
        mode = "deterministic"
    res = grooming.groom(s, p, item_id, mode=mode, product=str(body.get("product") or ""),
                         depth=str(body.get("depth") or "deep"))
    if res.get("error") == "not found":
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/groom/decide", dependencies=[Depends(require_operator)])
def groom_decide(item_id: str, body: dict[str, Any], request: Request,
                 ctx: dict[str, Any] = Depends(require_operator)):
    """User grooming decision: APPROVE | MODIFY | REJECT | DEFER."""
    from core import grooming
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    try:
        res = grooming.decide(s, p, item_id, str(body.get("decision") or ""),
                              note=str(body.get("note") or ""), by=str(body.get("by") or "user"))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res.get("error") == "not found":
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/dependencies", dependencies=[Depends(require_operator)])
def set_dependencies(item_id: str, body: dict[str, Any], request: Request,
                     ctx: dict[str, Any] = Depends(require_operator)):
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    try:
        res = backlog.set_dependencies(s, p, item_id, dependencies=body.get("dependencies"),
                                       blocked_by=body.get("blocked_by"), unlocks=body.get("unlocks"))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)

