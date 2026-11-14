"""Regression tests for deterministic fix-guard review selection (BI-PF-1531 flake)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import fix_guard as fg  # noqa: E402
import review_select  # noqa: E402
import architect_review as ar  # noqa: E402


def _review(path: Path, at: str, sha: str):
    path.write_text(json.dumps({"mode": "diff", "at": at, "sha": sha,
                                "findings": {"MAJOR": [], "BLOCKER": []}}), encoding="utf-8")


def test_closed_item_is_not_enforced(tmp_path):
    cfg = {"enforce_from": "2026-01-01", "enforce_items": []}
    assert fg.enforced({"id": "BI-PF-1", "status": "completed",
                        "created_at": "2026-06-01"}, cfg) is False


def test_latest_review_uses_recorded_at_not_mtime(tmp_path, monkeypatch):
    reviews = tmp_path / "engineering" / "reviews"
    reviews.mkdir(parents=True)
    older = reviews / "BI-PF-1-old.json"
    newer = reviews / "BI-PF-1-new.json"
    _review(older, "2026-01-01T00:00:00+00:00", "old")
    _review(newer, "2026-02-01T00:00:00+00:00", "new")
    # Simulate CI checkout order: the older review gets the newer filesystem mtime.
    older.touch()
    monkeypatch.setattr(fg, "ROOT", tmp_path)
    assert fg.latest_review("BI-PF-1")["sha"] == "new"


def test_shared_selector_used_for_reviews(tmp_path):
    reviews = tmp_path / "engineering" / "reviews"
    reviews.mkdir(parents=True)
    _review(reviews / "BI-PF-2-a.json", "2026-01-01T00:00:00Z", "a")
    _review(reviews / "BI-PF-2-b.json", "2026-02-01T00:00:00+00:00", "b")
    assert review_select.latest_review(reviews, "BI-PF-2")["sha"] == "b"


def test_architect_review_uses_shared_selector(tmp_path, monkeypatch):
    reviews = tmp_path / "engineering" / "reviews"
    reviews.mkdir(parents=True)
    _review(reviews / "BI-PF-3-a.json", "2026-01-01T00:00:00Z", "a")
    _review(reviews / "BI-PF-3-b.json", "2026-02-01T00:00:00+00:00", "b")
    monkeypatch.setattr(ar, "EVID", reviews)
    assert ar._latest_review("BI-PF-3", "diff")["sha"] == "b"


def test_selector_normalizes_timestamps_and_skips_malformed(tmp_path):
    reviews = tmp_path / "engineering" / "reviews"
    reviews.mkdir(parents=True)
    (reviews / "BI-PF-4-bad.json").write_text("{not-json", encoding="utf-8")
    _review(reviews / "BI-PF-4-a.json", "2026-01-01T00:00:00Z", "a")
    _review(reviews / "BI-PF-4-b.json", "2026-02-01T00:00:00+00:00", "b")
    assert review_select.latest_review(reviews, "BI-PF-4")["sha"] == "b"


def test_missing_at_uses_mtime_and_reports_fallback(tmp_path):
    reviews = tmp_path / "engineering" / "reviews"
    reviews.mkdir(parents=True)
    legacy = reviews / "BI-PF-5-legacy.json"
    legacy.write_text(json.dumps({"mode": "diff", "sha": "legacy",
                                  "findings": {"MAJOR": [], "BLOCKER": []}}), encoding="utf-8")
    meta = {}
    assert review_select.latest_review(reviews, "BI-PF-5", meta=meta)["sha"] == "legacy"
    assert meta["mtime_fallback"] is True


def test_closed_status_authority_covers_all_closed_values():
    for status in ("completed", "closed", "done", "delivered", "duplicate",
                   "rejected", "wontfix", "archived"):
        assert review_select.is_closed(status) is True, status
    for status in ("new", "in_progress", "executing", "wait", "blocked"):
        assert review_select.is_closed(status) is False, status


def test_fix_guard_problems_threads_meta(monkeypatch):
    def fake(_iid, meta=None):
        if meta is not None:
            meta["mtime_fallback"] = True
        return {"mode": "diff", "findings": {"BLOCKER": [], "MAJOR": []}}
    monkeypatch.setattr(fg, "latest_review", fake)
    meta = {}
    assert fg.problems({"id": "BI-PF-6", "status": "new", "created_at": "2026-01-01"}, {"enforce_from": "2020-01-01"}, meta=meta) == []
    assert meta["mtime_fallback"] is True
