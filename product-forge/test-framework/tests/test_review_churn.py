"""Review-churn budget tests (BI-PF-1480)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import architect_review as ar  # noqa: E402
import review_churn_check as rc  # noqa: E402


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
        {"decision": "REVIEW_CHURN", "by": "hil:srinikc", "hil_confirmed": True,
         "note": "Accepted extra reviews for the blocker rework; supersedes s4 with a recorded reason."},
    ])
    monkeypatch.setattr(ar, "diff_reviews", lambda *a, **k: _reviews(5))
    v = ar.churn_verdict("BI-TEST", item)
    assert v["attested"] and v["allowed"] and not v["fail"]


def test_attestation_requires_allowlist_and_sha(monkeypatch):
    monkeypatch.setattr(ar, "diff_reviews", lambda *a, **k: _reviews(5))
    for by, note, confirmed in [("agent:self", "x" * 40 + " s4", True),
                                ("hil:srinikc", "no sha here " + "x" * 40, True),
                                ("hil:srinikc", "x" * 40 + " s4", False)]:
        item = _item([{"gate": 1, "at": "2026-01-01T00:00:00+00:00"},
                      {"decision": "REVIEW_CHURN", "by": by, "note": note, "hil_confirmed": confirmed}])
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

def test_reason_flag_requires_rereview():
    assert ar.reason_flag_error(False, "why") == "--reason requires --rereview"
    assert ar.reason_flag_error(True, "why") == ""
    assert ar.reason_flag_error(False, "") == ""


def test_cli_exit_codes_json_and_report(monkeypatch, capsys):
    monkeypatch.setattr(ar, "_git_text", lambda args: "base-sha")
    monkeypatch.setattr(rc.g2, "transitions", lambda base: ["BI-X"])
    row = {"item": "BI-X", "count": 5, "warn": True, "fail": True, "allowed": False,
           "attested": False, "warn_after": 2, "fail_after": 4, "latest_sha": "s4",
           "epoch": "2026-01-01", "reviews": []}
    monkeypatch.setattr(rc, "evaluate", lambda ids: [row])
    assert rc.main(["--report"]) == 0
    assert rc.main([]) == 1
    capsys.readouterr()
    assert rc.main(["--json"]) == 1
    out = capsys.readouterr().out
    assert '"ok": false' in out and '"item": "BI-X"' in out

    monkeypatch.setattr(ar, "_git_text", lambda args: "")
    assert rc.main([]) == 2

    monkeypatch.setattr(ar, "_git_text", lambda args: "base")
    monkeypatch.setattr(rc.g2, "transitions", lambda base: (_ for _ in ()).throw(RuntimeError("git boom")))
    assert rc.main([]) == 2


def test_corrupt_evidence_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "EVID", tmp_path)
    (tmp_path / "BI-TEST-bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        ar.diff_reviews("BI-TEST")


def test_redact_url_and_pem():
    assert "user:pass" not in ar.redact_reason("see https://user:pass@host/x")
    pem = "-----BEGIN KEY-----\nsecret\n-----END KEY-----"
    assert "secret" not in ar.redact_reason(pem)
