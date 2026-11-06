"""One scope normalizer/allowlist for backlog DB authority (items and IDs)."""
from __future__ import annotations

import os

DEFAULT_SCOPES = "product_forge,ProductForge-Dashboard"
_LEGACY_FORGE_SCOPE = "factory"


def normalize(scope: str | None) -> str:
    return "product_forge" if str(scope or "") in ("portfolio", "product_forge", _LEGACY_FORGE_SCOPE) else "project"


def allowed() -> set[str]:
    try:
        from core import env_flags
        value = env_flags.get("PF_BACKLOG_DB_SCOPES", DEFAULT_SCOPES)
    except Exception:
        value = os.environ.get("PF_BACKLOG_DB_SCOPES", DEFAULT_SCOPES)
    return {normalize(s.strip()) for s in str(value or "").split(",") if s.strip()}


def enabled(scope: str | None) -> bool:
    return normalize(scope) in allowed()
