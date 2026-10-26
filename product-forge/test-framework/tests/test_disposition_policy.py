"""Disposition policy: max 2 HIL exceptions per mode; BLOCKER never; DEFERRED needs id."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import disposition_policy as dp  # noqa: E402


def _item(rows, decisions=None):
    return {"id": "BI-PF-1484", "review_dispositions": {"diff": rows}, "decisions": decisions or []}


def _approval(sigs):
    return {"decision": "DISPOSITION_APPROVAL", "hil_confirmed": True, "by": "hil:test",
            "scope": "disposition_approval", "mode": "diff", "sigs": sigs}


def test_two_accepted_with_approval_pass():
    it = _item({"a": {"status": "ACCEPTED", "severity": "MINOR", "note": "x"},
                "b": {"status": "ACCEPTED", "severity": "MAJOR", "note": "y"}})
    it["decisions"] = [_approval(["a", "b"])]
    assert dp.problems(it, "diff") == []


def test_three_exceptions_fail():
    it = _item({k: {"status": "ACCEPTED", "severity": "MINOR", "note": "x"} for k in ("a", "b", "c")})
    it["decisions"] = [_approval(["a", "b", "c"])]
    assert any("exceeds max 2" in p for p in dp.problems(it, "diff"))


def test_accepted_without_hil_fails():
    it = _item({"a": {"status": "ACCEPTED", "severity": "MINOR", "note": "x"}})
    assert any("without HIL" in p for p in dp.problems(it, "diff"))


def test_blocker_cannot_be_exception():
    it = _item({"a": {"status": "ACCEPTED", "severity": "BLOCKER", "note": "x"}})
    it["decisions"] = [_approval(["a"])]
    assert any("BLOCKER cannot" in p for p in dp.problems(it, "diff"))


def test_deferred_needs_id_and_approval():
    it = _item({"a": {"status": "DEFERRED", "severity": "MAJOR", "note": "later"}})
    assert dp.problems(it, "diff")
    it["review_dispositions"]["diff"]["a"]["note"] = "later BI-PF-1485"
    it["decisions"] = [_approval(["a"])]
    assert dp.problems(it, "diff", lambda i: {"id": i}) == []


def test_deferred_cannot_cite_its_own_item():
    it = _item({"a": {"status": "DEFERRED", "severity": "NIT", "note": "later BI-PF-1484"}})
    it["decisions"] = [_approval(["a"])]
    assert any("without an external backlog id" in p for p in dp.problems(it, "diff", lambda i: {"id": i}))
