"""Product Forge canonical API package (API-first control plane).

See ``api/app.py`` for the app and ``docs/API-0.1-CONTRACT-RECONCILIATION.md`` for the contract.
"""

from .app import app  # noqa: F401

__all__ = ["app"]
