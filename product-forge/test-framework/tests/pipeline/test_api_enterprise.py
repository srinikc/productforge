"""API-4: enterprise/SaaS/OEM surface — instance, tenants, users, tiers, license, entitlements, members, seats."""
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


def test_tiers(client):
    r = client.get("/api/v1/enterprise/tiers")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"] == "enterprise"
    assert "trial" in body["data"]


def test_instance(client):
    r = client.get("/api/v1/enterprise/instance")
    assert r.status_code == 200
    assert "role" in r.json()["data"]


def test_tenants(client):
    r = client.get("/api/v1/enterprise/tenants")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


def test_create_tenant_requires_name(client):
    r = client.post("/api/v1/enterprise/tenants", json={})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"


def test_create_tenant_unknown_tier(client):
    r = client.post("/api/v1/enterprise/tenants", json={"name": "acme-validation", "tier": "no-such-tier"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"
