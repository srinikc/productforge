import os
os.environ.setdefault("API_ALLOW_ANON", "1")
from fastapi.testclient import TestClient
from api.app import app


def test_list_and_upsert_alert_rules():
    client = TestClient(app)
    # List initially empty for new tenant
    r0 = client.get("/api/v1/events/alert-rules", params={"tenant": "tenant-initial"})
    assert r0.status_code == 200
    assert r0.json().get("data", {}).get("count") == 0

    # Upsert rule
    rule_payload = {
        "id": "rule-init-1",
        "tenant_id": "tenant-initial",
        "name": "Stuck Rule",
        "event_types": ["stuck"],
        "min_severity": "medium",
        "channels": ["notify"],
        "throttle_window_seconds": 0,
        "enabled": True,
    }
    r1 = client.post("/api/v1/events/alert-rules", headers={"X-Roles": "operator"}, json=rule_payload)
    assert r1.status_code == 200
    assert r1.json().get("data", {}).get("stored") is True

    # List has 1 rule now
    r2 = client.get("/api/v1/events/alert-rules", params={"tenant": "tenant-initial"})
    assert r2.status_code == 200
    assert r2.json().get("data", {}).get("count") == 1


def test_upsert_and_delete_alert_rule():
    client = TestClient(app)
    rule_payload = {
        "id": "test-ci-fail-rule",
        "tenant_id": "test-tenant-1",
        "name": "CI Failure Alert",
        "event_types": ["ci.failed", "build.error"],
        "min_severity": "high",
        "channels": ["notify", "hil"],
        "throttle_window_seconds": 60,
        "escalate": True,
        "escalate_channel": "hil",
        "enabled": True,
    }

    # Create rule
    r = client.post("/api/v1/events/alert-rules", headers={"X-Roles": "operator"}, json=rule_payload)
    assert r.status_code == 200
    res = r.json().get("data", {})
    assert res.get("stored") is True
    assert res["rule"]["id"] == "test-ci-fail-rule"

    # List rules for tenant
    r_list = client.get("/api/v1/events/alert-rules", params={"tenant": "test-tenant-1"})
    assert r_list.status_code == 200
    t_rules = r_list.json().get("data", {}).get("rules", [])
    assert len(t_rules) == 1
    assert t_rules[0]["id"] == "test-ci-fail-rule"

    # Delete rule
    r_del = client.delete("/api/v1/events/alert-rules/test-ci-fail-rule",
                          headers={"X-Roles": "operator"},
                          params={"tenant": "test-tenant-1"})
    assert r_del.status_code == 200
    assert r_del.json().get("data", {}).get("deleted") is True


def test_upsert_validation_failure():
    client = TestClient(app)
    # Bad severity
    r = client.post("/api/v1/events/alert-rules", headers={"X-Roles": "operator"},
                    json={"name": "Bad Rule", "min_severity": "super-critical"})
    assert r.status_code == 400

    # Negative throttle
    r2 = client.post("/api/v1/events/alert-rules", headers={"X-Roles": "operator"},
                     json={"name": "Bad Rule", "min_severity": "low", "throttle_window_seconds": -5})
    assert r2.status_code == 400


def test_evaluate_policy_and_throttling():
    client = TestClient(app)
    eval_payload = {
        "tenant_id": "tenant-throttle-api",
        "event_type": "service.down",
        "severity": "high",
        "subject": "service-auth-1",
    }
    # First event evaluation: not suppressed, escalated
    r_eval1 = client.post("/api/v1/events/alert-policy/evaluate", json=eval_payload)
    assert r_eval1.status_code == 200
    d1 = r_eval1.json().get("data", {})
    assert d1["matched"] is True
    assert d1["suppressed"] is False
    assert d1["escalated"] is True
    assert "hil" in d1["channels"]

    # Second event evaluation within window: suppressed
    r_eval2 = client.post("/api/v1/events/alert-policy/evaluate", json=eval_payload)
    assert r_eval2.status_code == 200
    d2 = r_eval2.json().get("data", {})
    assert d2["matched"] is True
    assert d2["suppressed"] is True
    assert d2["suppressed_count"] == 1
    assert len(d2["channels"]) == 0
