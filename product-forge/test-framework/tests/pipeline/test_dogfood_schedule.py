"""BI-PF-0460: dogfood schedule (due + tick) and trends/regression."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import dogfood_run, dogfood_schedule as ds  # noqa: E402
from core import validation_engine as ve  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


def test_due_logic(monkeypatch):
    now = datetime.now()
    data = {"entries": [
        {"project": "p1", "enabled": True, "interval_hours": 24, "last_run": ""},
        {"project": "p2", "enabled": True, "interval_hours": 24, "last_run": now.isoformat()},
        {"project": "p3", "enabled": False, "interval_hours": 1, "last_run": ""},
    ]}
    assert [e["project"] for e in ds.due(now, data)] == ["p1"]


def test_run_due_enqueues_only_due(monkeypatch):
    now = datetime.now()
    data = {"entries": [
        {"project": "p1", "enabled": True, "interval_hours": 24, "last_run": ""},
        {"project": "p2", "enabled": True, "interval_hours": 24, "last_run": now.isoformat()},
    ]}
    seen = []
    monkeypatch.setattr(ds, "load", lambda: data)
    monkeypatch.setattr(ds, "save", lambda d: d)
    monkeypatch.setattr(dogfood_run, "start", lambda idea, project, **k: (seen.append(project) or {"run_id": "r"}))
    ds.run_due()
    assert seen == ["p1"]
    assert data["entries"][0]["last_run"] != ""


def test_trends_regression(monkeypatch):
    monkeypatch.setattr(ve, "list_runs", lambda scope, project=None, profile="": [
        {"result": "PASS", "run_id": "a"}, {"result": "FAIL", "run_id": "b"}])
    t = dogfood_run.trends("p")
    assert t["regression"] is True and t["counts"]["PASS"] == 1


def test_api_schedule_and_trends(client, monkeypatch):
    monkeypatch.setattr(ds, "load", lambda: {"entries": [{"project": "p1", "enabled": True}]})
    monkeypatch.setattr(ds, "due", lambda now=None, data=None: [])
    r = client.get("/api/v1/dogfood/schedule")
    assert r.status_code == 200 and "entries" in r.json()["data"]

    monkeypatch.setattr(dogfood_run, "trends", lambda project, **k: {"project": project, "regression": False})
    r = client.get("/api/v1/dogfood/trends", params={"project": "p1"})
    assert r.status_code == 200 and r.json()["data"]["project"] == "p1"


def test_api_tick(client, monkeypatch):
    monkeypatch.setattr(ds, "run_due", lambda products_dir=None: {"due": 0, "started": []})
    r = client.post("/api/v1/dogfood/schedule/tick")
    assert r.status_code == 200 and r.json()["data"]["due"] == 0
