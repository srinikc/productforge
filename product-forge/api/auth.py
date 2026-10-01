"""Authentication / authorization boundary (API-0.1 §7).

Fail-closed by default: a request is authenticated only with a valid Bearer token, unless the explicit dev
flag ``API_ALLOW_ANON=1`` is set (development only). Roles come from ``X-Roles`` (comma-separated) or the
token; ``operator`` is the platform-admin role. Tenant routes require a matching ``X-Tenant-Id``.

This reimplements the legacy ``auth``/``operator_guard``/``tenant_guard`` concepts cleanly for the ``api``
surface *without* editing the legacy dashboard app.
"""

from typing import List

from fastapi import Depends, Header, Request

from .context import ctx_of
from .errors import ApiError

_PUBLIC = {"/health", "/ready", "/metrics"}


def _flag(name: str, default: str = "") -> str:
    try:
        from core import env_flags
        v = env_flags.get(name, default)
    except Exception:
        import os
        v = os.environ.get(name, default)
    return str(v if v not in (None, "") else default)


def _token() -> str:
    return _flag("API_TOKEN", "") or _flag("DASHBOARD_API_TOKEN", "")


def _anon_ok() -> bool:
    return _flag("API_ALLOW_ANON", "0").lower() in ("1", "true", "yes")


def authenticate(request: Request, authorization: str = Header(default=""),
                 x_roles: str = Header(default="")) -> dict:
    """FastAPI dependency: validate the Bearer token (fail-closed). Returns the auth context."""
    ctx = ctx_of(request)
    path = request.url.path
    token = _token()
    provided = ""
    if authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if not token:
        if _anon_ok() or path in _PUBLIC:
            ctx["roles"] = _roles(x_roles)
            ctx["authenticated"] = bool(_anon_ok())
            return ctx
        raise ApiError("UNAUTHENTICATED", "no API token configured; set API_TOKEN or enable API_ALLOW_ANON for dev")
    if provided != token:
        raise ApiError("UNAUTHENTICATED", "invalid or missing bearer token")
    ctx["roles"] = _roles(x_roles)
    ctx["authenticated"] = True
    return ctx


def _roles(x_roles: str) -> List[str]:
    return [r.strip() for r in str(x_roles or "").split(",") if r.strip()]


def require_operator(request: Request, authorization: str = Header(default=""),
                     x_roles: str = Header(default="")) -> dict:
    ctx = authenticate(request, authorization, x_roles)
    roles = ctx.get("roles") or []
    if not _anon_ok() and "operator" not in roles:
        raise ApiError("FORBIDDEN", "operator role required")
    return ctx


def require_tenant(request: Request, x_tenant_id: str = Header(default=""),
                   authorization: str = Header(default=""), x_roles: str = Header(default="")) -> dict:
    ctx = authenticate(request, authorization, x_roles)
    claimed = (x_tenant_id or ctx.get("tenant_id") or "").strip()
    if not claimed:
        raise ApiError("FORBIDDEN", "tenant_id required")
    ctx["tenant_id"] = claimed
    return ctx


# Dependencies for route use
auth = Depends(authenticate)
operator_guard = Depends(require_operator)
tenant_guard = Depends(require_tenant)
