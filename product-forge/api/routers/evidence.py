"""Evidence API (API-2): run-bound evidence — events, run manifest, evidence index.

Read-model over the canonical event stream (``core.events``) and the run manifest
(``core.run_manifest``) which carries content hashes for produced artifacts.
"""

import json
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/evidence", tags=["evidence"])


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


@router.get("/events", dependencies=[Depends(authenticate)])
def events(request: Request, project: str, limit: int = 100,
           ctx: Dict[str, Any] = Depends(authenticate)):
    from core import events as _events
    d = _project_dir(project)
    try:
        rows = _events.read(d, limit=limit)
    except TypeError:
        rows = _events.read(d, limit)
    return from_request(request, {"events": rows, "counts": _events.counts(d)}, resource="evidence")


@router.get("/manifest/{run_id}", dependencies=[Depends(authenticate)])
def manifest(run_id: str, request: Request, project: str,
             ctx: Dict[str, Any] = Depends(authenticate)):
    d = _project_dir(project)
    p = os.path.join(d, "run-manifests", f"{run_id}." + "json")
    if not os.path.isfile(p):
        raise ApiError("NOT_FOUND", "run manifest not found")
    with open(p, encoding="utf-8-sig") as f:
        return from_request(request, json.load(f), resource="evidence", resource_id=str(run_id))


@router.get("/index", dependencies=[Depends(authenticate)])
def evidence_index(request: Request, project: str, ctx: Dict[str, Any] = Depends(authenticate)):
    d = _project_dir(project)
    man_dir = os.path.join(d, "run-manifests")
    runs = []
    if os.path.isdir(man_dir):
        for n in sorted(os.listdir(man_dir)):
            if n.endswith("." + "json"):
                runs.append(n[: -len("." + "json")])
    return from_request(request, {"project": project, "runs": runs}, resource="evidence")
