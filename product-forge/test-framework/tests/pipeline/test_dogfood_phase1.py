"""BI-PF-0458: DOGFOOD Phase 1 — API auto-dogfood (start seed+enqueue, status aggregation, delivery assertions)."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import dogfood_run  # noqa: E402
from core import project_store  # noqa: E402
from core import run_entry  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


def test_start_seeds_and_enqueues(tmp_path, monkeypatch):
    seen = {}

    def fake_enqueue(project, products_dir="products", tier="", **kw):
        seen.update(project=project, tier=tier, source=kw.get("source"))
        return {"run_id": "run-dog-1", "queued": True}

    monkeypatch.setattr(run_entry, "enqueue", fake_enqueue)
    res = dogfood_run.start("a tiny idea", "dogproj", tier="kctier", auto=True,
                            caps={"minutes": 10}, products_dir=str(tmp_path))
    assert res["run_id"] == "run-dog-1"
    assert seen == {"project": "dogproj", "tier": "kctier", "source": "dogfood"}
    cfg = project_store.load("dogproj", str(tmp_path))
    assert cfg.get("idea") == "a tiny idea"
    assert cfg.get("model_tier") == "kctier"
    assert cfg.get("auto_mode") is True and cfg.get("auto_approve") is True


def test_status_aggregates(tmp_path):
    res = dogfood_run.status("nope", products_dir=str(tmp_path))
    assert res["project"] == "nope" and res["exists"] is False
    for k in ("active_run", "events", "log_tail", "defects", "validation", "delivery"):
        assert k in res


def test_assert_delivery_fail_closed_empty(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    r = dogfood_run.assert_delivery(str(d))
    assert r["delivered"] is False and r["checks"]["is_repo"] is False


def test_assert_delivery_needs_validation_or_close_loop(tmp_path):
    d = tmp_path / "p"
    d.mkdir()

    def g(*a):
        subprocess.run(["git", *a], cwd=str(d), capture_output=True, text=True)

    g("init", "-q")
    g("config", "user.email", "t@local")
    g("config", "user.name", "t")
    (d / "README.md").write_text("x\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-q", "-m", "init")
    r = dogfood_run.assert_delivery(str(d))
    assert r["checks"]["is_repo"] is True and r["checks"]["commits"] >= 1
    assert r["delivered"] is False          # commits alone are not delivery


def test_api_run_endpoint(client, monkeypatch):
    monkeypatch.setattr(dogfood_run, "start",
                        lambda *a, **k: {"project": a[1], "run_id": "run-x", "tier": "kctier"})
    r = client.post("/api/v1/dogfood/run", json={"project": "p1", "idea": "an idea"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["run_id"] == "run-x"


def test_api_run_requires_project_and_idea(client):
    r = client.post("/api/v1/dogfood/run", json={"project": "p1"})
    assert r.status_code >= 400


def test_api_status_endpoint(client, monkeypatch):
    monkeypatch.setattr(dogfood_run, "status",
                        lambda project, run_id="", **k: {"project": project, "run_id": run_id})
    r = client.get("/api/v1/dogfood/runs/run-1", params={"project": "p1"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["run_id"] == "run-1"
