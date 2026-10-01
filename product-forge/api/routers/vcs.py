"""Git/VCS API (API-3): read-only view of the canonical project repository.

Maps to ``core.vcs.VCSManager`` (the ONE git owner, uses the ``git`` CLI in the project dir). No shadow store.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
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
