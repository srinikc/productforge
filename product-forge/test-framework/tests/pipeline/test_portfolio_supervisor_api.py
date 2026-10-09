"""BI-PF: Pipeline Supervisor API (status/start/stop) + core.portfolio helpers."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")
os.environ.setdefault("API_ALLOW_ANON", "1")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import portfolio  # noqa: E402


def test_status_shape():
    st = portfolio.supervisor_status()
    assert set(("running", "supervisor_pids", "running_projects", "start_command")) <= set(st)


def test_start_idempotent_when_running(monkeypatch):
    monkeypatch.setattr(portfolio, "supervisor_running", lambda: True)
    res = portfolio.start_supervisor(1)
    assert res["ok"] is True and res.get("already_running") is True


def test_stop_no_supervisor(monkeypatch):
    monkeypatch.setattr(portfolio, "supervisor_status", lambda: {"running": False})
    res = portfolio.stop_supervisor()
    assert res["ok"] is True and res["stopped"] == []


def test_api_get(monkeypatch):
    monkeypatch.setattr(portfolio, "supervisor_status", lambda: {"running": False, "supervisor_pids": []})
    client = TestClient(app)
    r = client.get("/api/v1/portfolio/supervisor")
    assert r.status_code == 200 and r.json()["data"]["running"] is False


def test_api_start_stop(monkeypatch):
    monkeypatch.setattr(portfolio, "start_supervisor", lambda mc=1: {"ok": True, "pid": 123})
    monkeypatch.setattr(portfolio, "stop_supervisor", lambda: {"ok": True, "stopped": [123]})
    client = TestClient(app)
    assert client.post("/api/v1/portfolio/supervisor/start", json={}).status_code == 200
    assert client.post("/api/v1/portfolio/supervisor/stop", json={}).status_code == 200
