"""PFSSOT-P2 (BI-PF-0363): AI + user grooming.

Exercises the deterministic groomer + user decision flow (the AI path reuses the agent runtime and is
covered by the gate with a fallback assertion). No live model needed.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p2"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_guidelines_are_data():
    gl = grooming.guidelines()
    assert gl.get("default_mode") == "ai"          # AI is the default
    assert gl.get("checklist")
    assert {"APPROVE", "MODIFY", "REJECT", "DEFER"}.issubset(set(gl.get("decision_options", [])))


def test_deterministic_groom_then_approve():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Add login API", body="x", tag="TST")["id"]
        r = grooming.groom("project", _PROJ, iid, mode="deterministic")
        assert r["applied"] and r["mode"] == "deterministic"
        b = backlog.get("project", _PROJ, iid)
        assert b["analysis"]["status"] == "IN_PROGRESS"
        assert b["analysis"]["analyzed_by"] == "deterministic"
        assert b["analysis"]["architecture_fit"] in (
            "REUSE", "EXTEND", "MODIFY", "NEW_COMPONENT", "NEW_CAPABILITY", "REFACTOR", "OTHER")
        d = grooming.decide("project", _PROJ, iid, "APPROVE")
        assert d["applied"]
        b2 = backlog.get("project", _PROJ, iid)
        assert b2["analysis"]["status"] == "COMPLETE"
        assert b2["readiness"]["ready"] is True
        assert b2["decisions"] and b2["decisions"][-1]["decision"] == "APPROVE"
    finally:
        _clean()


def test_defer_and_reject_paths():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "T2", tag="TST")["id"]
        grooming.groom("project", _PROJ, iid, mode="deterministic")
        grooming.decide("project", _PROJ, iid, "DEFER")
        assert backlog.get("project", _PROJ, iid)["analysis"]["status"] == "NOT_ANALYZED"
        grooming.groom("project", _PROJ, iid, mode="deterministic")
        grooming.decide("project", _PROJ, iid, "REJECT")
        assert backlog.get("project", _PROJ, iid)["analysis"]["status"] == "STALE"
    finally:
        _clean()


def test_invalid_decision_rejected():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "T3", tag="TST")["id"]
        try:
            grooming.decide("project", _PROJ, iid, "BOGUS")
            raise AssertionError("bad decision should raise")
        except ValueError:
            pass
    finally:
        _clean()
