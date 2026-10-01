"""API-1: canonical api/ surface — envelopes, ids, errors, idempotency, auth, health, intake."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_envelope(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert {"request_id", "correlation_id", "status", "data", "error"} <= set(body)
    assert body["status"] == "ok" and body["error"] is None


def test_request_correlation_ids_propagate(client):
    r = client.get("/api/v1/health", headers={"X-Request-Id": "req-1", "X-Correlation-Id": "corr-1"})
    assert r.json()["request_id"] == "req-1"
    assert r.json()["correlation_id"] == "corr-1"
    assert r.headers["X-Request-Id"] == "req-1"


def test_unknown_route_error_contract(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "NOT_FOUND"
    assert err["retryable"] is False
    assert err["category"] == "client"


def test_idempotency_replay(client):
    body = {"source": "generic", "payload": {"title": "idem-scratch", "description": "scratch"},
            "scope": "product_forge"}
    h = {"Idempotency-Key": "idem-test-key"}
    r1 = client.post("/api/v1/intake", json=body, headers=h)
    r2 = client.post("/api/v1/intake", json=body, headers=h)
    assert r1.status_code == 200
    assert r2.json()["data"]["replayed"] is True


def test_idempotency_guard_blocks_duplicate_inflight():
    import uuid
    from api import idempotency
    k = f"inflight-key-{uuid.uuid4().hex}"
    st = idempotency.begin("t", "POST", "/x", k)
    assert st["state"] == "new"
    st2 = idempotency.begin("t", "POST", "/x", k)
    assert st2["state"] == "inflight"
    idempotency.complete("t", "POST", "/x", k)
    assert idempotency.lookup("t", "POST", "/x", k)["state"] == "done"


def test_intake_requires_payload(client):
    r = client.post("/api/v1/intake", json={"source": "generic"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"


def test_auth_fail_closed_when_token_required(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret-token")
    monkeypatch.setenv("API_ALLOW_ANON", "0")
    c = TestClient(app)
    # health/ready are public by contract; a protected route must fail closed.
    r = c.post("/api/v1/intake", json={"source": "generic", "payload": {"title": "x"}})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"
    r2 = c.post("/api/v1/intake", json={"source": "generic", "payload": {"title": "x"}},
                headers={"Authorization": "Bearer secret-token"})
    assert r2.status_code != 401


def test_error_redacts_secrets(client):
    from api.errors import ApiError
    e = ApiError("BAD_REQUEST", "api_key: super-secret-value")
    assert "super-secret-value" not in e.message
