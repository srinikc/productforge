"""BI-PF-1239: CI/CD + gates read API (engineering router)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402


def _client():
    return TestClient(app)


def test_ci_cd_model_endpoint():
    r = _client().get("/api/v1/engineering/ci-cd")
    assert r.status_code == 200
    assert r.json()["data"]["mechanical_gates"]


def test_ci_cd_scope_product_forge():
    r = _client().get("/api/v1/engineering/ci-cd/product_forge")
    assert r.status_code == 200
    assert r.json()["data"]["effective"] is True


def test_ci_cd_scope_project_not_built():
    r = _client().get("/api/v1/engineering/ci-cd/project", params={"project": "no-such-xyz-1239"})
    assert r.status_code == 200
    assert r.json()["data"]["effective"] is False


def test_gates_endpoint():
    r = _client().get("/api/v1/engineering/gates")
    assert r.status_code == 200
    assert r.json()["data"]["catalog"]
