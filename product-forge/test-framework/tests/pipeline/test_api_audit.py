"""FULL DOGFOOD + FINAL AUDIT: acceptance audit + lifecycle API."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import audit as _audit  # noqa: E402
from core import e2e_lifecycle as _e2e  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


def test_readiness_is_production_ready(client):
    r = client.get("/api/v1/audit/readiness")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["production_ready"] is True
    assert d["unmet"] == []


def test_acceptance_covers_all_areas(client):
    r = client.get("/api/v1/audit/acceptance")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    for area in ("API", "Runtime", "Engineering", "GitHub", "Validation", "Release", "Clients", "Invariants"):
        assert area in d["by_area"]


def test_lifecycle_dry_is_partial_success(client):
    r = client.post("/api/v1/audit/e2e", json={"dry": True})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["result"] == "PARTIAL_SUCCESS"
    assert not d["unmet"]
    assert len(d["stages"]) == len(_e2e.STAGES) - 1  # 'intake' is external-only


def test_audit_is_deterministic():
    assert _audit.summary()["production_ready"] is True
