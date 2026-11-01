"""BI-PF-1485 AC1: delta-only review binding and data-only invalidation rule."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import architect_review as ar  # noqa: E402


def test_data_only_delta_keeps_prior_review_current(monkeypatch):
    monkeypatch.setattr(ar, "_latest_review_sha", lambda item_id, mode: "abc123")
    monkeypatch.setattr(ar, "has_review_changes", lambda base="": False)
    assert ar.review_is_current("BI-PF-1", "diff") is True


def test_relevant_delta_requires_a_new_review(monkeypatch):
    monkeypatch.setattr(ar, "_latest_review_sha", lambda item_id, mode: "abc123")
    monkeypatch.setattr(ar, "has_review_changes", lambda base="": True)
    assert ar.review_is_current("BI-PF-1", "diff") is False


def test_no_prior_review_is_not_current(monkeypatch):
    monkeypatch.setattr(ar, "_latest_review_sha", lambda item_id, mode: "")
    assert ar.review_is_current("BI-PF-1", "diff") is False
