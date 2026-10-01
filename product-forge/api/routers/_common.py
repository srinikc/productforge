"""Shared helpers for API routers (project resolution / products dir).

Single place so every engineering router resolves a project and its directory the same way (API-3).
"""
import os

from ..errors import ApiError


def products_dir() -> str:
    from core import paths
    return paths.PRODUCTS_DIR


def project_dir(project: str) -> str:
    """Absolute ``products/<project>`` dir, or a canonical ApiError (fail-closed)."""
    p = str(project or "").strip()
    if not p or "/" in p or "\\" in p or p in (".", ".."):
        raise ApiError("VALIDATION_FAILED", "invalid project")
    d = os.path.join(products_dir(), p)
    if not os.path.isdir(d):
        raise ApiError("NOT_FOUND", "project not found")
    return d
