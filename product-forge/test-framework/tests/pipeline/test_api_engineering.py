"""API-3: engineering/validation APIs — validation, tests, gates, issues, vcs, workers, agents."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import paths as _paths  # noqa: E402

_SCRATCH = "_test_api3_eng"


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def scratch_project():
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "project.json").write_text("{}", encoding="utf-8")
    yield _SCRATCH
    if d.exists():
        shutil.rmtree(d)


def test_agents_list_and_capabilities(client):
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    agents = r.json()["data"]
    assert agents and agents[0]["agent_id"]
    r2 = client.get(f"/api/v1/agents/{agents[0]['agent_id']}/capabilities")
    assert r2.status_code == 200
    assert "reasoning_enabled" in r2.json()["data"]


def test_agent_not_found_contract(client):
    r = client.get("/api/v1/agents/nope-xyz")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_workers_queue_and_capacity(client):
    r = client.get("/api/v1/workers/queue")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "jobs" in data and "limits" in data
    r2 = client.get("/api/v1/workers/capacity")
    assert r2.status_code == 200
    assert "limits" in r2.json()["data"]


def test_issues_stats_and_unknown_not_found(client):
    r = client.get("/api/v1/issues/stats")
    assert r.status_code == 200
    r2 = client.get("/api/v1/issues/IS-NOPE-9999", params={"scope": "product_forge"})
    assert r2.status_code == 404
    assert r2.json()["error"]["code"] == "NOT_FOUND"


def test_issue_create_requires_title(client):
    r = client.post("/api/v1/issues", json={"scope": "product_forge"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"


def test_project_scoped_reads_unknown_project_404(client):
    for path in ("/api/v1/validation", "/api/v1/gates/pr", "/api/v1/vcs",
                 "/api/v1/tests/matrix", "/api/v1/gates/quality"):
        r = client.get(path, params={"project": "does-not-exist-xyz"})
        assert r.status_code == 404, path
        assert r.json()["error"]["code"] == "NOT_FOUND", path


def test_project_scoped_reads_on_scratch(client, scratch_project):
    for path in ("/api/v1/validation", "/api/v1/validation/policy", "/api/v1/tests/matrix",
                 "/api/v1/tests/cycles", "/api/v1/gates/quality", "/api/v1/vcs",
                 "/api/v1/vcs/status", "/api/v1/vcs/branches", "/api/v1/vcs/commits"):
        r = client.get(path, params={"project": scratch_project})
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert "data" in r.json(), path


def test_engineering_flow_is_valid_and_covered(client):
    from core import engineering_flow
    res = engineering_flow.validate()
    assert res["ok"], res["errors"]
    assert res["checked"] > 0
    r = client.get("/api/v1/engineering")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data.get("flow") and data.get("invariants") and data.get("forbidden")
    r2 = client.get("/api/v1/engineering/coverage")
    assert r2.status_code == 200
    assert r2.json()["data"]["total"] == res["checked"]


def test_engineering_stage_lookup(client):
    r = client.get("/api/v1/engineering/stages")
    assert r.status_code == 200
    steps = r.json()["data"]
    assert steps
    sid = steps[0]["id"]
    r2 = client.get(f"/api/v1/engineering/stages/{sid}")
    assert r2.status_code == 200
    assert r2.json()["data"]["id"] == sid
    r3 = client.get("/api/v1/engineering/stages/does-not-exist-xyz")
    assert r3.status_code == 404
