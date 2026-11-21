"""Contract tests for BI-PF-1275: Eventing SSOT bus daemon/service run model + ops."""
import os
import sys
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("PF_OFFLINE", "1")
os.environ.setdefault("API_ALLOW_ANON", "1")

from fastapi.testclient import TestClient
from api.app import app
from core import events as _events


def test_ac1_bus_status_query(monkeypatch):
    """AC-1: GET /api/v1/events/bus returns operational daemon status."""
    monkeypatch.setattr(_events, "bus_status", lambda project=None: {
        "running": False,
        "pid": None,
        "uptime_seconds": 0,
        "status": "stopped"
    })
    client = TestClient(app)
    resp = client.get("/api/v1/events/bus", headers={"authorization": "Bearer pf-edp-local-token-32-chars-long"})
    assert resp.status_code == 200, resp.text
    data = resp.json().get("data", resp.json())
    assert data["running"] is False
    assert data["status"] == "stopped"


def test_ac2_start_daemon_idempotent(monkeypatch):
    """AC-2: POST /api/v1/events/bus/start launches daemon idempotently."""
    state = {"started": False}

    def _start(project=None):
        if state["started"]:
            return {"ok": True, "pid": 4321, "already_running": True}
        state["started"] = True
        return {"ok": True, "pid": 4321, "already_running": False}

    monkeypatch.setattr(_events, "start_bus", _start)
    client = TestClient(app)
    headers = {
        "authorization": "Bearer pf-edp-local-token-32-chars-long",
        "x-roles": "operator,admin"
    }

    # First start
    resp1 = client.post("/api/v1/events/bus/start", json={}, headers=headers)
    assert resp1.status_code == 200, resp1.text
    d1 = resp1.json().get("data", resp1.json())
    assert d1["ok"] is True
    assert d1["pid"] == 4321
    assert d1.get("already_running") is False

    # Second start (idempotent)
    resp2 = client.post("/api/v1/events/bus/start", json={}, headers=headers)
    assert resp2.status_code == 200, resp2.text
    d2 = resp2.json().get("data", resp2.json())
    assert d2["ok"] is True
    assert d2["already_running"] is True


def test_ac3_stop_daemon_graceful(monkeypatch):
    """AC-3: POST /api/v1/events/bus/stop gracefully terminates daemon."""
    monkeypatch.setattr(_events, "stop_bus", lambda project=None: {
        "ok": True,
        "stopped": [4321]
    })
    client = TestClient(app)
    headers = {
        "authorization": "Bearer pf-edp-local-token-32-chars-long",
        "x-roles": "operator,admin"
    }
    resp = client.post("/api/v1/events/bus/stop", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    d = resp.json().get("data", resp.json())
    assert d["ok"] is True
    assert d["stopped"] == [4321]


def test_ac4_health_integration(monkeypatch):
    """AC-4: GET /health includes event_bus component status."""
    monkeypatch.setattr(_events, "bus_status", lambda project=None: {
        "running": True,
        "pid": 4321,
        "uptime_seconds": 120,
        "status": "running"
    })
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # /health returns an envelope or dict with components
    components = data.get("components", data)
    assert "event_bus" in components
    assert components["event_bus"]["status"] in ("ok", "running")


def test_ac5_bus_auth_operator_enforcement(monkeypatch):
    """AC-5: Operator mutations enforce authentication and authorization."""
    monkeypatch.delenv("API_ALLOW_ANON", raising=False)
    monkeypatch.setenv("PF_API_TOKEN", "test-token")
    client = TestClient(app)
    # Anonymous call must fail closed
    resp_anon = client.post("/api/v1/events/bus/start", json={})
    assert resp_anon.status_code in (401, 403), resp_anon.status_code

    # Non-operator authenticated user must be rejected with 403
    resp_viewer = client.post("/api/v1/events/bus/start", json={}, headers={
        "authorization": "Bearer test-token",
        "x-roles": "viewer"
    })
    assert resp_viewer.status_code in (401, 403), resp_viewer.status_code

