"""Request context: request_id / correlation_id / tenant / actor (API-0.1 §2).

Middleware assigns and propagates the canonical ids on ``request.state`` and echoes them on responses
(``X-Request-Id`` / ``X-Correlation-Id``). Everything downstream reads them via :func:`ctx_of`.
"""

import uuid
from typing import Any, Dict

from fastapi import Request

_STATE_KEY = "pf_ctx"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:20]}"


def context_middleware(app) -> None:
    @app.middleware("http")
    async def _ctx(request: Request, call_next):
        req_id = (request.headers.get("X-Request-Id") or "").strip() or _new_id("req")
        corr_id = (request.headers.get("X-Correlation-Id") or "").strip() or req_id
        tenant = (request.headers.get("X-Tenant-Id") or "").strip()
        actor = (request.headers.get("X-Actor") or "").strip()
        api_version = (request.headers.get("X-Api-Version") or "").strip()
        ctx: Dict[str, Any] = {"request_id": req_id, "correlation_id": corr_id,
                               "tenant_id": tenant, "actor": actor, "api_version": api_version}
        setattr(request.state, _STATE_KEY, ctx)
        response = await call_next(request)
        response.headers["X-Request-Id"] = req_id
        response.headers["X-Correlation-Id"] = corr_id
        return response


def ctx_of(request: Request) -> Dict[str, Any]:
    return getattr(request.state, _STATE_KEY, {}) or {}


def current(request: Request) -> Dict[str, Any]:
    """Convenience: canonical ids for building envelopes."""
    c = ctx_of(request)
    return {"request_id": c.get("request_id", ""), "correlation_id": c.get("correlation_id", "")}
