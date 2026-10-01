"""Defect / RCCA API (API-3): canonical findings registry with root-cause analysis.

Maps to ``core.issues`` (the canonical single-writer ``IS-*`` store with RCCA + backlog linkage).
Reads are authenticated; mutations are operator-gated. No shadow store.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
from ..pagination import paginate

router = APIRouter(prefix="/issues", tags=["issues"])

_KINDS = ("issue", "bug", "risk", "gap")
_PRIORITIES = ("P0", "P1", "P2", "P3")


def _scope_project(scope: str, project: str):
    s = str(scope or "product_forge").strip()
    p = str(project or "").strip() or None
    if s not in ("product_forge", "project"):
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project",
                       details={"scope": s})
    if s == "project" and not p:
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


@router.get("", dependencies=[Depends(authenticate)])
def list_issues(request: Request, scope: str = "product_forge", project: str = "",
                status: str = "", priority: str = "", module: str = "",
                limit: int = 50, cursor: str = "",
                ctx: Dict[str, Any] = Depends(authenticate)):
    from core import issues
    s, p = _scope_project(scope, project)
    items: List[Dict[str, Any]] = issues.list_open(s, p, priority=priority, module=module)
    items += issues.list_closed(s, p)
    if status:
        items = [it for it in items if it.get("status") == status]
    page, links = paginate(items, limit=limit, cursor=cursor)
    return from_request(request, page, resource="issue", links=links)


@router.get("/stats", dependencies=[Depends(authenticate)])
def stats(request: Request, scope: str = "product_forge", project: str = "",
          ctx: Dict[str, Any] = Depends(authenticate)):
    from core import issues
    s, p = _scope_project(scope, project)
    return from_request(request, issues.stats(s, p), resource="issue")


@router.get("/{iid}", dependencies=[Depends(authenticate)])
def get_issue(iid: str, request: Request, scope: str = "product_forge", project: str = "",
              ctx: Dict[str, Any] = Depends(authenticate)):
    from core import issues
    s, p = _scope_project(scope, project)
    it = issues.get(s, p, iid)
    if not it:
        raise ApiError("NOT_FOUND", "issue not found")
    return from_request(request, it, resource="issue", resource_id=iid)


@router.post("", dependencies=[Depends(require_operator)])
def create_issue(body: Dict[str, Any], request: Request,
                 ctx: Dict[str, Any] = Depends(require_operator)):
    from core import issues
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    title = str(body.get("title") or "").strip()
    if not title:
        raise ApiError("VALIDATION_FAILED", "title required")
    kind = str(body.get("kind") or "issue").strip()
    if kind not in _KINDS:
        raise ApiError("VALIDATION_FAILED", "invalid kind", details={"allowed": list(_KINDS)})
    priority = str(body.get("priority") or "P2").strip().upper()
    if priority not in _PRIORITIES:
        raise ApiError("VALIDATION_FAILED", "invalid priority", details={"allowed": list(_PRIORITIES)})
    rcca = body.get("rcca")
    it = issues.raise_issue(s, p, title, body=str(body.get("body") or ""), kind=kind,
                            priority=priority, severity=str(body.get("severity") or ""),
                            module=str(body.get("module") or ""), source="api",
                            rcca=rcca if isinstance(rcca, dict) else None,
                            backlog_ref=str(body.get("backlog_ref") or ""),
                            source_ref=str(body.get("source_ref") or ""))
    return from_request(request, it, resource="issue", resource_id=str(it.get("id") or ""))


@router.post("/{iid}/rcca", dependencies=[Depends(require_operator)])
def set_rcca(iid: str, body: Dict[str, Any], request: Request,
             ctx: Dict[str, Any] = Depends(require_operator)):
    from core import issues
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = issues.set_rcca(s, p, iid, root_cause=str(body.get("root_cause") or ""),
                          corrective=str(body.get("corrective") or ""),
                          preventive=str(body.get("preventive") or ""),
                          fixed_where=str(body.get("fixed_where") or ""),
                          generalized=bool(body.get("generalized") or False),
                          guideline_ref=str(body.get("guideline_ref") or ""),
                          product_ref=str(body.get("product_ref") or ""))
    if res is None:
        raise ApiError("NOT_FOUND", "issue not found")
    return from_request(request, res, resource="issue", resource_id=iid)


@router.post("/{iid}/status", dependencies=[Depends(require_operator)])
def set_status(iid: str, body: Dict[str, Any], request: Request,
               ctx: Dict[str, Any] = Depends(require_operator)):
    from core import issues
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    status = str(body.get("status") or "").strip()
    if not status:
        raise ApiError("VALIDATION_FAILED", "status required")
    try:
        res = issues.set_status(s, p, iid, status, note=str(body.get("note") or ""),
                                force=bool(body.get("force") or False))
    except Exception as e:
        raise ApiError("CONFLICT", f"status change refused: {type(e).__name__}")
    if res is None:
        raise ApiError("NOT_FOUND", "issue not found")
    return from_request(request, res, resource="issue", resource_id=iid)
