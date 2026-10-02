"""Engineering change log API (ENG-0/ENG-6 traceability): drift + corrective actions.

Read-only view of the append-only ``core.change_log`` store: what structural drift was detected and what we did
(regeneration / redesign / implementation / revert), with before/after and commit/revert refs.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from . import _common

router = APIRouter(prefix="/changes", tags=["changes"])


def _scope_project(scope: str, project: str):
    s = str(scope or "product_forge").strip()
    p = str(project or "").strip() or None
    s = s if s in ("product_forge", "project") else "product_forge"
    if s == "project" and not p:
        from ..errors import ApiError
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


@router.get("", dependencies=[Depends(authenticate)])
def list_changes(request: Request, scope: str = "product_forge", project: str = "",
                 kind: str = "", limit: int = 100,
                 ctx: dict[str, Any] = Depends(authenticate)):
    from core import change_log
    s, p = _scope_project(scope, project)
    if s == "project":
        _common.project_dir(p)  # fail-closed on unknown project
    rows = change_log.list_records(s, p, kind=kind)
    return from_request(request, rows[-max(1, int(limit)):], resource="change")


@router.get("/kinds", dependencies=[Depends(authenticate)])
def kinds(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import change_log
    return from_request(request, {"kinds": list(change_log.KINDS)}, resource="change")
