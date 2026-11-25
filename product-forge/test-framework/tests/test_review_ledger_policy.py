"""Review ledger: only full reviews consume budget; delta reviews must chain."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import review_ledger as rl  # noqa: E402


def _item(*entries):
    return {"id": "BI-PF-1", "review_ledger": list(entries)}


def _full(head="a", sha="f1"):
    return {"mode": "diff", "review_scope": "full_candidate", "review_sha": sha, "head_sha": head}


def _delta(base, head, sha):
    return {"mode": "diff", "review_scope": "delta", "base_sha": base, "head_sha": head, "review_sha": sha}


def test_full_plus_delta_does_not_exceed_budget():
    it = _item(_full("a"), _delta("a", "b", "d1"), _delta("b", "c", "d2"))
    assert rl.problems(it, "diff", 1) == []
    assert rl.chain_problems(it, "diff") == []


def test_delta_without_full_is_rejected():
    it = _item(_delta("a", "b", "d1"))
    assert rl.chain_problems(it, "diff")


def test_delta_with_unknown_base_is_rejected():
    it = _item(_full("a"), _delta("b", "c", "d1"))
    assert rl.chain_problems(it, "diff")


def test_two_full_reviews_require_material_approval():
    it = _item(_full("a", "f1"), _full("b", "f2"))
    assert rl.problems(it, "diff", 1)
    it["decisions"] = [{"decision": "MATERIAL_CHANGE", "hil_confirmed": True,
                        "mode": "diff", "at": "2099-01-01T00:00:00+00:00"}]
    assert rl.problems(it, "diff", 1) == []
