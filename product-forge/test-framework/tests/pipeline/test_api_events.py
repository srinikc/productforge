"""API-5: the formalized event envelope + read-only Event API."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import events as _events  # noqa: E402
from core import paths as _paths  # noqa: E402

_SCRATCH = "_test_api_events"


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def scratch():
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    yield _SCRATCH
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def test_event_types(client):
    r = client.get("/api/v1/events/types")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["event_version"] == "1"
    assert "run_started" in data["types"]


def test_event_envelope_and_read(client, scratch):
    d = Path(_paths.PRODUCTS_DIR) / scratch
    _events.emit(str(d), "run_started", run_id="r1", task_id="TC-PF-0001", actor="tester")
    r = client.get("/api/v1/events", params={"project": scratch})
    assert r.status_code == 200
    rows = r.json()["data"]["events"]
    assert rows
    e = rows[-1]
    for k in ("event_id", "event_type", "event_version", "occurred_at", "correlation_id",
              "task_id", "payload"):
        assert k in e, k
    assert e["event_type"] == "run_started" and e["task_id"] == "TC-PF-0001"


def test_events_unknown_project_404(client):
    r = client.get("/api/v1/events", params={"project": "nope-xyz"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
