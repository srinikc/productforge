"""Health / readiness endpoints (API-0.1 §1 public paths)."""

from fastapi import APIRouter, Request

from ..envelope import from_request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request):
    # BI-PF-1253: surface the code the process loaded vs the working tree (staleness is silent otherwise).
    try:
        from core import runtime_freshness
        fs = runtime_freshness.status()
        code = {"loaded_sha": fs["loaded_sha"][:12], "current_sha": fs["current_sha"][:12],
                "stale": fs["stale"]}
    except Exception as e:
        code = {"error": type(e).__name__}

    bus_comp = {"status": "stopped"}
    try:
        from core import events
        bst = events.bus_status()
        bus_comp = {"status": "ok" if bst.get("running") else bst.get("status", "stopped"), **bst}
    except Exception as e:
        bus_comp = {"status": "error", "error": type(e).__name__}

    components = {"event_bus": bus_comp}
    resp = from_request(request, {"status": "ok", "service": "product-forge-api", "version": "v1",
                                  "code": code, "components": components}, resource="health")
    resp["components"] = components
    resp["event_bus"] = bus_comp
    return resp



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
    try:
        from core import runtime_freshness
        fs = runtime_freshness.status()
        checks["code_fresh"] = "ok" if not fs["stale"] else (
            f"stale: loaded {fs['loaded_sha'][:8]} != tree {fs['current_sha'][:8]} - restart to refresh")
    except Exception as e:
        checks["code_fresh"] = f"error: {type(e).__name__}"
    return from_request(request, {"ready": ok, "checks": checks}, resource="readiness",
                        status="ok" if ok else "error")
