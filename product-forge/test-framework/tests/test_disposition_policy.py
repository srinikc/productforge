"""Strict disposition policy: no ACCEPTED; DEFERRED only NIT with HIL approval (BI-PF-1484)."""
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


def test_accepted_is_always_rejected():
    it = _item({"a": {"status": "ACCEPTED", "severity": "MINOR", "note": "x"}})
    it["decisions"] = [_approval(["a"])]
    assert any("ACCEPTED is not allowed" in p for p in dp.problems(it, "diff"))


def test_major_cannot_be_deferred():
    it = _item({"a": {"status": "DEFERRED", "severity": "MAJOR", "note": "later BI-PF-1485"}})
    it["decisions"] = [_approval(["a"])]
    assert any("MAJOR cannot be DEFERRED" in p for p in dp.problems(it, "diff"))


def test_nit_deferred_needs_id_and_approval():
    it = _item({"a": {"status": "DEFERRED", "severity": "NIT", "note": "later"}})
    assert dp.problems(it, "diff")
    it["review_dispositions"]["diff"]["a"]["note"] = "later BI-PF-1485"
    it["decisions"] = [_approval(["a"])]
    assert dp.problems(it, "diff", lambda i: {"id": i}) == []

def test_deferred_cannot_cite_its_own_item():
    it = _item({"a": {"status": "DEFERRED", "severity": "NIT", "note": "later BI-PF-1484"}})
    it["decisions"] = [_approval(["a"])]
    assert any("without an external backlog id" in p for p in dp.problems(it, "diff", lambda i: {"id": i}))
