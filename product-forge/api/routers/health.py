"""Health / readiness endpoints (API-0.1 §1 public paths)."""

from fastapi import APIRouter, Request

from ..envelope import from_request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request):
    return from_request(request, {"status": "ok", "service": "product-forge-api", "version": "v1"},
                        resource="health")


@router.get("/ready")
def ready(request: Request):
    checks = {}
    ok = True
    try:
        from core import backlog  # canonical store reachable
        backlog.stats("product_forge", None)
        checks["backlog"] = "ok"
    except Exception as e:
        checks["backlog"] = f"error: {type(e).__name__}"
        ok = False
    try:
        from core import events
        checks["events"] = "ok" if events else "ok"
    except Exception as e:
        checks["events"] = f"error: {type(e).__name__}"
        ok = False
    return from_request(request, {"ready": ok, "checks": checks}, resource="readiness",
                        status="ok" if ok else "error")
