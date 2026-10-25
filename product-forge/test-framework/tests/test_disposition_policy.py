"""Disposition cap + HIL approval policy (BI-PF-1484)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import disposition_policy as dp  # noqa: E402


def _item(rows, decisions=None):
    return {"review_dispositions": {"diff": rows}, "decisions": decisions or []}


def test_two_accepted_without_approval_fails():
    it = _item({"a": {"status": "ACCEPTED", "note": "x"}, "b": {"status": "ACCEPTED", "note": "y"}})
    assert dp.problems(it, "diff")


def test_two_accepted_with_approval_passes():
    it = _item({"a": {"status": "ACCEPTED", "note": "x"}, "b": {"status": "ACCEPTED", "note": "y"}})
    it["decisions"] = [{"decision": "DISPOSITION_APPROVAL", "hil_confirmed": True,
                        "scope": "disposition_approval", "mode": "diff", "sigs": ["a", "b"]}]
    assert dp.problems(it, "diff") == []


def test_three_accepted_fails_even_with_approval():
    it = _item({k: {"status": "ACCEPTED", "note": "x"} for k in ("a", "b", "c")})
    it["decisions"] = [{"decision": "DISPOSITION_APPROVAL", "hil_confirmed": True,
                        "scope": "disposition_approval", "mode": "diff", "sigs": ["a", "b", "c"]}]
    assert any("exceeds cap" in p for p in dp.problems(it, "diff"))


def test_deferred_needs_id_and_approval():
    it = _item({"a": {"status": "DEFERRED", "note": "later"}})
    assert dp.problems(it, "diff")
    it["review_dispositions"]["diff"]["a"]["note"] = "later BI-PF-1484"
    it["decisions"] = [{"decision": "DISPOSITION_APPROVAL", "hil_confirmed": True,
                        "scope": "disposition_approval", "mode": "diff", "sigs": ["a"]}]
    assert dp.problems(it, "diff", lambda i: {"id": i}) == []
