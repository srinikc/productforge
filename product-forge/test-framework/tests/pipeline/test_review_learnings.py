"""BI-PF-1449: review-findings learning loop - signature, aggregation, capture detection."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import review_learnings as rl  # noqa: E402


def _review(item, findings, mode="diff"):
    return {"item": item, "mode": mode, "file": f"{item}.json", "findings": findings}


def test_signature_normalises_and_is_stable():
    a = rl.signature("**Rollback is not actually reversible.** `up.sql` drops audit_legacy.")
    b = rl.signature("Rollback is not actually reversible. drops audit_legacy.")
    assert a == b
    assert len(rl.digest("x")) == 16


def test_aggregate_counts_and_ignores_none():
    reviews = [
        _review("BI-1", {"BLOCKER": ["none"], "MAJOR": ["No tests planned."], "MINOR": [], "NIT": []}),
        _review("BI-2", {"BLOCKER": ["No tests planned."], "MAJOR": [], "MINOR": [], "NIT": []}),
    ]
    agg = rl.aggregate(reviews)
    assert agg["reviews"] == 2
    assert agg["severity"] == {"MAJOR": 1, "BLOCKER": 1}
    assert sum(v["count"] for v in agg["signatures"].values()) == 2
    assert rl.recurring(agg, 2) and rl.recurring(agg, 2)[0][1]["count"] == 2


def test_unresolved_respects_ledger_digest():
    reviews = [
        _review("BI-1", {"MAJOR": ["Reuse the existing owner"], "BLOCKER": [], "MINOR": [], "NIT": []}),
        _review("BI-2", {"MAJOR": ["Reuse the existing owner"], "BLOCKER": [], "MINOR": [], "NIT": []}),
    ]
    agg = rl.aggregate(reviews)
    d = rl.digest("Reuse the existing owner")
    assert [(k, v) for k, v in rl.unresolved(agg, set(), 2)][0][0] == d
    assert rl.unresolved(agg, {d}, 2) == []


def test_load_reviews_reads_committed_evidence_json(tmp_path):
    import json
    review_name = "BI-X-abc" + ".json"
    (tmp_path / review_name).write_text(json.dumps({
        "item": "BI-X", "mode": "design", "sha": "abc",
        "findings": {"BLOCKER": [], "MAJOR": ["m"], "MINOR": [], "NIT": [], "SUMMARY": ["s"]},
    }), encoding="utf-8")
    (tmp_path / ("not-a-review" + ".json")).write_text("{}", encoding="utf-8")
    rs = rl.load_reviews(tmp_path)
    assert len(rs) == 1 and rs[0]["item"] == "BI-X"
