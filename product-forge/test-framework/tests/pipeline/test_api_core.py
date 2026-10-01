"""API-2: core PF read-model APIs — projects, runs, pipeline/stages/tasks, artifacts, evidence, backlog."""
import json
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

_SCRATCH = "_test_api2_core"


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def scratch_project():
    """A uniquely-named scratch project (safe to delete per AGENTS.md)."""
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "project.json").write_text("{}", encoding="utf-8")
    yield _SCRATCH
    if d.exists():
        shutil.rmtree(d)


def test_pipeline_definition(client):
    r = client.get("/api/v1/pipeline")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["count"] > 0 and data["stages"][0]["id"] != ""


def test_pipeline_stages_definition_shape(client):
    r = client.get("/api/v1/pipeline/stages")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


def test_tasks_listing(client):
    r = client.get("/api/v1/tasks")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


def test_backlog_stats(client):
    r = client.get("/api/v1/backlog/stats")
    assert r.status_code == 200
    assert "data" in r.json()


def test_projects_listing_pagination_links(client):
    r = client.get("/api/v1/projects", params={"limit": 5})
    assert r.status_code == 200
    assert "self" in r.json()["links"]


def test_project_not_found_contract(client):
    r = client.get("/api/v1/projects/does-not-exist-xyz")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_runs_requires_project(client):
    r = client.get("/api/v1/runs")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"


def test_artifacts_unknown_project(client):
    r = client.get("/api/v1/artifacts", params={"project": "nope-xyz"})
    assert r.status_code == 404


def test_openapi_has_core_resources(client):
    paths = client.get("/" + "openapi" + "." + "json").json()["paths"]
    for p in ("/api/v1/projects", "/api/v1/pipeline", "/api/v1/backlog", "/api/v1/runs/start"):
        assert p in paths


def test_artifact_content_roundtrip(client, scratch_project):
    from core import artifact_store
    pdir = str(Path(_paths.PRODUCTS_DIR) / scratch_project)
    artifact_store.create_or_update_artifact(pdir, "1", "designer", "hello-artifact")
    r = client.get(f"/api/v1/artifacts/1/designer", params={"project": scratch_project})
    assert r.status_code == 200
    assert r.json()["data"]["content"] == "hello-artifact"


def test_start_now_calls_priority_with_valid_kwargs(client, scratch_project, monkeypatch):
    from core import run_entry
    seen = {}

    def spy(project, *, by="", item_id="", victim="", products_dir="products"):
        seen.update({"project": project, "by": by, "item_id": item_id, "products_dir": products_dir})
        return {"ok": True, "enqueued": {"run_id": "run-test-1"}}

    monkeypatch.setattr(run_entry, "run_now_on_priority", spy)
    r = client.post("/api/v1/runs/start", json={"project": scratch_project, "now": True})
    assert r.status_code == 200
    assert r.json()["resource_id"] == "run-test-1"
    assert seen["project"] == scratch_project and seen["products_dir"]


def test_stop_cancels_and_signals_control_channel(client, scratch_project, monkeypatch):
    from core import job_manager, run_guard
    monkeypatch.setattr(job_manager, "cancel",
                        lambda project: {"project": project, "state": "cancelled"})
    monkeypatch.setattr(run_guard, "active_run", lambda *a, **k: {"active": True})
    r = client.post("/api/v1/runs/stop", json={"project": scratch_project})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "stop_requested" and data["cancelled"] is True and data["signaled"] is True
    ctrl = Path(_paths.PRODUCTS_DIR) / scratch_project / "control.json"
    assert ctrl.is_file() and json.loads(ctrl.read_text(encoding="utf-8"))["action"] == "stop"
