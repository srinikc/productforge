"""Execution-trail store + completion gate tests (BI-PF-1481)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

from core import execution_trail as tr  # noqa: E402
import execution_trail_check as chk  # noqa: E402


def test_record_appends_monotonic_events(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    a = tr.record("BI-PF-1481", "planning", "pass", "what/why")
    b = tr.record("BI-PF-1481", "gate0", "pass", "impact")
    assert (a["seq"], b["seq"]) == (1, 2)
    assert [e["stage"] for e in tr.events("BI-PF-1481")] == ["planning", "gate0"]


def test_invalid_item_and_stage_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    with pytest.raises(ValueError):
        tr.record("../x", "gate0")
    with pytest.raises(ValueError):
        tr.record("BI-PF-1481", "nonsense")


def test_redaction_and_summary_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    ev = tr.record("BI-PF-1481", "gate0", "pass", "token=abc123 " + "x" * 3000)
    assert "abc123" not in ev["summary"] and "token=[REDACTED]" in ev["summary"]
    assert len(ev["summary"]) <= tr.MAX_SUMMARY


def test_missing_stages_and_order(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    tr.record("BI-PF-1481", "planning", "pass")
    tr.record("BI-PF-1481", "gate0", "pass")
    missing = tr.missing_stages("BI-PF-1481")
    assert "gate1" in missing and "tests" in missing
    assert tr.order_problems("BI-PF-1481") == []


def test_usage_totals(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    tr.record("BI-PF-1481", "design_review", "pass", usage={"input_tokens": 10, "output_tokens": 5,
                                                            "cached_tokens": 2, "cost_usd": 0.1})
    tr.record("BI-PF-1481", "diff_review", "pass", usage={"not_captured": True})
    u = tr.usage_totals(tr.events("BI-PF-1481"))
    assert (u["input_tokens"], u["output_tokens"], u["cached_tokens"]) == (10, 5, 2)
    assert u["captured"] == 1 and u["not_captured"] == 1


def test_show_renders_stages_tests_and_next(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    monkeypatch.setattr(tr, "_item", lambda i: {"id": i, "title": "A title", "status": "completed",
                                                "epic": "E", "summary": "Shipped it",
                                                "links": {"delivery": {"pr": "7", "merge_sha": "abc"}},
                                                "review_dispositions": {}})
    monkeypatch.setattr(tr, "next_item", lambda i: ("BI-PF-2", "Next thing"))
    tr.record("BI-PF-1481", "gate0", "pass", "impact", tests=[{"command": "pytest x", "result": "pass",
                                                               "duration_ms": 5, "passed": 1}])
    out = tr.show("BI-PF-1481")
    assert "gate0" in out and "pytest x" in out and "| Field" in out
    assert "BI-PF-2" in out and "7 / abc" in out


def test_show_is_one_ordered_flow_with_current_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    monkeypatch.setattr(tr, "_item", lambda i: {
        "id": i, "title": "A title", "status": "in_progress", "epic": "E",
        "objective": "Ship it",
        "brief": {"problem": "the problem", "what_adds": "the change",
                  "why_now": "the reason", "success": "the proof"},
        "review": {"reconciliation": {"prior_decisions": ["ADR-1"],
                                      "assumptions": ["assumption A"]},
                   "impact_review": [{"claim": "API", "verdict": "aligned",
                                      "evidence": "file:1", "recommendation": "approve"}]},
        "decisions": [{"gate": 1, "decision": "APPROVE_WITH_ATTENTION", "by": "hil:x", "at": "now",
                       "note": "design ok"}],
        "links": {}, "review_dispositions": {}})
    monkeypatch.setattr(tr, "next_item", lambda i: ("", ""))
    monkeypatch.setattr(tr, "_review_evidence", lambda i, mode: (f"({mode} table)", "APPROVE"))
    tr.record("BI-PF-1481", "planning", "pass", "plain language")
    tr.record("BI-PF-1481", "gate0", "pass", "impact")
    tr.record("BI-PF-1481", "design_review", "fail", "9 findings")
    tr.record("BI-PF-1481", "design_review", "pass", "0 pending")
    out = tr.show("BI-PF-1481")
    order = ["## 1. Plain language", "## 2. Gate 0", "## 3. Flow", "## 4. Gate 1.5",
             "## 5. Gate 1", "## 6. Implementation", "## 7. Gate 2.5", "## 8. Gate 2",
             "## 9. Tests", "## 10. Usage", "## 11. Final completion", "## Disposition key"]
    assert [out.index(x) for x in order] == sorted(out.index(x) for x in order)
    assert "**Current stage:** gate1" in out
    assert "the problem" in out and "ADR-1" in out and "| API" in out
    assert "APPROVE_WITH_ATTENTION" in out and "**ACTIONED**" in out
    assert "design_review (APPROVE)" in out


def test_current_stage_and_latest_event_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    tr.record("BI-PF-1481", "planning", "pass")
    tr.record("BI-PF-1481", "gate0", "pass")
    assert tr.current_stage("BI-PF-1481") == "design_review"
    tr.record("BI-PF-1481", "design_review", "fail")
    tr.record("BI-PF-1481", "design_review", "pass")
    assert tr.current_stage("BI-PF-1481") == "gate1"
    assert tr._stage_events("BI-PF-1481")["design_review"]["status"] == "pass"


def test_deferred_requires_follow_up_item(monkeypatch):
    item = {"review_dispositions": {"diff": {"sig:a": {"status": "DEFERRED", "note": "later"}}}}
    assert chk.deferred_problems(item)
    import core.backlog as bl
    monkeypatch.setattr(bl, "get_epic", lambda *a, **k: {"id": "BI-PF-1490", "status": "new"})
    item["review_dispositions"]["diff"]["sig:a"]["note"] = "follow-up BI-PF-1490"
    assert chk.deferred_problems(item) == []

def test_concurrent_records_have_unique_monotonic_seq(tmp_path, monkeypatch):
    import threading
    monkeypatch.setattr(tr, "TRAILS", tmp_path)

    def work():
        tr.record("BI-PF-1481", "gate0", "pass", "concurrent")

    threads = [threading.Thread(target=work) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    seqs = sorted(e["seq"] for e in tr.events("BI-PF-1481"))
    assert seqs == list(range(1, 11))


def test_deferred_followup_must_exist(monkeypatch):
    item = {"review_dispositions": {"diff": {"sig:a": {"status": "DEFERRED",
                                                      "note": "follow-up BI-PF-9999"}}}}
    import core.backlog as bl
    monkeypatch.setattr(bl, "get_epic", lambda *a, **k: None)
    assert chk.deferred_problems(item)
    monkeypatch.setattr(bl, "get_epic", lambda *a, **k: {"id": "BI-PF-9999", "status": "new"})
    assert chk.deferred_problems(item) == []

def test_price_usage_mimo():
    u = tr.price_usage({"model": "mimo-v2.6-flash", "input_tokens": 1000, "output_tokens": 500,
                        "cached_tokens": 200})
    assert u["cost_source"] == "opencode-data"
    assert u["cost_usd"] == 0.000253


def test_price_unknown_and_invalid():
    u = tr.price_usage({"model": "unknown-model", "input_tokens": 10, "output_tokens": 1})
    assert u["cost_source"] == "unavailable" and "cost_usd" not in u
    u = tr.price_usage({"model": "mimo-v2.6-flash", "input_tokens": 10, "output_tokens": 1,
                        "cached_tokens": 20})
    assert u["cost_source"] == "invalid_usage" and "cost_usd" not in u


def test_provider_cost_wins():
    u = tr.price_usage({"model": "mimo-v2.6-flash", "input_tokens": 1000, "output_tokens": 500,
                        "cached_tokens": 200, "provider_cost_usd": 0.5})
    assert u["cost_source"] == "provider" and u["cost_usd"] == 0.5


def test_normalize_model_aliases():
    assert tr.normalize_model("xiaomi/mimo-v2.6-flash:latest") == "mimo-v2.6-flash"
    assert tr.normalize_model("deepseek/deepseek-v4.1-flash") == "deepseek-v4.1-flash"
    assert tr.normalize_model("MIMO-V2.6-FLASH") == "mimo-v2.6-flash"


def test_box_table_wraps_long_cells():
    out = tr._box(["A", "B"], [["short", "x" * 100]], widths=[8, 20])
    assert out.startswith("+") and out.rstrip().endswith("+")
    assert out.count("|") > 4


def test_parse_recommendation_realistic_and_formats():
    out = ("Gate 1.5 - Findings & Dispositions (model=mimo-v2.6-flash sha=abc)\n"
           "**Overall architect recommendation: APPROVE**\n"
           "Findings: 9 (BLOCKER 0 / MAJOR 3)\n")
    assert tr._parse_recommendation(out) == "APPROVE"
    assert tr._parse_recommendation("Overall architect recommendation: APPROVE-WITH-ATTENTION") == "APPROVE WITH ATTENTION"
    assert tr._parse_recommendation("Overall architect recommendation: APPROVE / WITH ATTENTION") == "APPROVE WITH ATTENTION"
    assert tr._parse_recommendation("Overall architect recommendation: NOT READY") == "NOT READY"
    assert tr._parse_recommendation("no recommendation here") == ""


def test_show_empty_item_has_explicit_missing_states(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    monkeypatch.setattr(tr, "_item", lambda i: {"id": i, "title": "Empty", "status": "new", "epic": "E",
                                                "objective": "Nothing yet", "links": {},
                                                "review_dispositions": {}})
    monkeypatch.setattr(tr, "next_item", lambda i: ("", ""))
    out = tr.show("BI-PF-1481")
    assert "**Current stage:** planning" in out
    assert "(no events yet)" in out
    assert "Not recorded." in out
    assert "reviewed (recommendation unavailable)" not in out


def test_current_stage_completed_item_is_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    tr.record("BI-PF-1481", "planning", "pass")
    assert tr.current_stage("BI-PF-1481", status="completed") == "complete"
    assert tr.current_stage("BI-PF-1481", status="in_progress") == "gate0"


def test_review_stage_never_falls_back_to_ingest_pass():
    ev = {"status": "fail"}
    assert tr._stage_status("design_review", ev, "", "") == "reviewed (recommendation unavailable)"
    assert tr._stage_status("design_review", ev, "APPROVE", "") == "APPROVE"
    assert tr._stage_status("gate0", ev, "", "") == "fail"


def test_current_stage_blocks_on_failing_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    tr.record("BI-PF-1481", "planning", "pass")
    tr.record("BI-PF-1481", "gate0", "fail")
    assert tr.current_stage("BI-PF-1481", status="in_progress") == "blocked at gate0"


def test_show_keeps_legacy_unknown_stage_events(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    monkeypatch.setattr(tr, "_item", lambda i: {"id": i, "title": "Legacy", "status": "in_progress",
                                                "epic": "E", "links": {}, "review_dispositions": {}})
    monkeypatch.setattr(tr, "next_item", lambda i: ("", ""))
    tr.record("BI-PF-1481", "planning", "pass")
    data = tr._load("BI-PF-1481")
    data["events"].append({"seq": 2, "at": tr._now(), "stage": "legacy_stage", "actor": "tool",
                           "status": "pass", "summary": "old event", "refs": {}, "tests": [],
                           "usage": {}, "duration_ms": 0})
    tr._write("BI-PF-1481", data)
    out = tr.show("BI-PF-1481")
    assert "legacy_stage" in out


def test_review_evidence_missing_and_exception_are_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRAILS", tmp_path)
    assert tr._review_evidence("BI-PF-1481", "design")[0].endswith("no evidence)")
    tr.record("BI-PF-1481", "design_review", "pass", refs={"review_sha": "abc"})
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    table, rec = tr._review_evidence("BI-PF-1481", "design")
    assert "cannot render" in table and rec == ""
