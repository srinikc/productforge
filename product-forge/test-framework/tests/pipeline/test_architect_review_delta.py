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


def test_design_delta_fields_reports_only_changed_sections():
    previous = {"acceptance_criteria": ["old"], "design_pack": {"test_matrix": [{"ac": "AC-1"}], "scope": ["old"]}}
    current = {"acceptance_criteria": ["new"], "design_pack": {"test_matrix": [{"ac": "AC-1"}, {"ac": "AC-2"}], "scope": ["old"]}}
    delta = ar.design_delta_fields(current, previous)
    assert delta["changed_fields"] == ["acceptance_criteria", "design_pack"]
    assert set(delta["delta"]["design_pack"]) == {"test_matrix"}
    assert delta["delta"]["design_pack"]["test_matrix"][-1]["ac"] == "AC-2"


def test_design_delta_prompt_scopes_to_changed_fields(monkeypatch):
    previous = {"acceptance_criteria": ["old"], "design_pack": {"test_matrix": [{"ac": "AC-1"}]}}
    current = {"acceptance_criteria": ["new"], "design_pack": {"test_matrix": [{"ac": "AC-2"}]}}
    monkeypatch.setattr(ar, "_item_at", lambda base, item_id: previous)
    prompt = ar._build_prompt(current, "BI-PF-1", "design", "abc123")
    assert "DELTA DESIGN REVIEW SCOPE" in prompt
    assert "Changed design fields (authoritative delta)" in prompt
    assert "Do not re-review unchanged" in prompt
    assert "AC-2" in prompt and "AC-1" not in prompt.split("Changed design fields", 1)[1]

def test_delta_review_is_exempt_from_full_review_budget():
    assert ar.is_delta_review("diff", True, "abc123") is True
    assert ar.is_delta_review("diff", False, "") is False
    assert ar.is_delta_review("design", True, "abc123") is False
