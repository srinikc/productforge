"""Pipeline / stages / tasks API (API-2): inspect pipeline definition, stage state, task/agent execution.

Read-model over the canonical ``pipeline-definition.json`` (engine: ``core.pipeline_executor``) and the
per-project ``pipeline-state.json`` (owner ``core.pipeline_executor``). No shadow state.
"""

import json
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(tags=["pipeline"])


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


def _definition() -> Dict[str, Any]:
    from core import paths
    try:
        with open(paths.PIPELINE_DEFINITION, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


def _stage_defs(d: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize the two possible shapes: dict keyed by id, or list of defs."""
    raw = d.get("stages") or {}
    if isinstance(raw, dict):
        out = []
        for sid, sdef in raw.items():
            item = dict(sdef or {})
            item.setdefault("id", sid)
            out.append(item)
        return out
    return list(raw)


def _state(project_dir: str) -> Dict[str, Any]:
    p = os.path.join(project_dir, "pipeline-state.json")
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


@router.get("/pipeline", dependencies=[Depends(authenticate)])
def pipeline(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    d = _definition()
    stages = [{"id": s.get("id"), "name": s.get("name"), "depends_on": s.get("depends_on") or []}
              for s in _stage_defs(d)]
    return from_request(request, {"version": d.get("version"), "stages": stages,
                                  "count": len(stages)}, resource="pipeline")


@router.get("/pipeline/stages", dependencies=[Depends(authenticate)])
def stages(request: Request, project: str = "", ctx: Dict[str, Any] = Depends(authenticate)):
    d = _definition()
    st = _state(_project_dir(project)) if project else {}
    out: List[Dict[str, Any]] = []
    for s in _stage_defs(d):
        sid = s.get("id")
        out.append({"id": sid, "name": s.get("name"),
                    "status": (st.get("stages") or {}).get(sid), "depends_on": s.get("depends_on") or []})
    return from_request(request, out, resource="stage")


@router.get("/pipeline/stages/{stage_id}", dependencies=[Depends(authenticate)])
def stage(stage_id: str, request: Request, project: str,
          ctx: Dict[str, Any] = Depends(authenticate)):
    d = _definition()
    sdef = next((s for s in _stage_defs(d) if s.get("id") == stage_id), None)
    if not sdef:
        raise ApiError("NOT_FOUND", "stage not found")
    st = _state(_project_dir(project))
    return from_request(request, {"id": stage_id, "name": sdef.get("name"),
                                  "status": (st.get("stages") or {}).get(stage_id),
                                  "ideal_flow": sdef.get("ideal_flow") or [],
                                  "sub_agents": sdef.get("sub_agents") or {}},
                        resource="stage", resource_id=str(stage_id))


@router.get("/tasks", dependencies=[Depends(authenticate)])
def tasks(request: Request, project: str = "", stage_id: str = "",
          ctx: Dict[str, Any] = Depends(authenticate)):
    d = _definition()
    st = _state(_project_dir(project)) if project else {}
    out: List[Dict[str, Any]] = []
    for s in _stage_defs(d):
        if stage_id and s.get("id") != stage_id:
            continue
        for agent in (s.get("ideal_flow") or []):
            out.append({"stage_id": s.get("id"), "task_id": f"{s.get('id')}:{agent}",
                        "agent": agent, "status": (st.get("agents") or {}).get(f"{s.get('id')}:{agent}")})
    return from_request(request, out, resource="task")
