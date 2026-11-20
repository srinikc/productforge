"""Contract and regression tests for BI-PF-1273: Eventing SSOT consumer shims.

Verifies:
  1. event_bus.emit() delegates to canonical core.events Go-backed seam.
  2. In-process on() callbacks execute with exception isolation.
  3. orchestration_context.route() and build() function over the canonical stream.
  4. notification_system and alerts adapters operate with exact public signatures.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from core import alerts, event_bus, events, orchestration_context
from core.notification_system import NotificationSystem, NotificationType
from core.paths import ROOT

TEST_PROJ = "_test_shim_proj"
TEST_PROJ_DIR = ROOT / "products" / TEST_PROJ


@pytest.fixture(autouse=True)
def cleanup_test_project():
    """Ensure clean test fixture directory before and after tests."""
    if TEST_PROJ_DIR.exists():
        shutil.rmtree(TEST_PROJ_DIR, ignore_errors=True)
    yield
    if TEST_PROJ_DIR.exists():
        shutil.rmtree(TEST_PROJ_DIR, ignore_errors=True)


def test_event_bus_canonical_delegation():
    """AC-1: event_bus.emit routes to core.events canonical stream."""
    ev = event_bus.emit("stuck", project=TEST_PROJ, run_id="run-42", stage="1a", agent="coder", detail="test error")
    assert isinstance(ev, dict)
    assert ev.get("kind") == "stuck"
    assert ev.get("run_id") == "run-42"
    assert ev.get("agent") == "coder"
    assert "at" in ev

    # Verify event appears in the canonical project event stream
    read_events = events.read(str(TEST_PROJ_DIR))
    assert len(read_events) >= 1
    matched = [e for e in read_events if e.get("event_type") == "stuck" or e.get("type") == "stuck"]
    assert len(matched) == 1
    canon = matched[0]
    assert canon.get("run_id") == "run-42"
    assert canon.get("agent") == "coder"


def test_event_bus_handlers_and_wildcard():
    """AC-2: in-process handlers for specific kind and wildcard receive event."""
    received_specific = []
    received_wildcard = []

    def specific_cb(ev):
        received_specific.append(ev)

    def wildcard_cb(ev):
        received_wildcard.append(ev)

    event_bus.on("anomaly", specific_cb)
    event_bus.on("*", wildcard_cb)

    ev = event_bus.emit("anomaly", project=TEST_PROJ, metric="cpu", value=99)
    assert len(received_specific) == 1
    assert received_specific[0].get("metric") == "cpu"
    assert len(received_wildcard) >= 1
    assert any(e.get("metric") == "cpu" for e in received_wildcard)


def test_event_bus_handler_exception_isolation():
    """AC-2 & Safety: a failing handler must never abort subsequent handlers or crash emit."""
    invoked = []

    def failing_cb(ev):
        raise RuntimeError("simulated handler crash")

    def safe_cb(ev):
        invoked.append(ev)

    event_bus.on("agent_conflict", failing_cb)
    event_bus.on("agent_conflict", safe_cb)

    # emit() must never raise
    ev = event_bus.emit("agent_conflict", project=TEST_PROJ, agent_a="alice", agent_b="bob")
    assert isinstance(ev, dict)
    assert len(invoked) == 1
    assert invoked[0].get("agent_a") == "alice"


def test_orchestration_context_routing():
    """AC-3: orchestration_context.route preserves _POLICY action mappings."""
    for kind in event_bus.KINDS:
        ev = {"kind": kind, "project": TEST_PROJ, "at": "2026-11-20T23:00:00"}
        decision = orchestration_context.route(ev)
        assert isinstance(decision, dict)
        assert decision.get("kind") == kind
        assert "action" in decision
        assert "priority" in decision

    # Specific policy mappings check
    stuck_dec = orchestration_context.route({"kind": "stuck"})
    assert stuck_dec.get("action") == "retry_with_backoff"
    assert stuck_dec.get("priority") == "high"

    compliance_dec = orchestration_context.route({"kind": "compliance_exhausted"})
    assert compliance_dec.get("action") == "request_hil_decision"
    assert compliance_dec.get("priority") == "critical"

    # Context build check
    ctx = orchestration_context.build(project=TEST_PROJ, limit=10)
    assert isinstance(ctx, dict)
    assert "events" in ctx
    assert "generated_at" in ctx


def test_notification_system_adapter():
    """AC-5: notification_system maintains exact public API signatures."""
    ns = NotificationSystem(project=TEST_PROJ)
    assert ns.get_unread_count() == 0

    notif = ns.send_notification(
        NotificationType.STAGE_COMPLETE,
        title="Stage 1 complete",
        message="Stage finished with 0 defects",
        agent="builder",
        stage=1,
        priority="medium"
    )
    assert notif.notification_id.startswith("NOTIF-")
    assert not notif.read
    assert ns.get_unread_count() == 1

    ns.mark_read(notif.notification_id)
    assert ns.get_unread_count() == 0


def test_alerts_email_adapter():
    """AC-5: alerts.email maintains exact public API signature and never raises."""
    res = alerts.email("Pipeline Alert", "Test body message", priority="critical")
    assert isinstance(res, dict)
    assert "sent" in res
    assert "reason" in res
