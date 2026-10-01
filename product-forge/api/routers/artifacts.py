"""Artifacts API (API-2): inspect produced artifacts (canonical artifact store + run manifest)."""

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _products_dir() -> str:
    from core import paths
    return paths.PRODUCTS_DIR


def _project_dir(project: str) -> str:
    p = str(project or "").strip()
    if not p or "/" in p or "\\" in p:
        raise ApiError("VALIDATION_FAILED", "invalid project")
    d = os.path.join(_products_dir(), p)
    if not os.path.isdir(d):
        raise ApiError("NOT_FOUND", "project not found")
    return d


@router.get("", dependencies=[Depends(authenticate)])
def list_artifacts(request: Request, project: str, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import artifact_store
    d = _project_dir(project)
    try:
        summary = artifact_store.get_artifact_summary(d)
    except Exception:
        summary = {"artifacts": []}
    return from_request(request, summary, resource="artifact")


@router.get("/{stage_id}/{agent}", dependencies=[Depends(authenticate)])
def get_artifact(stage_id: str, agent: str, request: Request, project: str,
                 ctx: Dict[str, Any] = Depends(authenticate)):
    from core import artifact_store
    d = _project_dir(project)
    proj = artifact_store.scan_project_artifacts(d)
    stage = proj.stages.get(stage_id)
    art = next((a for a in (stage.artifacts if stage else []) if a.agent == agent), None)
    if art is None:
        raise ApiError("NOT_FOUND", "artifact not found")
    content = artifact_store.get_artifact_content(art.path)
    if content is None:
        raise ApiError("NOT_FOUND", "artifact not found")
    return from_request(request, {"stage_id": stage_id, "agent": agent, "content": content},
                        resource="artifact", resource_id=f"{stage_id}/{agent}")
