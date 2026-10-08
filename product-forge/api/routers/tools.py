"""Tools API (BI-PF-0439) - API-first settings surface for PF's tool layer.

GET/PUT the web_search configuration. The secret key is accepted on PUT but NEVER returned (only ``has_key``).
Operator role required to change settings; env still overrides the store (``PF_WEB_SEARCH_*``).
"""
from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/tools", tags=["tools"])

_BACKENDS = {"none", "whoogle", "searxng", "duckduckgo_html", "brave", "tavily"}


def _view() -> dict:
    from core import tool_settings
    e = tool_settings.effective()
    return {"backend": e["backend"], "url": e["url"], "has_key": e["has_key"], "source": e["source"]}


@router.get("/web-search", dependencies=[Depends(authenticate)])
def get_web_search(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    return from_request(request, _view(), resource="tools")


@router.put("/web-search", dependencies=[Depends(require_operator)])
def put_web_search(body: dict[str, Any], request: Request,
                   ctx: dict[str, Any] = Depends(require_operator)):
    from core import tool_settings
    backend = str(body.get("backend") or "").strip().lower()
    url = str(body.get("url") or "").strip()
    if backend and backend not in _BACKENDS:
        raise ApiError("VALIDATION_FAILED", f"backend must be one of {sorted(_BACKENDS)}",
                       details={"backend": backend})
    api_key = body.get("api_key")  # None -> leave unchanged; "" -> clear
    tool_settings.save(backend=backend, url=url, api_key=(None if api_key is None else str(api_key)))
    return from_request(request, _view(), resource="tools")
