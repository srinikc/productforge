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
    assert "| 1 | gate0 | pass |" in out
    assert "| pytest x | pass |" in out
    assert "BI-PF-2" in out and "| 7 | abc |" in out


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
