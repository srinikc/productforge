"""Git/VCS API (API-3): read-only view of the canonical project repository.

Maps to ``core.vcs.VCSManager`` (the ONE git owner, uses the ``git`` CLI in the project dir). No shadow store.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
from . import _common

router = APIRouter(prefix="/vcs", tags=["vcs"])


def _manager(project: str):
    from core.vcs import VCSManager
    return VCSManager(_common.project_dir(project))


@router.get("", dependencies=[Depends(authenticate)])
def vcs(project: str, request: Request, limit: int = 50,
        ctx: Dict[str, Any] = Depends(authenticate)):
    m = _manager(project)
    out = m.history(limit)
    if out.get("is_repo"):
        try:
            out["status"] = m.status()
        except Exception:
            out["status"] = {}
    return from_request(request, out, resource="vcs", resource_id=project)


@router.get("/status", dependencies=[Depends(authenticate)])
def status(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    return from_request(request, _manager(project).status(),
                        resource="vcs", resource_id=project)


@router.get("/branches", dependencies=[Depends(authenticate)])
def branches(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    return from_request(request, _manager(project).branches(),
                        resource="vcs", resource_id=project)


@router.get("/commits", dependencies=[Depends(authenticate)])
def commits(project: str, request: Request, limit: int = 50,
            ctx: Dict[str, Any] = Depends(authenticate)):
    return from_request(request, _manager(project).checkins(limit),
                        resource="vcs", resource_id=project)


# ── ENG-3: branch naming + worktree isolation ───────────────────────────────

@router.get("/branch-name", dependencies=[Depends(authenticate)])
def branch_name(request: Request, task_id: str = "", area: str = "", run_id: str = "",
                ctx: Dict[str, Any] = Depends(authenticate)):
    from core.vcs import VCSManager
    return from_request(request, {
        "feature": VCSManager.feature_branch_name(area, task_id),
        "validation": VCSManager.validation_branch_name(run_id) if run_id else "",
    }, resource="vcs", resource_id=task_id)


@router.get("/worktrees", dependencies=[Depends(authenticate)])
def worktrees(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    m = _manager(project)
    return from_request(request, {"root": m.worktree_root(), "worktrees": m.list_worktrees()},
                        resource="vcs", resource_id=project)


@router.post("/worktrees", dependencies=[Depends(require_operator)])
def add_worktree(body: Dict[str, Any], request: Request,
                 ctx: Dict[str, Any] = Depends(require_operator)):
    project = str(body.get("project") or "")
    name = str(body.get("name") or body.get("task_id") or "")
    if not name:
        raise ApiError("VALIDATION_FAILED", "name or task_id required")
    m = _manager(project)
    res = m.add_worktree(name, branch=str(body.get("branch") or ""), base=str(body.get("base") or ""))
    if not res.get("ok"):
        raise ApiError("CONFLICT", res.get("error") or "could not create worktree")
    return from_request(request, res, resource="vcs", resource_id=project)


@router.post("/worktrees/{name}/remove", dependencies=[Depends(require_operator)])
def remove_worktree(name: str, body: Dict[str, Any], request: Request,
                    ctx: Dict[str, Any] = Depends(require_operator)):
    project = str(body.get("project") or "")
    res = _manager(project).remove_worktree(name)
    if not res.get("ok"):
        raise ApiError("NOT_FOUND", res.get("error") or "worktree not found")
    return from_request(request, res, resource="vcs", resource_id=project)
