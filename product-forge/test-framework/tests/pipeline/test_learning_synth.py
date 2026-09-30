"""BI-PF-0293: evidence-gated learning pipeline (no evidence -> no candidate; approve -> owner store)."""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import learning_synth as ls  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_learnsynth"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)
    # clear candidate store so tests are independent
    try:
        if os.path.exists(ls.STORE):
            os.remove(ls.STORE)
    except Exception:
        pass


def test_no_evidence_no_candidate():
    _clean()
    assert ls.propose(_pdir(), _PROJECT) == []
    _clean()


def test_propose_from_a_closed_rcca_then_approve_applies_to_learnings():
    _clean()
    os.makedirs(_pdir(), exist_ok=True)
    # create a closed issue with a generalized RCCA (evidence source)
    from core import issues as I
    it = I.raise_issue("project", _PROJECT, "scratch defect for learning",
                       kind="bug", priority="P1", module="core/x.py")
    I.set_rcca("project", _PROJECT, it["id"], root_cause="rc", corrective="co",
               fixed_where="core/x.py", preventive="always validate media before publish",
               generalized=True)
    I.set_status("project", _PROJECT, it["id"], "closed")

    created = ls.propose(_pdir(), _PROJECT)
    assert created, "expected a candidate from the closed RCCA"
    c = created[0]
    assert c["status"] == "proposed"
    assert c["evidence"] and c["scope"].startswith("project:")

    # reject changes nothing in learnings
    from core import learnings as L
    before = len(L.all_learnings())
    ls.reject(c["id"], by="test")
    assert len(L.all_learnings()) == before

    # approve applies into the OWNER store (learnings)
    r = ls.approve(c["id"], by="test")
    assert r["ok"] and r["candidate"]["status"] == "approved"
    after = L.all_learnings()
    assert len(after) >= before
    assert any("validate media before publish" in (l.get("rule") or "") for l in after)
    _clean()


def test_effectiveness_counts():
    _clean()
    eff = ls.effectiveness()
    assert set(("approved", "rejected", "proposed", "applied")).issubset(eff.keys())
    _clean()
