"""Success envelope helper (API-0.1 §3).

Every JSON success response from the ``api`` surface goes through :func:`ok` so the shape is consistent and
carries the canonical ids.
"""

from typing import Any, Dict, List, Optional


def ok(data: Any = None, *, request_id: str = "", correlation_id: str = "",
       resource: str = "", resource_id: str = "", links: Optional[Dict[str, Any]] = None,
       warnings: Optional[List[str]] = None, status: str = "ok") -> Dict[str, Any]:
    """Build the canonical success envelope."""
    return {"request_id": request_id, "correlation_id": correlation_id, "status": status,
            "resource": resource, "resource_id": resource_id, "data": data,
            "links": dict(links or {}), "warnings": list(warnings or []), "error": None}


def from_request(request, data: Any = None, *, resource: str = "", resource_id: str = "",
                 links: Optional[Dict[str, Any]] = None, warnings: Optional[List[str]] = None,
                 status: str = "ok") -> Dict[str, Any]:
    from .context import current
    c = current(request)
    return ok(data, request_id=c["request_id"], correlation_id=c["correlation_id"],
              resource=resource, resource_id=resource_id, links=links, warnings=warnings, status=status)
