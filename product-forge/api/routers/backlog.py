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


@router.get("/epics/{epic_id}/order", dependencies=[Depends(authenticate)])
def epic_order(epic_id: str, request: Request, scope: str = "product_forge", project: str = "",
               stage: str = "", ctx: dict[str, Any] = Depends(authenticate)):
    """READ-ONLY: execution order of an epic's OPEN children (dependency wave -> priority, READY/wait).

    Delegates to ``core.scheduler.epic_order`` (no writes). Use POST to persist the order on the epic.
    """
    from core import backlog, scheduler
    s, p = _scope_project(request, scope, project)
    if not backlog.get_epic(s, p, epic_id):
        raise ApiError("NOT_FOUND", "backlog epic not found")
    return from_request(request, scheduler.epic_order(s, p, epic=epic_id, stage=stage or None),
                        resource="backlog", resource_id=epic_id)


@router.post("/epics/{epic_id}/order", dependencies=[Depends(require_operator)])
def epic_order_save(epic_id: str, request: Request, scope: str = "product_forge", project: str = "",
                    stage: str = "", ctx: dict[str, Any] = Depends(require_operator)):
    """SAVE: compute the epic's execution order AND persist it on the epic (``execution_order[]``).

    BI-PF-1222: the write is delegated to ``core.backlog.set_execution_order`` (single writer). ``children[]``
    (membership) is never touched.
    """
    from core import backlog, scheduler
    s, p = _scope_project(request, scope, project)
    if not backlog.get_epic(s, p, epic_id):
        raise ApiError("NOT_FOUND", "backlog epic not found")
    return from_request(request, scheduler.epic_order(s, p, epic=epic_id, stage=stage or None, save=True),
                        resource="backlog", resource_id=epic_id)


@router.get("/status", dependencies=[Depends(authenticate)])
def backlog_status(request: Request, scope: str = "product_forge", project: str = "",
                   stage: str = "", all: bool = False, ctx: dict[str, Any] = Depends(authenticate)):
    """Scope-level status: every epic's rollup (open/closed/groomed/need_reanalysis/ready/wait) + standalone
    items. ``all=true`` aggregates across EVERY backlog/scope (BI-PF-1222). Read-only."""
    from core import scheduler
    if all:
        return from_request(request, scheduler.backlog_status_all(stage=stage or None), resource="backlog")
    s, p = _scope_project(request, scope, project)
    return from_request(request, scheduler.backlog_status(s, p, stage=stage or None), resource="backlog")


@router.get("/epics/{epic_id}/status", dependencies=[Depends(authenticate)])
def epic_status(epic_id: str, request: Request, scope: str = "product_forge", project: str = "",
                stage: str = "", ctx: dict[str, Any] = Depends(authenticate)):
    """Full lifecycle status of one epic: ALL children (open + closed) with state/status/groomed/
    needs_reanalysis/ready/worker/wave/order_rank/order_status/reasons + an epic rollup. Read-only."""
    from core import backlog, scheduler
    s, p = _scope_project(request, scope, project)
    if not backlog.get_epic(s, p, epic_id):
        raise ApiError("NOT_FOUND", "backlog epic not found")
    return from_request(request, scheduler.epic_status(s, p, epic=epic_id, stage=stage or None),
                        resource="backlog", resource_id=epic_id)


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


@router.post("/ids:reserve", dependencies=[Depends(require_operator)])
def reserve_ids(body: dict[str, Any], request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    """BI-PF-0462: the id-allocation authority - mint a contiguous id block for the calling session."""
    from core import id_allocator
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    blk = id_allocator.reserve(s, p, size=int(body.get("size") or 0),
                               session=str(body.get("session") or ""))
    return from_request(request, blk, resource="backlog")


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
                         depth=str(body.get("depth") or "deep"), force=bool(body.get("force")))
    if res.get("error") == "not found":
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/context-review", dependencies=[Depends(require_operator)])
def context_review_item(item_id: str, body: dict[str, Any], request: Request,
                        ctx: dict[str, Any] = Depends(require_operator)):
    """AI (LLM) review of an item's context: is it implementable (what/why/how/where)? Advisory."""
    from core import backlog, context_review
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    it = backlog.get_epic(s, p, item_id)
    if not it:
        raise ApiError("NOT_FOUND", "backlog item not found")
    res = context_review.review(it)
    return from_request(request, {"item_id": item_id, **res}, resource="backlog", resource_id=item_id)


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


@router.post("/groom", dependencies=[Depends(require_operator)])
def groom_batch(body: dict[str, Any], request: Request,
                ctx: dict[str, Any] = Depends(require_operator)):
    """Bulk groom every open item (BI-PF-1194): AI default, batched (default 3/pass), resumable."""
    from core import grooming
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    mode = str(body.get("mode") or "")
    if body.get("ai") is False and not mode:
        mode = "deterministic"
    res = grooming.groom_all(s, p, mode=mode, batch=int(body.get("batch") or 0),
                             limit=int(body.get("limit") or 0), force=bool(body.get("force")),
                             dry=bool(body.get("dry")), depth=str(body.get("depth") or "deep"),
                             jobs=int(body.get("jobs") or 0), ids=body.get("ids"))
    return from_request(request, res, resource="backlog")


@router.post("/restamp", dependencies=[Depends(require_operator)])
@router.post("/refresh-stale", dependencies=[Depends(require_operator)])
def refresh_stale(body: dict[str, Any], request: Request,
                  ctx: dict[str, Any] = Depends(require_operator)):
    """Re-stamp OPEN items whose analysis is stale vs the current architecture (alias: /refresh-stale).

    Re-analyzes each item and records the current ``arch_fingerprint`` (does NOT overwrite authored context).
    Deterministic by default; ``mode="ai"`` (or ``ai=true``) for a deep AI refresh. ``limit`` caps items per call.
    """
    from core import grooming
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    mode = str(body.get("mode") or "")
    if body.get("ai") is True and not mode:
        mode = "ai"
    res = grooming.refresh_stale(s, p, limit=int(body.get("limit") or 0) or 1_000_000,
                                 mode=mode or "deterministic")
    return from_request(request, res, resource="backlog")


@router.post("/groom/approve", dependencies=[Depends(require_operator)])
def groom_approve_batch(body: dict[str, Any], request: Request,
                        ctx: dict[str, Any] = Depends(require_operator)):
    """Bulk grooming decision (default APPROVE) over groomed items (BI-PF-1194)."""
    from core import grooming
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = grooming.decide_all(s, p, str(body.get("decision") or "APPROVE"), ids=body.get("ids"),
                              force=bool(body.get("force")), dry=bool(body.get("dry")),
                              by=str(body.get("by") or "user"))
    return from_request(request, res, resource="backlog")


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

