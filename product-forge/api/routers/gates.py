"""Gates API (API-3): PR merge gate, repo quality gate, QA Go/No-Go.

Read-models over ``core.pr_gate`` (checklist + can-merge), ``core.run_quality_gate`` (compileall/wired-audit
record) and ``core.qa_report`` (persisted Go/No-Go). No shadow store.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from . import _common

router = APIRouter(prefix="/gates", tags=["gates"])


@router.get("/pr", dependencies=[Depends(authenticate)])
def pr(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import pr_gate
    d = _common.project_dir(project)
    return from_request(request, pr_gate.evaluate(project, d),
                        resource="gate", resource_id=project)


@router.get("/pr/merge", dependencies=[Depends(authenticate)])
def pr_merge(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import pr_gate
    d = _common.project_dir(project)
    return from_request(request, pr_gate.can_merge(project, d),
                        resource="gate", resource_id=project)


@router.get("/quality", dependencies=[Depends(authenticate)])
def quality(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import run_quality_gate
    d = _common.project_dir(project)
    return from_request(request, run_quality_gate.latest(d) or {},
                        resource="gate", resource_id=project)


@router.get("/go-no-go", dependencies=[Depends(authenticate)])
def go_no_go(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import qa_report
    _common.project_dir(project)
    return from_request(request, qa_report.load(project),
                        resource="gate", resource_id=project)
