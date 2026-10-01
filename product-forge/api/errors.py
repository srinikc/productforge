"""Canonical API error model + helpers (API-0.1 §4).

Single definition of the error contract for the ``api`` surface: a stable ``ApiError`` type, the canonical
error payload, and the FastAPI exception handlers that render it. Fail-closed: unknown failures never leak
stack traces or secrets.
"""

import re
from typing import Any, Dict, Optional

_MAP = {
    "VALIDATION_FAILED": (400, "client", False),
    "API_VERSION_UNSUPPORTED": (400, "client", False),
    "BAD_REQUEST": (400, "client", False),
    "UNAUTHENTICATED": (401, "auth", False),
    "FORBIDDEN": (403, "auth", False),
    "NOT_FOUND": (404, "client", False),
    "METHOD_NOT_ALLOWED": (405, "client", False),
    "CONFLICT": (409, "conflict", False),
    "IDEMPOTENCY_CONFLICT": (409, "conflict", True),
    "UNPROCESSABLE": (422, "client", False),
    "RATE_LIMITED": (429, "rate_limit", True),
    "INTERNAL": (500, "server", False),
    "DEPENDENCY_UNAVAILABLE": (503, "dependency", True),
}

_SECRET = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer|authorization)\s*[:=]?\s*\S+")


def _redact(s: str) -> str:
    return _SECRET.sub(r"\1=[REDACTED]", str(s or ""))


class ApiError(Exception):
    """A canonical, safe API error.

    ``code`` is a stable SCREAMING_SNAKE machine code; ``message`` is safe for clients; ``details`` carries
    structured context (field errors etc.). HTTP status/category/retryable are derived from the code map.
    """

    def __init__(self, code: str, message: str = "", *, status: Optional[int] = None,
                 category: Optional[str] = None, retryable: Optional[bool] = None,
                 details: Optional[Dict[str, Any]] = None):
        self.code = str(code or "INTERNAL").upper()
        self.message = _redact(message) or self.code
        m = _MAP.get(self.code, (500, "server", False))
        self.status = int(status if status is not None else m[0])
        self.category = str(category if category is not None else m[1])
        self.retryable = bool(retryable if retryable is not None else m[2])
        self.details = dict(details or {})
        super().__init__(self.message)

    def payload(self, request_id: str = "", correlation_id: str = "") -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "category": self.category,
                "retryable": self.retryable, "details": self.details,
                "request_id": request_id, "correlation_id": correlation_id}


def error_response(exc: ApiError, request_id: str = "", correlation_id: str = "") -> Dict[str, Any]:
    """Render the canonical failure envelope (API-0.1 §3/§4)."""
    return {"request_id": request_id, "correlation_id": correlation_id,
            "status": "error", "resource": "", "resource_id": "", "data": None,
            "links": {}, "warnings": [], "error": exc.payload(request_id, correlation_id)}


def install_handlers(app) -> None:
    """Register FastAPI exception handlers so every error uses the canonical envelope."""
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from .context import ctx_of

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        from fastapi.responses import JSONResponse
        c = ctx_of(request)
        return JSONResponse(status_code=exc.status,
                            content=error_response(exc, c.get("request_id", ""), c.get("correlation_id", "")))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        from fastapi.responses import JSONResponse
        c = ctx_of(request)
        err = ApiError("VALIDATION_FAILED", "request validation failed",
                       details={"errors": exc.errors()})
        return JSONResponse(status_code=err.status, content=error_response(err, c.get("request_id", ""),
                                                                          c.get("correlation_id", "")))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        from fastapi.responses import JSONResponse
        c = ctx_of(request)
        code = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND",
                405: "METHOD_NOT_ALLOWED", 429: "RATE_LIMITED"}.get(int(exc.status_code), "INTERNAL")
        err = ApiError(code, str(exc.detail or code), status=int(exc.status_code))
        return JSONResponse(status_code=err.status, content=error_response(err, c.get("request_id", ""),
                                                                          c.get("correlation_id", "")))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        from fastapi.responses import JSONResponse
        c = ctx_of(request)
        err = ApiError("INTERNAL", "internal error")  # never leak the raw exception
        return JSONResponse(status_code=err.status, content=error_response(err, c.get("request_id", ""),
                                                                          c.get("correlation_id", "")))
