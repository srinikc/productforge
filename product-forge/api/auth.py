"""Authentication / authorization boundary (API-0.1 §7).

Fail-closed by default: a request is authenticated only with a valid Bearer token, unless the explicit dev
flag ``API_ALLOW_ANON=1`` is set (development only). Roles come from ``X-Roles`` (comma-separated) or the
token; ``operator`` is the platform-admin role. Tenant routes require a matching ``X-Tenant-Id``.

This reimplements the legacy ``auth``/``operator_guard``/``tenant_guard`` concepts cleanly for the ``api``
surface *without* editing the legacy dashboard app.
"""

import os
import secrets
from typing import List

from fastapi import Depends, Header, Request

from .context import ctx_of
from .errors import ApiError

try:
    from core.paths import ROOT as _ROOT
except Exception:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# BI-PF-1256: local dev credential, shared with the worker via WorkerGrid `token_file`. Dev-only (PF_DEV=1);
# the API falls back to this file ONLY when PF_DEV=1, so production stays fail-closed.
TOKEN_PATH = os.path.join(str(_ROOT), "data", "local", "dev-api-token")


def is_dev() -> bool:
    return str(os.environ.get("PF_DEV", "")).strip().lower() in ("1", "true", "yes")


def dev_token() -> str:
    try:
        with open(TOKEN_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def ensure_dev_token() -> str:
    t = dev_token()
    if t:
        return t
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    t = secrets.token_urlsafe(32)
    tmp = TOKEN_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(t + "\n")
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    os.replace(tmp, TOKEN_PATH)
    return t


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
    # BI-PF-1325: PF_API_TOKEN is canonical; API_TOKEN is a deprecated back-compat alias.
    # The legacy DASHBOARD_API_TOKEN alias was removed (no consumers; the dashboard is legacy/frozen).
    tok = _flag("PF_API_TOKEN", "") or _flag("API_TOKEN", "")
    if not tok and is_dev():
        # BI-PF-1256: dev-only shared local token so local dev needs no manual env (never in prod).
        tok = ensure_dev_token()
    return tok


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
        raise ApiError("UNAUTHENTICATED", "no API token configured; set PF_API_TOKEN or enable API_ALLOW_ANON for dev")
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


def require_worker(request: Request, authorization: str = Header(default=""),
                   x_roles: str = Header(default="")) -> dict:
    """BI-PF-0419: the assignment-lifecycle boundary. A worker (``worker`` role) or an operator may call it."""
    ctx = authenticate(request, authorization, x_roles)
    roles = ctx.get("roles") or []
    if not _anon_ok() and not ({"worker", "operator"} & set(roles)):
        raise ApiError("FORBIDDEN", "worker role required")
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
