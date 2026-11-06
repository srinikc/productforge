"""One scope normalizer/allowlist for backlog DB authority (items and IDs)."""
from __future__ import annotations

import os

DEFAULT_SCOPES = "product_forge,ProductForge-Dashboard"
LEGACY_FORGE_SCOPE = "factory"
VALID_MODES = ("off", "on", "dual", "shadow")


def normalize(scope: str | None) -> str:
    return "product_forge" if str(scope or "") in ("portfolio", "product_forge", LEGACY_FORGE_SCOPE) else "project"


def key(scope: str | None) -> str:
    """Allowlist key: preserves distinct scopes (unlike path normalization)."""
    return "product_forge" if str(scope or "") in ("portfolio", "product_forge", LEGACY_FORGE_SCOPE) else str(scope or "").strip().lower()


def allowed() -> set[str]:
    try:
        from core import env_flags
        value = env_flags.get("PF_BACKLOG_DB_SCOPES", DEFAULT_SCOPES)
    except Exception:
        value = os.environ.get("PF_BACKLOG_DB_SCOPES", DEFAULT_SCOPES)
    return {key(s.strip()) for s in str(value or "").split(",") if s.strip()}


def enabled(scope: str | None) -> bool:
    return key(scope) in allowed()


def mode() -> str:
    try:
        from core import env_flags
        value = env_flags.get("PF_BACKLOG_DB", "on")
    except Exception:
        value = os.environ.get("PF_BACKLOG_DB", "on")
    m = str(value or "on").strip().lower()
    if m not in VALID_MODES:
        raise RuntimeError(f"BACKLOG_DB_MODE_INVALID: {m}")
    return m
