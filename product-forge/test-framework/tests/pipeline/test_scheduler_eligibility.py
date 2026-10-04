"""PFSSOT-P4 (BI-PF-0365): scheduler eligibility over the canonical backlog (read-only)."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming, scheduler  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p4"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _approve(iid):
    grooming.groom("project", _PROJ, iid, mode="deterministic")
    grooming.decide("project", _PROJ, iid, "APPROVE")


def test_analysis_gate_blocks_until_complete():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Feature A", tag="TST")["id"]
        e = scheduler.eligible(backlog.get("project", _PROJ, iid))
        assert e["ok"] is False
        assert any("analysis" in r for r in e["reasons"])
        _approve(iid)
        assert scheduler.eligible(backlog.get("project", _PROJ, iid))["ok"] is True
    finally:
        _clean()


def test_dependency_blocks_then_unblocks():
    _clean()
    try:
        a = backlog.add_epic("project", _PROJ, "Feature A", tag="TST")["id"]
        _approve(a)
        b = backlog.add_epic("project", _PROJ, "Feature B", tag="TST")["id"]
        backlog.set_dependencies("project", _PROJ, b, dependencies=[{"task_id": a, "type": "BLOCKS"}])
        _approve(b)
        by = {a: backlog.get("project", _PROJ, a), b: backlog.get("project", _PROJ, b)}
        assert scheduler.eligible(by[b], by_id=by)["ok"] is False   # a not terminal
        backlog.set_status("project", _PROJ, a, "completed")
        by = {a: backlog.get("project", _PROJ, a), b: backlog.get("project", _PROJ, b)}
        assert scheduler.eligible(by[b], by_id=by)["ok"] is True    # a done -> eligible
    finally:
        _clean()


def test_next_eligible_picks_highest_priority():
    _clean()
    try:
        lo = backlog.add_epic("project", _PROJ, "Low", tag="TST")["id"]
        hi = backlog.add_epic("project", _PROJ, "High", tag="TST")["id"]
        _approve(lo)
        _approve(hi)
        backlog.set_priority("project", _PROJ, lo, priority_rank=9)
        backlog.set_priority("project", _PROJ, hi, priority_rank=1)
        assert scheduler.next_eligible("project", _PROJ)["item"] == hi
    finally:
        _clean()


def test_terminal_item_not_eligible():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Done", tag="TST")["id"]
        backlog.set_status("project", _PROJ, iid, "completed")
        # completed is terminal -> not in list_open; eligible() still flags terminal
        e = scheduler.eligible(backlog.get("project", _PROJ, iid) or {"id": iid, "status": "completed"})
        assert e["ok"] is False
    finally:
        _clean()
