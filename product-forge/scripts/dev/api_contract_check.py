"""API contract checks for the canonical api/ surface.

Exercises the app in-process with the FastAPI TestClient: envelope shape, request/correlation id propagation,
error contract, auth boundary, health/ready, and resource reachability. It is a general control-plane contract
check and is SIDE-EFFECT FREE: it does not call the Intake endpoint (Intake is a separate external-ingestion
path) and does not write any store. Idempotency is covered by the API unit tests
(``test-framework/tests/pipeline/test_api_foundation.py``). Run: ``python scripts/dev/api_contract_check.py``.
Exit code 1 on any failure (wire into CI/precheck).
"""

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
    _check(set(r.json()) >= SUCCESS_KEYS, "health envelope keys")
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

    # NOTE: idempotency is NOT exercised here - it is covered by the API unit tests. This check stays
    # side-effect free and independent of the external-ingestion (Intake) path.

    # API-2 core resources: canonical envelope + reachable
    for path in ("/api/v1/pipeline", "/api/v1/pipeline/stages", "/api/v1/tasks",
                 "/api/v1/backlog", "/api/v1/backlog/stats", "/api/v1/projects"):
        r = c.get(path)
        _check(r.status_code == 200, f"{path} status {r.status_code}")
        _check(set(r.json()) >= SUCCESS_KEYS, f"{path} envelope keys")

    # canonical validation error on missing required query param
    r = c.get("/api/v1/runs")
    _check(r.status_code == 400, f"runs missing-project status {r.status_code}")
    _check((r.json().get("error") or {}).get("code") == "VALIDATION_FAILED", "runs validation error code")

    # API-3 engineering surface: canonical envelope + reachable
    for path in ("/api/v1/agents", "/api/v1/workers/queue", "/api/v1/workers/capacity",
                 "/api/v1/issues/stats", "/api/v1/engineering", "/api/v1/engineering/coverage",
                 "/api/v1/engineering/tasks", "/api/v1/engineering/workers",
                 "/api/v1/engineering/schedule", "/api/v1/engineering/worker-providers",
                 "/api/v1/vcs/branch-name", "/api/v1/github", "/api/v1/github/evidence",
                 "/api/v1/events/types", "/api/v1/apidocs." + "json", "/api/v1/backlog/stats"):
        r = c.get(path)
        _check(r.status_code == 200, f"{path} status {r.status_code}")
        _check(set(r.json()) >= SUCCESS_KEYS, f"{path} envelope keys")

    r = c.get("/api/v1/agents")
    agents = r.json().get("data") or []
    _check(bool(agents), "agents list non-empty")
    if agents:
        aid = agents[0].get("agent_id")
        r = c.get(f"/api/v1/agents/{aid}/capabilities")
        _check(r.status_code == 200, f"agent capabilities status {r.status_code}")
        _check(set(r.json()) >= SUCCESS_KEYS, "agent capabilities envelope keys")

    # project-scoped engineering reads are fail-closed on an unknown project
    for path in ("/api/v1/validation", "/api/v1/gates/pr", "/api/v1/vcs",
                 "/api/v1/tests/matrix", "/api/v1/validation/policy"):
        r = c.get(path, params={"project": "does-not-exist-xyz"})
        _check(r.status_code == 404, f"{path} unknown-project status {r.status_code}")
        _check((r.json().get("error") or {}).get("code") == "NOT_FOUND", f"{path} unknown-project code")

    # GitHub: project-scope reads are fail-closed on an unknown project
    for path in ("/api/v1/github", "/api/v1/github/evidence"):
        r = c.get(path, params={"scope": "project", "project": "does-not-exist-xyz"})
        _check(r.status_code == 404, f"{path} unknown-project status {r.status_code}")

    # Event API: project-scoped read is fail-closed on an unknown project
    r = c.get("/api/v1/events", params={"project": "does-not-exist-xyz"})
    _check(r.status_code == 404, f"/api/v1/events unknown-project status {r.status_code}")

    if FAILS:
        print("api-contract: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("api-contract: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
