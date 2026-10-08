"""BI-PF-0422: assignments view + claim-time dedup guard (near-duplicates run at most once)."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming, job_manager  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_assignment_dedup"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _seed(title: str) -> str:
    iid = backlog.add_epic("project", _PROJ, title, body=title, tag="TST")["id"]
    grooming.decide("project", _PROJ, iid, "APPROVE")
    return iid


def test_near_duplicate_is_not_run_twice():
    _clean()
    try:
        _seed("add a csv export button to the reports dashboard")
        _seed("add csv export button to reports dashboard")   # near-duplicate
        assert job_manager.claim_next("project", _PROJ, worker="w1")["claimed"] is True
        r2 = job_manager.claim_next("project", _PROJ, worker="w2")
        assert r2["claimed"] is False, r2        # the near-duplicate is skipped, not run
    finally:
        _clean()


def test_distinct_items_are_both_claimable():
    _clean()
    try:
        _seed("add csv export to the reports page")
        _seed("fix login timeout on mobile clients")
        assert job_manager.claim_next("project", _PROJ, worker="w1")["claimed"] is True
        assert job_manager.claim_next("project", _PROJ, worker="w2")["claimed"] is True
    finally:
        _clean()


def test_assignments_view_lists_active(monkeypatch):
    _clean()
    try:
        _seed("do a distinct thing")
        job_manager.claim_next("project", _PROJ, worker="WRK-X")
        monkeypatch.setenv("API_ALLOW_ANON", "1")
        from fastapi.testclient import TestClient
        from api.app import app
        client = TestClient(app)
        r = client.get(f"/api/v1/engineering/assignments?scope=project&project={_PROJ}")
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["count"] == 1, data
        assert data["assignments"][0]["worker_id"] == "WRK-X", data
        assert data["assignments"][0]["lease_expires_at"], data
    finally:
        _clean()
