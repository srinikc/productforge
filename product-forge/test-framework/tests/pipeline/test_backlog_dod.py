"""BI-PF-1410: DoD gate - detailed Acceptance Criteria required (write-time + baseline logic)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("API_ALLOW_ANON", "1")

from fastapi.testclient import TestClient  # noqa: E402

from api import auth as _auth  # noqa: E402
from api.app import app  # noqa: E402
from scripts.dev import backlog_dod_check as d  # noqa: E402


def _op() -> dict:
    # Do NOT read the gitignored local token file (data/local/dev-api-token is absent in a clean
    # checkout/CI). Use the SAME token the app computes (env PF_API_TOKEN/API_TOKEN, else the dev token).
    return {"Authorization": f"Bearer {_auth._token()}", "X-Roles": "operator"}


def test_min_ac_is_detailed():
    assert d.MIN_AC >= 40


def test_create_without_ac_rejected():
    r = TestClient(app).post("/api/v1/backlog/items",
                             json={"title": "dod test - no ac", "type": "task"}, headers=_op())
    assert r.status_code == 400


def test_create_with_short_ac_rejected():
    r = TestClient(app).post("/api/v1/backlog/items",
                             json={"title": "dod test - short ac", "type": "task",
                                   "acceptance_criteria": ["too short"]}, headers=_op())
    assert r.status_code == 400


def test_close_without_independent_verification_rejected():
    # BI-PF-1413 closure guard: an item with AC+verification but no verified_by cannot be completed.
    r = TestClient(app).post("/api/v1/backlog/items/BI-PF-1408/status",
                             json={"status": "completed"}, headers=_op())
    assert r.status_code == 400
    assert "verified_by" in (r.json().get("error", {}).get("message") or "")
