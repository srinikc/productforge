"""Gate predicate tests (BI-PF-1469): approval binding, ordering, force, baseline."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import gate_predicates as gp  # noqa: E402


def _view():
    return {"parsed_ok": True, "blocking": [],
            "dispositions": {"sig:a": {"status": "ACTIONED"}, "sig:b": {"status": "DEFERRED"}},
            "review": {"sha": "abc", "at": "2026-01-01T00:00:00+00:00"}}


def _item(**over):
    d = {"gate": 2, "decision": "APPROVE", "by": "hil:test",
         "at": "2026-01-02T00:00:00+00:00", "findings_sha": "abc",
         "findings_digest": gp.findings_digest(_view()), "seq": 1}
    d.update(over)
    return {"decisions": [d]}


def test_allow():
    assert gp.gate2_ready(_item(), "abc", _view()) == (True, "OK")


def test_no_decision():
    assert gp.gate2_ready({"decisions": []}, "abc", _view())[1] == "NO_GATE_APPROVAL"


def test_pending_blocks():
    v = dict(_view(), blocking=["x"])
    assert gp.gate2_ready(_item(), "abc", v)[1] == "PENDING_FINDINGS"


def test_stale_sha():
    assert gp.gate2_ready(_item(), "other", _view())[1] == "STALE_APPROVAL"


def test_stale_ordering():
    it = _item(at="2025-12-31T00:00:00+00:00")
    assert gp.gate2_ready(it, "abc", _view())[1] == "STALE_APPROVAL"


def test_digest_drift():
    it = _item(findings_digest="deadbeef")
    assert gp.gate2_ready(it, "abc", _view())[1] == "STALE_APPROVAL"


def test_unauthorized_approver():
    assert gp.gate2_ready(_item(by="system:auto"), "abc", _view())[1] == "UNAUTHORIZED_APPROVER"


def test_seq_order():
    it = {"decisions": [
        dict(_item()["decisions"][0], seq=2),
        dict(_item()["decisions"][0], seq=1, findings_sha="abc"),
    ]}
    assert gp.gate2_ready(it, "abc", _view())[1] == "DECISION_ORDER_INVALID"


def test_force_requires_env_and_no_ci():
    assert gp.force_allowed({"PF_GATE_FORCE": "1"}) is True
    assert gp.force_allowed({}) is False
    assert gp.force_allowed({"PF_GATE_FORCE": "1", "PF_CI": ""}) is False


def test_docs_only():
    assert gp.is_docs_only(["docs/x.md"], ["docs/**"]) is True
    assert gp.is_docs_only(["core/x.py"], ["docs/**"]) is False


def test_older_valid_decision_is_used():
    view = _view()
    good = _item()["decisions"][0]
    stale = dict(good, findings_sha="zzz", seq=2, at="2026-02-01T00:00:00+00:00")
    it = {"decisions": [good, stale]}
    assert gp.gate2_ready(it, "abc", view) == (True, "OK")


def test_all_stale_reports_stale():
    view = _view()
    d = _item()["decisions"][0]
    it = {"decisions": [dict(d, findings_sha="zzz")]}
    assert gp.gate2_ready(it, "abc", view)[1] == "STALE_APPROVAL"


def test_bookkeeping_tier_runs_delivery_gates():
    src = (ROOT / "scripts" / "dev" / "precheck.py").read_text(encoding="utf-8")
    assert "gate2-completion" in src and "delivery-completeness" in src
    assert 'must = ("compile", "docs-fresh", "gate2-completion", "delivery-completeness")' in src


def test_gate0_allows_empty_open_questions():
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts" / "dev"))
    import gate0_check as g0
    item = {"id": "BI-T", "review": {"reconciliation": {"prior_decisions": ["x"], "existing_path": ["y"],
            "assumptions": ["z"], "divergences": ["d"], "open_questions": []},
            "impact_review": [{"claim": "API CHECK", "verdict": "aligned", "evidence": "e", "recommendation": "r"},
                              {"claim": "AC", "verdict": "aligned", "evidence": "e", "recommendation": "r"},
                              {"claim": "language", "verdict": "aligned", "evidence": "e", "recommendation": "r"}]},
            "api_impact": {"needs_api": False, "reason": "none"}}
    assert g0.problems(item) == []
