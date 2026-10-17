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


def _guard_revision(backlog, scope: str, project: str | None, item_id: str, expected) -> None:
    """Optimistic concurrency (BI-PF-0360): reject a write whose expected revision is stale (409).

    The API is the single writer; an item carries a monotonic ``revision`` (bumped by
    ``core.backlog.update`` on material changes). Callers may pass ``expected_revision`` to detect a
    concurrent read-modify-write instead of silently clobbering (last-write-wins). Omitted -> no check.
    Durable multi-host concurrency arrives with the EDP Postgres system of record (EDP-17/18 + G3).
    """
    if expected in (None, ""):
        return
    it = backlog.get_epic(scope, project, item_id)
    if it is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    try:
        want, current = int(expected), int(it.get("revision") or 0)
    except (TypeError, ValueError):
        raise ApiError("VALIDATION_FAILED", "expected_revision must be an integer") from None
    if current != want:
        raise ApiError("CONFLICT", f"stale revision: expected {want}, current {current}")


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
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"),
                          str(body.get("project") or ""))
    title = str(body.get("title") or "").strip()
    if not title:
        raise ApiError("VALIDATION_FAILED", "title required")
    typ = str(body.get("type") or "feature")
    ac = body.get("acceptance_criteria") or []
    if isinstance(ac, str):
        ac = [ac]
    ac = [str(x).strip() for x in ac if str(x).strip()]
    if typ != "epic":
        # BI-PF-1410: detailed Acceptance Criteria are the DoD - creation fails without them.
        if not ac:
            raise ApiError("VALIDATION_FAILED", "acceptance_criteria required (>=1 detailed criterion)")
        if any(len(x) < 40 for x in ac):
            raise ApiError("VALIDATION_FAILED", "each acceptance criterion must be >= 40 characters (detailed DoD)")
    external_id = str(body.get("external_id") or "")
    try:
        if external_id:
            it = backlog.ensure_item(s, p, external_id, title, type_=typ,
                                     origin="api", tag=str(body.get("tag") or ""))
            if ac and not (it.get("acceptance_criteria") or []):
                it = backlog.update(s, p, str(it.get("id")), acceptance_criteria=ac) or it
        else:
            it = backlog.add_epic(s, p, title, body=str(body.get("body") or ""),
                                  source="api", type_=typ,
                                  origin="api", tag=str(body.get("tag") or ""),
                                  epic=str(body.get("epic") or ""), acceptance_criteria=ac or None)
    except (RuntimeError, TimeoutError) as e:
        # BI-PF-1387: id allocation can be unavailable -> 503 (not a 500), never hang.
        raise ApiError("DEPENDENCY_UNAVAILABLE", f"id allocation unavailable: {e}") from None
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
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    status = str(body.get("status") or "").strip()
    if not status:
        raise ApiError("VALIDATION_FAILED", "status required")
    if status.lower() in ("completed", "done", "closed"):
        # BI-PF-1413 closure guard: an item cannot be completed unless its DoD is met AND the verification is
        # independent (verifier != implementer). Prevents closing partial/self-verified work.
        it = backlog.get_epic(s, p, item_id)
        if it is None:
            raise ApiError("NOT_FOUND", "backlog item not found")
        if not backlog.is_epic(it):
            if not (it.get("acceptance_criteria") or []):
                raise ApiError("VALIDATION_FAILED", "cannot complete: acceptance_criteria missing (DoD)")
            if not (it.get("verification") or it.get("evidence")):
                raise ApiError("VALIDATION_FAILED", "cannot complete: verification/evidence missing")
            vb = str(it.get("verified_by") or "").strip()
            wi = str(it.get("worker_id") or "").strip()
            if not vb:
                raise ApiError("VALIDATION_FAILED", "cannot complete: verified_by missing (independent verifier)")
            if wi and vb == wi:
                raise ApiError("VALIDATION_FAILED", "cannot complete: verifier must differ from implementer (worker_id)")
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
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
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
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
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
    from core import backlog
    res["decision_request"] = ((backlog.get_epic(s, p, item_id) or {}).get("analysis") or {}).get("decision_request")
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


@router.get("/grooming/stranded", dependencies=[Depends(authenticate)])
def grooming_stranded(request: Request, scope: str = "product_forge", project: str = "",
                      ctx: dict[str, Any] = Depends(authenticate)):
    """Items left IN_PROGRESS/NOT_ANALYZED with an explicit decision request awaiting a human (BI-PF-1319)."""
    from core import grooming
    s, p = _scope_project(request, scope, project)
    return from_request(request, grooming.stranded(s, p), resource="backlog")


@router.post("/items/{item_id}/dependencies", dependencies=[Depends(require_operator)])
def set_dependencies(item_id: str, body: dict[str, Any], request: Request,
                     ctx: dict[str, Any] = Depends(require_operator)):
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    try:
        res = backlog.set_dependencies(s, p, item_id, dependencies=body.get("dependencies"),
                                       blocked_by=body.get("blocked_by"), unlocks=body.get("unlocks"))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/epic", dependencies=[Depends(require_operator)])
def set_item_epic(item_id: str, body: dict[str, Any], request: Request,
                  ctx: dict[str, Any] = Depends(require_operator)):
    """Assign/move an item to an epic (single writer ``core.backlog.move_to_epic``).

    Every backlog item belongs to an epic; this exposes the assignment so it can be done API-only.
    """
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    epic_id = str(body.get("epic") or "").strip()
    if not epic_id:
        raise ApiError("VALIDATION_FAILED", "epic required")
    if not backlog.get_epic(s, p, epic_id):
        raise ApiError("NOT_FOUND", "epic not found")
    try:
        res = backlog.move_to_epic(s, p, item_id, epic_id, note=str(body.get("note") or ""))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/delivery", dependencies=[Depends(require_operator)])
def set_delivery(item_id: str, body: dict[str, Any], request: Request,
                 ctx: dict[str, Any] = Depends(require_operator)):
    """Record delivery provenance (``branch``/``merge_sha``/``commits``/``pr``/``pr_url``).

    Completes the traceability loop backlog item -> branch -> merge -> PR without hand-editing the store.
    """
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    res = backlog.set_delivery(s, p, item_id, branch=str(body.get("branch") or ""),
                               merge_sha=str(body.get("merge_sha") or ""),
                               commits=body.get("commits") or None,
                               pr=str(body.get("pr") or ""), pr_url=str(body.get("pr_url") or ""),
                               note=str(body.get("note") or ""))
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


# ── Full backlog e2e workflow over the API (BI-PF-0360): expose the remaining core.backlog writers so
# every workflow step is API-only (no direct access). Each endpoint is a thin wrapper over the single
# writer; no new logic. ──
_CONTEXT_FIELDS = ("objective", "acceptance_criteria", "in_scope", "out_of_scope",
                   "affected_components", "affected_files", "approach", "verification",
                   "risks", "rollback", "evidence", "owner", "summary", "brief", "verified_by",
                   "review_dispositions")


@router.post("/items/{item_id}/context", dependencies=[Depends(require_operator)])
def set_item_context(item_id: str, body: dict[str, Any], request: Request,
                     ctx: dict[str, Any] = Depends(require_operator)):
    """Author an item's context fields deterministically (no AI) - the API-only take-up path.

    Whitelisted fields are written via ``core.backlog.update`` (single writer). Empty/None values are ignored.
    """
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    fields = {k: body[k] for k in _CONTEXT_FIELDS if body.get(k) not in (None, "", [], {})}
    if not fields:
        raise ApiError("VALIDATION_FAILED", "no context fields provided (allowed: " + ", ".join(_CONTEXT_FIELDS) + ")")
    try:
        res = backlog.update(s, p, item_id, **fields)
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/links", dependencies=[Depends(require_operator)])
def set_item_links(item_id: str, body: dict[str, Any], request: Request,
                   ctx: dict[str, Any] = Depends(require_operator)):
    """Merge references into ``item.links`` (ids only); cross-scope refs must be scope-qualified."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    refs = body.get("refs") or body.get("links") or {}
    if not isinstance(refs, dict) or not refs:
        raise ApiError("VALIDATION_FAILED", "refs (object of link references) required")
    res = backlog.link(s, p, item_id, **refs)
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/pair", dependencies=[Depends(require_operator)])
def pair_item(item_id: str, body: dict[str, Any], request: Request,
              ctx: dict[str, Any] = Depends(require_operator)):
    """Cross-link two items reciprocally via ``links.paired_with`` (``other_ref`` scope-qualified)."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    other = str(body.get("other_ref") or "").strip()
    if not other:
        raise ApiError("VALIDATION_FAILED", "other_ref required")
    try:
        res = backlog.pair(s, p, item_id, other, capability=body.get("capability"))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/triage", dependencies=[Depends(require_operator)])
def triage_item(item_id: str, body: dict[str, Any], request: Request,
                ctx: dict[str, Any] = Depends(require_operator)):
    """Triage an item (recommendation + value/effort/risk/moscow) -> status ``triaged``."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    res = backlog.triage(s, p, item_id, recommendation=str(body.get("recommendation") or ""),
                         value=body.get("value"), effort=body.get("effort"), risk=body.get("risk"),
                         moscow=body.get("moscow"))
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/accept", dependencies=[Depends(require_operator)])
def accept_item(item_id: str, body: dict[str, Any], request: Request,
                ctx: dict[str, Any] = Depends(require_operator)):
    """Accept an item: ``when=now`` -> queued; ``when=later`` -> accepted (unscheduled)."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    res = backlog.accept(s, p, item_id, when=str(body.get("when") or "later"), by=str(body.get("by") or "hil"))
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/follow-up", dependencies=[Depends(require_operator)])
def set_item_follow_up(item_id: str, body: dict[str, Any], request: Request,
                       ctx: dict[str, Any] = Depends(require_operator)):
    """Set an item's follow-up review schedule (at / every_days / snooze_days)."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    kw = {}
    if body.get("every_days") not in (None, ""):
        kw["every_days"] = int(body["every_days"])
    if body.get("snooze_days") not in (None, ""):
        kw["snooze_days"] = int(body["snooze_days"])
    res = backlog.set_follow_up(s, p, item_id, at=str(body.get("at") or ""), **kw)
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/stale", dependencies=[Depends(require_operator)])
def mark_item_stale(item_id: str, body: dict[str, Any], request: Request,
                    ctx: dict[str, Any] = Depends(require_operator)):
    """Force an item's analysis to STALE (e.g. a related component changed)."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    res = backlog.mark_stale(s, p, item_id, reason=str(body.get("reason") or ""))
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/readiness", dependencies=[Depends(require_operator)])
def set_item_readiness(item_id: str, body: dict[str, Any], request: Request,
                       ctx: dict[str, Any] = Depends(require_operator)):
    """Record the computed readiness (ready + reasons) on an item."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    res = backlog.set_readiness(s, p, item_id, ready=bool(body.get("ready")), reasons=body.get("reasons"))
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/archive", dependencies=[Depends(require_operator)])
def archive_item(item_id: str, body: dict[str, Any], request: Request,
                 ctx: dict[str, Any] = Depends(require_operator)):
    """Non-destructive retire: move the item to the terminal ``archived`` status."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    res = backlog.archive(s, p, item_id, note=str(body.get("note") or "archived"))
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/delete", dependencies=[Depends(require_operator)])
def delete_item(item_id: str, body: dict[str, Any], request: Request,
                ctx: dict[str, Any] = Depends(require_operator)):
    """Remove an item (files + index) and re-sync its epic's children. Operator only; irreversible."""
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    res = backlog.delete(s, p, item_id)
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.get("/parked", dependencies=[Depends(authenticate)])
def parked(request: Request, days: int = 0, ctx: dict[str, Any] = Depends(authenticate)):
    """Parked items whose follow-up is due (weekly default). Read-only."""
    from core import backlog
    return from_request(request, backlog.parked_review(days=int(days or 0)), resource="backlog")


@router.post("/items/{item_id}/api-impact", dependencies=[Depends(require_operator)])
def set_item_api_impact(item_id: str, body: dict[str, Any], request: Request,
                        ctx: dict[str, Any] = Depends(require_operator)):
    """Record the API-first decision for an item (BI-PF-1066 E9; ADR-0007) via ``core.backlog.update``.

    Body: ``{scope, project, needs_api, reason, routes, expected_revision}``. Writes ``item.api_impact``
    (mandatory decision; routes required only when ``needs_api`` is true). Thin wrapper over the single writer.
    """
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    if "needs_api" not in body:
        raise ApiError("VALIDATION_FAILED", "needs_api (bool) is required")
    needs_api = bool(body.get("needs_api"))
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise ApiError("VALIDATION_FAILED", "reason is required (why the API is or is not needed)")
    routes = list(body.get("routes") or [])
    if needs_api and not routes:
        raise ApiError("VALIDATION_FAILED", "routes are required when needs_api is true")
    try:
        res = backlog.update(s, p, item_id,
                             api_impact={"needs_api": needs_api, "reason": reason, "routes": routes})
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


@router.post("/items/{item_id}/execution", dependencies=[Depends(require_operator)])
def set_item_execution(item_id: str, body: dict[str, Any], request: Request,
                       ctx: dict[str, Any] = Depends(require_operator)):
    """Record an item's execution fields (BI-PF-1423): ``usage`` (tokens/cost) + ``duration_seconds`` etc.

    Thin wrapper over ``core.backlog.set_execution`` (single writer). ``usage`` is a dict, e.g.
    ``{input_tokens, output_tokens, reasoning_tokens, cache_read, cache_write, cost_usd}``.
    """
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    allowed = ("usage", "duration_seconds", "started_at", "last_heartbeat_at", "worker_id", "status", "stage")
    fields = {k: body[k] for k in allowed if k in body}
    if not fields:
        raise ApiError("VALIDATION_FAILED", "no execution fields provided (allowed: " + ", ".join(allowed) + ")")
    try:
        res = backlog.set_execution(s, p, item_id, **fields)
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)


_EDITABLE_FIELDS = ("title", "body", "type", "label", "tag", "summary", "origin",
                    "value", "effort", "risk", "moscow")


@router.patch("/items/{item_id}", dependencies=[Depends(require_operator)])
def edit_item(item_id: str, body: dict[str, Any], request: Request,
              ctx: dict[str, Any] = Depends(require_operator)):
    """Edit an item's core fields (whitelisted) via ``core.backlog.update`` (single writer).

    Covers the generic edit/update path (title/body/type/label/tag/summary/origin/value/effort/risk/moscow).
    Optimistic-concurrency aware via ``expected_revision`` (-> 409).
    """
    from core import backlog
    s, p = _scope_project(request, str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    _guard_revision(backlog, s, p, item_id, body.get("expected_revision"))
    fields = {k: body[k] for k in _EDITABLE_FIELDS if k in body}
    if not fields:
        raise ApiError("VALIDATION_FAILED", "no editable fields provided (allowed: " + ", ".join(_EDITABLE_FIELDS) + ")")
    try:
        res = backlog.update(s, p, item_id, **fields)
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "backlog item not found")
    return from_request(request, res, resource="backlog", resource_id=item_id)

