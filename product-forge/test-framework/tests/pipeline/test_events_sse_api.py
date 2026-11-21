"""Tests for SSE Event Streaming and Subscription CRUD API (BI-PF-1274)."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from api.app import app
from core import events as _events
from core import paths as _paths

_TEST_PROJECT = "_test_events_sse"


@pytest.fixture
def client():
    os.environ["API_ALLOW_ANON"] = "1"
    return TestClient(app)


@pytest.fixture
def scratch_project():
    d = Path(_paths.PRODUCTS_DIR) / _TEST_PROJECT
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    yield _TEST_PROJECT
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def test_events_stream_sse_format(client, scratch_project):
    """AC-1: GET /api/v1/events/stream connects and streams text/event-stream chunks."""
    r = client.get(f"/api/v1/events/stream?project={scratch_project}")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert ": connected\n\n" in r.text


def test_events_stream_since_replay(client, scratch_project):
    """AC-2: GET /api/v1/events/stream accepts since parameter and replays backlog events."""
    d = Path(_paths.PRODUCTS_DIR) / scratch_project
    _events.emit(str(d), "run_started", run_id="run-replay-1", agent="test-agent")

    r = client.get(f"/api/v1/events/stream?project={scratch_project}&since=2020-01-01T00:00:00Z")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: run_started\n" in r.text
    assert "run-replay-1" in r.text


def test_subscription_create_and_list(client, scratch_project):
    """AC-3: Operators can create and list event subscriptions with tenant scoping."""
    payload = {
        "id": "sub-test-1",
        "transport": "webhook",
        "event_types": ["run_started", "run_completed"],
        "target": "https://example.com/events/webhook",
        "filter": {"min_severity": "low"},
        "enabled": True,
    }
    r = client.post(
        f"/api/v1/events/subscriptions?project={scratch_project}",
        json=payload,
        headers={"X-Roles": "operator"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["stored"] is True
    assert data["subscription"]["id"] == "sub-test-1"
    assert data["subscription"]["transport"] == "webhook"

    # List subscriptions
    r_list = client.get(f"/api/v1/events/subscriptions?project={scratch_project}")
    assert r_list.status_code == 200
    list_data = r_list.json()["data"]
    assert list_data["count"] >= 1
    ids = [s["id"] for s in list_data["subscriptions"]]
    assert "sub-test-1" in ids


def test_subscription_patch_and_delete(client, scratch_project):
    """AC-4: Operators can update subscription fields via PATCH and delete subscriptions."""
    # Create subscription
    sub_id = "sub-patch-test"
    payload = {
        "id": sub_id,
        "transport": "notify",
        "event_types": ["alert_raised"],
        "enabled": True,
    }
    r_create = client.post(
        f"/api/v1/events/subscriptions?project={scratch_project}",
        json=payload,
        headers={"X-Roles": "operator"},
    )
    assert r_create.status_code == 200

    # Get single
    r_get = client.get(f"/api/v1/events/subscriptions/{sub_id}?project={scratch_project}")
    assert r_get.status_code == 200
    assert r_get.json()["data"]["subscription"]["id"] == sub_id

    # Patch subscription
    r_patch = client.patch(
        f"/api/v1/events/subscriptions/{sub_id}?project={scratch_project}",
        json={"enabled": False, "transport": "sse"},
        headers={"X-Roles": "operator"},
    )
    assert r_patch.status_code == 200
    patched = r_patch.json()["data"]["subscription"]
    assert patched["enabled"] is False
    assert patched["transport"] == "sse"

    # Delete subscription
    r_del = client.delete(
        f"/api/v1/events/subscriptions/{sub_id}?project={scratch_project}",
        headers={"X-Roles": "operator"},
    )
    assert r_del.status_code == 200
    assert r_del.json()["data"]["deleted"] is True

    # Confirm 404 after deletion
    r_get_after = client.get(f"/api/v1/events/subscriptions/{sub_id}?project={scratch_project}")
    assert r_get_after.status_code == 404


def test_subscription_validation_errors(client, scratch_project):
    """AC-5: Validates required subscription fields and rejects invalid transports with 400."""
    # Missing id
    r1 = client.post(
        f"/api/v1/events/subscriptions?project={scratch_project}",
        json={"transport": "webhook", "event_types": ["run_started"]},
        headers={"X-Roles": "operator"},
    )
    assert r1.status_code == 400
    assert r1.json()["error"]["code"] == "VALIDATION_FAILED"

    # Invalid transport
    r2 = client.post(
        f"/api/v1/events/subscriptions?project={scratch_project}",
        json={"id": "sub-bad-transport", "transport": "unsupported_protocol", "event_types": ["run_started"]},
        headers={"X-Roles": "operator"},
    )
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "VALIDATION_FAILED"

    # Missing event_types
    r3 = client.post(
        f"/api/v1/events/subscriptions?project={scratch_project}",
        json={"id": "sub-no-events", "transport": "webhook", "event_types": []},
        headers={"X-Roles": "operator"},
    )
    assert r3.status_code == 400
    assert r3.json()["error"]["code"] == "VALIDATION_FAILED"

    # Non-existent subscription PATCH returns 404
    r4 = client.patch(
        f"/api/v1/events/subscriptions/non-existent-sub?project={scratch_project}",
        json={"enabled": False},
        headers={"X-Roles": "operator"},
    )
    assert r4.status_code == 404
