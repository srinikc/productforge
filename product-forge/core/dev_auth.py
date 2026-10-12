"""Local dev auth credential (BI-PF-1256).

A single gitignored token shared by the PF API server and the worker client so local dev needs **no manual
env**: the API reads it (only in dev) and the worker reads it (via WorkerGrid ``token_file``).

Dev-only: gated by ``PF_DEV=1``. Production stays fail-closed (no file fallback).
"""
import os
import secrets

from core.paths import ROOT

TOKEN_PATH = os.path.join(str(ROOT), "data", "local", "dev-api-token")


def is_dev() -> bool:
    """True only when the explicit dev flag is set (never implied)."""
    return str(os.environ.get("PF_DEV", "")).strip().lower() in ("1", "true", "yes")


def dev_token() -> str:
    """The stored dev token, or '' when absent."""
    try:
        with open(TOKEN_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def ensure_dev_token() -> str:
    """Return the dev token, generating + persisting it (0600) on first use."""
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
