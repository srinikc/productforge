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
