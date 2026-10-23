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
