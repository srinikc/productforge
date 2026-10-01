"""BI-PF-0277: result aggregator — provenance, evidence merge, conflicts, quorum (bug fix)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import result_aggregator as RA  # noqa: E402


def _c(src, status, conf=0.8, kind="text", out="x", ev=None, issues=None):
    return RA.contribution("agent", src, out, kind=kind, confidence=conf,
                           validation_status=status, evidence=ev or [], unresolved_issues=issues or [])


def test_aggregate_preserves_provenance():
    agg = RA.aggregate([_c("a", "pass"), _c("b", "pass")])
    assert [x["source"] for x in agg["contributions"]] == ["a", "b"]
    assert "timestamp" in agg["contributions"][0]


def test_evidence_merge_dedup_and_corroboration():
    ev = {"claim": "X"}
    agg = RA.aggregate([_c("a", "pass", ev=[ev]), _c("b", "pass", ev=[ev])])
    merged = agg["merged_evidence"]
    assert len(merged) == 1 and merged[0]["corroborated"] is True


def test_conflict_escalates_on_tie():
    agg = RA.aggregate([_c("a", "pass", conf=0.5, out="A"), _c("b", "fail", conf=0.5, out="B")])
    assert agg["conflicts"] and agg["conflicts"][0]["resolution"] == "escalate"


def test_conflict_resolves_by_confidence():
    agg = RA.aggregate([_c("a", "pass", conf=0.9, out="A"), _c("b", "fail", conf=0.2, out="B")])
    assert agg["conflicts"][0]["resolution"] == "chosen"
    assert agg["conflicts"][0]["chosen"] == "a"


def test_quorum_single_pass_does_not_pass():
    # THE BUG: one pass must not pass a review when quorum>=2
    agg = RA.aggregate([_c("a", "pass")], quorum=2)
    assert agg["passed"] is False
    assert agg["consensus"]["reached"] is False


def test_quorum_majority_passes():
    agg = RA.aggregate([_c("a", "pass"), _c("b", "pass"), _c("c", "fail")], quorum=2)
    assert agg["passed"] is True


def test_unresolved_conflict_blocks_pass():
    agg = RA.aggregate([_c("a", "pass", conf=0.5, out="A"), _c("b", "pass", conf=0.5, out="B")], quorum=2)
    assert agg["conflicts"][0]["resolution"] == "escalate"
    assert agg["passed"] is False


def test_multi_model_review_quorum_bug_fixed(monkeypatch):
    from core import multi_model_review as M
    monkeypatch.setattr(M, "_post", lambda rev, prompt: {"verdict": "pass", "issues": [],
                                                         "model": rev.get("model", "m")})
    one = M.review("code", "text", [{"model": "m1"}])
    assert one["passed"] is False  # single pass no longer passes (quorum defaults to 2)
    two = M.review("code", "text", [{"model": "m1"}, {"model": "m2"}])
    assert two["passed"] is True


def test_unknown_status_fails_closed():
    agg = RA.aggregate([RA.contribution("agent", "a", "x"), RA.contribution("agent", "b", "y")], quorum=2)
    assert agg["passed"] is False
    assert agg["validation"]["unknown"] == 2


def test_report_write_and_load(tmp_path):
    agg = RA.aggregate([_c("a", "pass"), _c("b", "pass")], quorum=2)
    RA.write_report(str(tmp_path), agg)
    loaded = RA.load_report(str(tmp_path))
    assert loaded and loaded["passed"] is True
