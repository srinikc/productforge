"""Review-churn budget tests (BI-PF-1480)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import architect_review as ar  # noqa: E402


def _item(decisions=None, disp=None):
    return {"id": "BI-TEST", "decisions": decisions or [], "review_dispositions": disp or {}}


def _reviews(n, at="2026-01-02T00:00:00+00:00"):
    return [{"path": f"BI-TEST-s{i}.json", "sha": f"s{i}", "at": at} for i in range(n)]


def test_diff_reviews_filters_design_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "EVID", tmp_path)
    (tmp_path / "BI-TEST-a.json").write_text(json.dumps({"mode": "diff", "sha": "a",
                                                         "at": "2026-01-02T00:00:00+00:00"}))
    (tmp_path / "BI-TEST-b.json").write_text(json.dumps({"mode": "design", "sha": "b"}))
    assert [r["sha"] for r in ar.diff_reviews("BI-TEST")] == ["a"]


def test_budget_boundaries(monkeypatch):
    item = _item([{"gate": 1, "at": "2026-01-01T00:00:00+00:00"}])
    for n, warn, fail in [(2, False, False), (3, True, False), (4, True, False), (5, True, True)]:
        monkeypatch.setattr(ar, "diff_reviews", lambda *a, **k: _reviews(n))
        v = ar.churn_verdict("BI-TEST", item)
        assert (v["warn"], v["fail"]) == (warn, fail), (n, v)


def test_gate1_epoch_excludes_earlier_reviews(monkeypatch):
    item = _item([{"gate": 1, "at": "2026-01-02T00:00:00+00:00"}])
    monkeypatch.setattr(ar, "diff_reviews", lambda *a, **k: [
        {"path": "BI-TEST-OLD.json", "sha": "old", "at": "2026-01-01T00:00:00+00:00"}])
    assert ar.churn_verdict("BI-TEST", item)["count"] == 0


def test_hil_attestation_allows_over_budget(monkeypatch):
    item = _item([
        {"gate": 1, "at": "2026-01-01T00:00:00+00:00"},
        {"decision": "REVIEW_CHURN", "by": "hil:srinikc",
         "note": "Accepted extra reviews for the blocker rework; supersedes s4 with a recorded reason."},
    ])
    monkeypatch.setattr(ar, "diff_reviews", lambda *a, **k: _reviews(5))
    v = ar.churn_verdict("BI-TEST", item)
    assert v["attested"] and v["allowed"] and not v["fail"]


def test_attestation_requires_allowlist_and_sha(monkeypatch):
    monkeypatch.setattr(ar, "diff_reviews", lambda *a, **k: _reviews(5))
    for by, note in [("hil:other", "x" * 40 + " s4"), ("hil:srinikc", "no sha here " + "x" * 40)]:
        item = _item([{"gate": 1, "at": "2026-01-01T00:00:00+00:00"},
                      {"decision": "REVIEW_CHURN", "by": by, "note": note}])
        assert ar.churn_verdict("BI-TEST", item)["fail"], (by, note)


def test_review_guard(monkeypatch):
    monkeypatch.setattr(ar, "diff_reviews", lambda *a, **k: _reviews(1))
    item = _item([{"gate": 1, "at": "2026-01-01T00:00:00+00:00"}])
    assert not ar.review_guard("BI-TEST", item, False, "")[0]
    assert not ar.review_guard("BI-TEST", item, True, "")[0]
    assert not ar.review_guard("BI-TEST", item, True, "generic reason")[0]
    ok, why = ar.review_guard("BI-TEST", item, True, "supersedes s0; blocker fix")
    assert ok and "s0" in why
    item["review_dispositions"] = {"diff": {"sig:x": {"status": "ACTIONED"}}}
    assert ar.review_guard("BI-TEST", item, False, "")[0]


def test_redact_reason_then_cap():
    out = ar.redact_reason("token=abc123 supersedes s0")
    assert "abc123" not in out and "token=[REDACTED]" in out
    assert len(ar.redact_reason("x" * 900)) == ar.review_budget()["reason_max_chars"]


def test_bad_budget_config_fails_closed(monkeypatch):
    monkeypatch.setattr(ar, "_config", lambda: {"review_budget": {"warn_after": 4, "fail_after": 2}})
    with pytest.raises(ValueError):
        ar.review_budget()
