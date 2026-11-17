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
