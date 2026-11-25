"""BI-PF-1466: Gate 1 transition enforcement - pure check() behaviour."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import gate1_transition_check as g  # noqa: E402
import design_contract_check as dcc  # noqa: E402
import ownership_check as own  # noqa: E402
import review_ledger as rl  # noqa: E402
import biis_tier_check as bt  # noqa: E402
import biis_completeness_check as bc  # noqa: E402


def _view(blocking=(), parsed_ok=True):
    sha = "abc"
    return {"review": {"sha": sha}, "dispositions": {}, "total": len(blocking),
            "pending": len(blocking), "blocking": list(blocking), "parsed_ok": parsed_ok}


def _base(monkeypatch, view, pack=None):
    monkeypatch.setattr(g.gp, "baseline_state", lambda _iid: "")
    monkeypatch.setattr(g.dpack, "evaluate", lambda _iid: pack or [])
    monkeypatch.setattr(g, "evaluate", lambda _iid: view)
    monkeypatch.setattr(g.ar, "_get_item", lambda _iid: {"id": "BI-1"})
    monkeypatch.setattr(dcc, "problems", lambda *_a, **_k: [])
    monkeypatch.setattr(own, "problems", lambda *_a, **_k: [])
    monkeypatch.setattr(rl, "problems", lambda *_a, **_k: [])
    monkeypatch.setattr(bt, "problems", lambda *_a, **_k: [])
    monkeypatch.setattr(bc, "problems", lambda *_a, **_k: [])


def test_pending_blocker_fails(monkeypatch):
    _base(monkeypatch, _view([(1, "BLOCKER", "x")]))
    probs = g.check(["BI-1"])
    assert probs and probs[0] == ("BI-1", "PENDING_FINDINGS")


def test_clean_passes(monkeypatch):
    _base(monkeypatch, _view([]))
    monkeypatch.setattr(g.ar, "_get_item", lambda _iid: {"id": "BI-1"})
    monkeypatch.setattr(g.ar, "design_sha", lambda _item: "abc")
    monkeypatch.setattr(g.gp, "approval", lambda *_a, **_k: (True, "OK"))
    assert g.check(["BI-1"]) == []


def test_no_design_review_fails(monkeypatch):
    _base(monkeypatch, None)
    assert g.check(["BI-1"]) == [("BI-1", "NO_EVIDENCE")]


def test_unparsable_fails(monkeypatch):
    _base(monkeypatch, _view([], parsed_ok=False))
    probs = g.check(["BI-1"])
    assert probs == [("BI-1", "UNPARSABLE")]


def test_design_pack_gap_fails(monkeypatch):
    _base(monkeypatch, _view([]), pack=["design_pack.runtime_contract.entrypoint missing"])
    probs = g.check(["BI-1"])
    assert probs == [("BI-1", "DESIGN_PACK: design_pack.runtime_contract.entrypoint missing")]
