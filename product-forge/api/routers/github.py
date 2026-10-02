"""GitHub / PR / CI API (ENG-5): PR orchestration + run-bound PR evidence + CI status.

Maps to ``core.github`` (push-ready -> PR -> CI), which aggregates evidence from canonical stores and uses the
optional ``gh`` adapter. No shadow store; PR records are append-only evidence.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
from . import _common

router = APIRouter(prefix="/github", tags=["github"])


def _scope_project(scope: str, project: str):
    s = str(scope or "product_forge").strip()
    p = str(project or "").strip() or None
    if s not in ("product_forge", "project"):
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project")
    if s == "project" and not p:
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


def _pdir(scope: str, project: str) -> str:
    if scope == "product_forge":
        from core.paths import ROOT
        return ROOT
    return _common.project_dir(project)


@router.get("", dependencies=[Depends(authenticate)])
def overview(request: Request, scope: str = "product_forge", project: str = "",
             ctx: Dict[str, Any] = Depends(authenticate)):
    from core import github
    s, p = _scope_project(scope, project)
    _pdir(s, p)  # fail-closed on an unknown project
    return from_request(request, {"available": github.available(), "prs": github.list_prs(s, p)},
                        resource="github")


@router.get("/evidence", dependencies=[Depends(authenticate)])
def evidence(request: Request, scope: str = "product_forge", project: str = "", run_id: str = "",
             task_id: str = "", base_sha: str = "", head_sha: str = "", backlog_ref: str = "",
             ctx: Dict[str, Any] = Depends(authenticate)):
    from core import github
    s, p = _scope_project(scope, project)
    return from_request(request, github.build_evidence(p or s, _pdir(s, p), run_id=run_id, task_id=task_id,
                                                       base_sha=base_sha, head_sha=head_sha,
                                                       backlog_ref=backlog_ref),
                        resource="github", resource_id=task_id)


@router.post("/pr", dependencies=[Depends(require_operator)])
def create_pr(body: Dict[str, Any], request: Request,
              ctx: Dict[str, Any] = Depends(require_operator)):
    from core import github
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    pdir = _pdir(s, p)
    res = github.create_pr(p or s, pdir, title=str(body.get("title") or ""), body=str(body.get("body") or ""),
                           base=str(body.get("base") or ""), head=str(body.get("head") or ""),
                           run_id=str(body.get("run_id") or ""), task_id=str(body.get("task_id") or ""),
                           backlog_ref=str(body.get("backlog_ref") or ""), scope=s)
    if not res.get("ok"):
        raise ApiError("CONFLICT", res.get("error") or "could not create PR")
    return from_request(request, res, resource="github",
                        resource_id=str((res.get("pr") or {}).get("number") or ""))


@router.get("/pr/{number}", dependencies=[Depends(authenticate)])
def get_pr(number: str, request: Request, scope: str = "product_forge", project: str = "",
           ctx: Dict[str, Any] = Depends(authenticate)):
    from core import github
    s, p = _scope_project(scope, project)
    pr = github.get_pr(s, p, number)
    if not pr:
        raise ApiError("NOT_FOUND", "PR record not found")
    return from_request(request, pr, resource="github", resource_id=number)


@router.get("/pr/{number}/ci", dependencies=[Depends(authenticate)])
def ci(number: str, request: Request, scope: str = "product_forge", project: str = "",
       ctx: Dict[str, Any] = Depends(authenticate)):
    from core import github
    s, p = _scope_project(scope, project)
    return from_request(request, github.ci_status(_pdir(s, p), number),
                        resource="github", resource_id=number)
