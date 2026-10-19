"""BI-PF-1466: Gate 1 transition enforcement - pure check() behaviour."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import gate1_transition_check as g  # noqa: E402


def _view(blocking=(), parsed_ok=True):
    return {"review": {}, "dispositions": {}, "total": len(blocking), "pending": len(blocking),
            "blocking": list(blocking), "parsed_ok": parsed_ok}


def test_pending_blocker_fails():
    probs = g.check(["BI-1"], gate_view=lambda i, m="design": _view([(1, "BLOCKER", "x")]))
    assert probs and probs[0][0] == "BI-1"


def test_clean_passes():
    assert g.check(["BI-1"], gate_view=lambda i, m="design": _view([])) == []


def test_no_design_review_is_grandfathered():
    assert g.check(["BI-1"], gate_view=lambda i, m="design": None) == []


def test_unparsable_fails():
    probs = g.check(["BI-1"], gate_view=lambda i, m="design": _view([], parsed_ok=False))
    assert probs and "parsed" in probs[0][1].lower()
