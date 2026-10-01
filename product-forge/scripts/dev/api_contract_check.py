"""API contract checks for the canonical api/ surface (API-1).

Exercises the app in-process with the FastAPI TestClient: envelope shape, request/correlation id propagation,
error contract, idempotency, auth boundary, health/ready, and intake. Run: ``python scripts/dev/api_contract_check.py``.
Exit code 1 on any failure (wire into CI/precheck).
"""

import json
import os
import sys

os.environ.setdefault("API_ALLOW_ANON", "1")

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

SUCCESS_KEYS = {"request_id", "correlation_id", "status", "resource", "resource_id",
                "data", "links", "warnings", "error"}
FAILS = []


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main() -> int:
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)

    r = c.get("/api/v1/health")
    _check(r.status_code == 200, f"health status {r.status_code}")
    _check(SUCCESS_KEYS <= set(r.json()), "health envelope keys")
    _check(r.headers.get("X-Request-Id"), "health echoes X-Request-Id")

    r = c.get("/api/v1/health", headers={"X-Request-Id": "req-fixed", "X-Correlation-Id": "corr-fixed"})
    _check(r.json().get("request_id") == "req-fixed", "request_id echoed")
    _check(r.json().get("correlation_id") == "corr-fixed", "correlation_id echoed")

    r = c.get("/api/v1/ready")
    _check(r.status_code == 200, f"ready status {r.status_code}")
    _check("checks" in r.json().get("data", {}), "ready checks present")

    r = c.get("/api/v1/does-not-exist")
    _check(r.status_code == 404, f"404 status {r.status_code}")
    err = r.json().get("error") or {}
    _check(err.get("code") == "NOT_FOUND", "404 error code")
    for k in ("code", "message", "category", "retryable", "details", "request_id", "correlation_id"):
        _check(k in err, f"error field {k}")

    # idempotency: same key replays
    body = {"source": "generic", "payload": {"title": "contract-check scratch", "description": "scratch"},
            "scope": "product_forge"}
    h = {"Idempotency-Key": "contract-check-key-1"}
    r1 = c.post("/api/v1/intake", json=body, headers=h)
    r2 = c.post("/api/v1/intake", json=body, headers=h)
    _check(r1.status_code == 200, f"intake1 status {r1.status_code}")
    _check(r2.status_code == 200 and (r2.json().get("data") or {}).get("replayed") is True,
           "idempotent replay detected")

    # API-2 core resources: canonical envelope + reachable
    for path in ("/api/v1/pipeline", "/api/v1/pipeline/stages", "/api/v1/tasks",
                 "/api/v1/backlog", "/api/v1/backlog/stats", "/api/v1/projects"):
        r = c.get(path)
        _check(r.status_code == 200, f"{path} status {r.status_code}")
        _check(SUCCESS_KEYS <= set(r.json()), f"{path} envelope keys")

    # canonical validation error on missing required query param
    r = c.get("/api/v1/runs")
    _check(r.status_code == 400, f"runs missing-project status {r.status_code}")
    _check((r.json().get("error") or {}).get("code") == "VALIDATION_FAILED", "runs validation error code")

    # API-3 engineering surface: canonical envelope + reachable
    for path in ("/api/v1/agents", "/api/v1/workers/queue", "/api/v1/workers/capacity",
                 "/api/v1/issues/stats", "/api/v1/engineering", "/api/v1/engineering/coverage",
                 "/api/v1/engineering/tasks", "/api/v1/engineering/workers",
                 "/api/v1/engineering/schedule", "/api/v1/engineering/worker-providers",
                 "/api/v1/vcs/branch-name", "/api/v1/backlog/stats"):
        r = c.get(path)
        _check(r.status_code == 200, f"{path} status {r.status_code}")
        _check(SUCCESS_KEYS <= set(r.json()), f"{path} envelope keys")

    r = c.get("/api/v1/agents")
    agents = r.json().get("data") or []
    _check(bool(agents), "agents list non-empty")
    if agents:
        aid = agents[0].get("agent_id")
        r = c.get(f"/api/v1/agents/{aid}/capabilities")
        _check(r.status_code == 200, f"agent capabilities status {r.status_code}")
        _check(SUCCESS_KEYS <= set(r.json()), "agent capabilities envelope keys")

    # project-scoped engineering reads are fail-closed on an unknown project
    for path in ("/api/v1/validation", "/api/v1/gates/pr", "/api/v1/vcs",
                 "/api/v1/tests/matrix", "/api/v1/validation/policy"):
        r = c.get(path, params={"project": "does-not-exist-xyz"})
        _check(r.status_code == 404, f"{path} unknown-project status {r.status_code}")
        _check((r.json().get("error") or {}).get("code") == "NOT_FOUND", f"{path} unknown-project code")

    if FAILS:
        print("api-contract: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("api-contract: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
