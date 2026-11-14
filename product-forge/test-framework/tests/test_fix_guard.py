"""Regression tests for deterministic fix-guard review selection (BI-PF-1531 flake)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import fix_guard as fg  # noqa: E402
import review_select  # noqa: E402


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
