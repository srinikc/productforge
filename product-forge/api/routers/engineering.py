"""Engineering architecture API (ENG-0): the requirement -> deploy flow over the API-1..API-3 contracts.

Read-model over ``core.engineering_flow`` (``config/engineering-flow.json``): each step with its canonical
owner file, the ``/api/v1`` route that exposes it, and its status (exists | partial | planned). No engine.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
from ..pagination import paginate

router = APIRouter(prefix="/engineering", tags=["engineering"])


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
def engineering(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    return from_request(request, engineering_flow.load(), resource="engineering")


@router.get("/stages", dependencies=[Depends(authenticate)])
def stages(request: Request, phase: str = "", status: str = "",
           ctx: Dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    steps: List[Dict[str, Any]] = engineering_flow.flow()
    if phase:
        steps = [s for s in steps if str(s.get("phase")) == phase]
    if status:
        steps = [s for s in steps if str(s.get("status")) == status]
    return from_request(request, steps, resource="engineering")


@router.get("/stages/{stage_id}", dependencies=[Depends(authenticate)])
def stage(stage_id: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    s = engineering_flow.stage(stage_id)
    if not s:
        raise ApiError("NOT_FOUND", "engineering stage not found")
    return from_request(request, s, resource="engineering", resource_id=stage_id)


@router.get("/coverage", dependencies=[Depends(authenticate)])
def coverage(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    return from_request(request, engineering_flow.coverage(), resource="engineering")


# ── ENG-1: engineering task contracts ───────────────────────────────────────

@router.get("/tasks", dependencies=[Depends(authenticate)])
def list_tasks(request: Request, scope: str = "product_forge", project: str = "",
               status: str = "", limit: int = 50, cursor: str = "",
               ctx: Dict[str, Any] = Depends(authenticate)):
    from core import task_contract
    s, p = _scope_project(scope, project)
    items = task_contract.list_tasks(s, p, status=status)
    page, links = paginate(items, limit=limit, cursor=cursor)
    return from_request(request, page, resource="task_contract", links=links)


@router.get("/tasks/{task_id}", dependencies=[Depends(authenticate)])
def get_task(task_id: str, request: Request, scope: str = "product_forge", project: str = "",
             ctx: Dict[str, Any] = Depends(authenticate)):
    from core import task_contract
    s, p = _scope_project(scope, project)
    it = task_contract.get(s, p, task_id)
    if not it:
        raise ApiError("NOT_FOUND", "task contract not found")
    return from_request(request, it, resource="task_contract", resource_id=task_id)


@router.post("/tasks", dependencies=[Depends(require_operator)])
def create_task(body: Dict[str, Any], request: Request,
                ctx: Dict[str, Any] = Depends(require_operator)):
    from core import task_contract
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    try:
        it = task_contract.create(s, p, body)
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e))
    return from_request(request, it, resource="task_contract", resource_id=str(it.get("task_id") or ""))


@router.post("/tasks/{task_id}/status", dependencies=[Depends(require_operator)])
def set_task_status(task_id: str, body: Dict[str, Any], request: Request,
                    ctx: Dict[str, Any] = Depends(require_operator)):
    from core import task_contract
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    try:
        res = task_contract.set_status(s, p, task_id, str(body.get("status") or ""),
                                       note=str(body.get("note") or ""))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e))
    if res is None:
        raise ApiError("NOT_FOUND", "task contract not found")
    return from_request(request, res, resource="task_contract", resource_id=task_id)
