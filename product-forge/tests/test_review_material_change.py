import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import review_budget


def test_material_change_decision_is_required_for_extra_review():
    now = datetime.now(timezone.utc).isoformat()
    rows = [{"mode": "diff", "review_scope": "full_candidate", "at": now}]
    item = {"decisions": [{"decision": "MATERIAL_CHANGE", "mode": "diff", "hil_confirmed": True,
                           "by": "hil:owner", "at": now}]}
    assert review_budget._material_ok(item, "diff", rows)


def test_material_change_without_hil_is_rejected():
    now = datetime.now(timezone.utc).isoformat()
    rows = [{"mode": "diff", "review_scope": "full_candidate", "at": now}]
    item = {"decisions": [{"decision": "MATERIAL_CHANGE", "mode": "diff", "hil_confirmed": False,
                           "by": "hil:owner", "at": now}]}
    assert not review_budget._material_ok(item, "diff", rows)


def test_decisions_api_route_exists():
    from api.app import app
    assert "/api/v1/backlog/items/{item_id}/decisions" in app.openapi()["paths"]


def test_material_change_requires_allowlisted_hil_actor():
    from core.review_decisions import material_change_errors
    body = {"decision": "MATERIAL_CHANGE", "mode": "design", "reason": "x" * 30,
            "hil_confirmed": True, "by": "hil:evil"}
    bad = material_change_errors("BI-PF-1540", body)
    assert any("configured HIL actor" in x for x in bad)


def test_material_change_reason_must_cite_latest_review():
    from core.review_decisions import material_change_errors, latest_review_sha
    sha = latest_review_sha("BI-PF-1540", "design")
    assert sha
    body = {"decision": "MATERIAL_CHANGE", "mode": "design", "reason": "x" * 30,
            "hil_confirmed": True, "by": "hil:owner"}
    assert any("reason must cite" in x for x in material_change_errors("BI-PF-1540", body))
    body["reason"] = "Material change approved after review " + sha
    assert material_change_errors("BI-PF-1540", body) == []


def test_decisions_endpoint_rejects_without_hil(monkeypatch):
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.post("/api/v1/backlog/items/BI-PF-1540/decisions",
               headers={"X-Roles": "operator"},
               json={"decision": "MATERIAL_CHANGE", "mode": "design", "reason": "x" * 30,
                     "hil_confirmed": False, "by": "hil:owner"})
    assert r.status_code == 400


def test_reviewed_ancestor_contract():
    import architect_review
    heads = architect_review._reviewed_heads("BI-PF-1540", "design")
    assert heads
    assert all(len(h) >= 12 for h in heads)


def test_valid_delta_base_requires_reviewed_head_and_ancestor():
    import architect_review
    heads = architect_review._reviewed_heads("BI-PF-1540", "design")
    assert heads
    head = sorted(heads)[0]
    assert architect_review.valid_delta_base("BI-PF-1540", "design", head)
    assert not architect_review.valid_delta_base("BI-PF-1540", "design", "0" * 40)


def test_decisions_endpoint_requires_authentication(monkeypatch):
    monkeypatch.setenv("API_ALLOW_ANON", "0")
    monkeypatch.delenv("PF_API_TOKEN", raising=False)
    monkeypatch.delenv("API_TOKEN", raising=False)
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.post("/api/v1/backlog/items/BI-PF-1540/decisions", json={})
    assert r.status_code == 401


def test_decisions_endpoint_revision_guard_returns_409(monkeypatch):
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.post("/api/v1/backlog/items/BI-PF-1540/decisions",
               headers={"X-Roles": "operator"},
               json={"expected_revision": 0, "decision": "MATERIAL_CHANGE",
                     "mode": "design", "reason": "x" * 30, "hil_confirmed": True,
                     "by": "hil:owner"})
    assert r.status_code == 409


def test_decisions_endpoint_requires_operator_role(monkeypatch):
    monkeypatch.setenv("API_ALLOW_ANON", "0")
    monkeypatch.setenv("PF_API_TOKEN", "tok")
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.post("/api/v1/backlog/items/BI-PF-1540/decisions",
               headers={"Authorization": "Bearer tok"})
    assert r.status_code == 403


def test_decisions_endpoint_persists_append_only(monkeypatch):
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    from core import backlog
    from core.backlog import latest_review_sha
    captured = {}
    def fake_update(scope, project, item_id, **fields):
        captured.update(fields)
        return {"id": item_id, **fields}
    monkeypatch.setattr(backlog, "update", fake_update)
    sha = latest_review_sha("BI-PF-1540", "design")
    c = TestClient(app)
    r = c.post("/api/v1/backlog/items/BI-PF-1540/decisions",
               headers={"X-Roles": "operator"},
               json={"decision": "MATERIAL_CHANGE", "mode": "design",
                     "reason": "Approved after review " + sha,
                     "hil_confirmed": True, "by": "hil:owner"})
    assert r.status_code == 200
    assert captured["decisions"][-1]["decision"] == "MATERIAL_CHANGE"
    assert captured["decisions"][-1]["by"] == "hil:owner"
