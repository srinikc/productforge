"""Pipeline Supervisor API (portfolio coordinator): status / start / stop.

API-first control surface over ``core.portfolio`` (the supervisor is a SEPARATE service process that
launches ``scripts/run_pipeline.py`` per queued project). Reads are ``authenticate``; start/stop are
``require_operator``. No new store/engine.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/supervisor", dependencies=[Depends(authenticate)])
def supervisor_status(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import portfolio
    return from_request(request, portfolio.supervisor_status(), resource="portfolio", resource_id="supervisor")


@router.post("/supervisor/start", dependencies=[Depends(require_operator)])
def supervisor_start(body: Dict[str, Any], request: Request,
                     ctx: Dict[str, Any] = Depends(require_operator)):
    from core import portfolio
    res = portfolio.start_supervisor(int(body.get("max_concurrent") or 1))
    return from_request(request, res, resource="portfolio", resource_id="supervisor",
                        status="accepted" if res.get("ok") else "error")


@router.post("/supervisor/stop", dependencies=[Depends(require_operator)])
def supervisor_stop(request: Request, ctx: Dict[str, Any] = Depends(require_operator)):
    from core import portfolio
    return from_request(request, portfolio.stop_supervisor(), resource="portfolio", resource_id="supervisor")
