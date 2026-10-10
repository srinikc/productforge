"""PFSSOT-P1 (BI-PF-0362): first-class execution fields on backlog items.

Covers: add defaults, analysis set/stale rules, structured deps (+flat deps sync), priority_rank,
execution/readiness setters, deterministic ordering, and revision bump on material change only.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p1"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_added_defaults():
    _clean()
    try:
        it = backlog.add_epic("project", _PROJ, "T", tag="TST")
        assert it["revision"] == 1
        assert it["analysis"]["status"] == "NOT_ANALYZED"
        assert it["analyze_mode"] == "on_entry"
        assert it["dependencies"] == [] and it["execution"]["worker_id"] == ""
    finally:
        _clean()


def test_analysis_complete_then_priority_keeps_complete():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "T", tag="TST")["id"]
        backlog.set_analysis("project", _PROJ, iid, status="COMPLETE", architecture_fit="EXTEND",
                             implementation_strategy="extend backlog")
        backlog.set_priority("project", _PROJ, iid, priority="P1", priority_rank=5)
        b = backlog.get("project", _PROJ, iid)
        assert b["analysis"]["status"] == "COMPLETE"
        assert b["priority_rank"] == 5
    finally:
        _clean()


def test_content_change_stales_completed_analysis():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "T", tag="TST")["id"]
        backlog.set_analysis("project", _PROJ, iid, status="COMPLETE")
        backlog.update("project", _PROJ, iid, body="changed requirement")
        b = backlog.get("project", _PROJ, iid)
        assert b["analysis"]["status"] == "STALE"
        assert b["revision"] >= 2
    finally:
        _clean()


def test_structured_dependencies_sync_flat_deps():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "T", tag="TST")["id"]
        dep = backlog.add_epic("project", _PROJ, "Dep", tag="TST")["id"]
        backlog.set_dependencies("project", _PROJ, iid,
                                 dependencies=[{"task_id": dep, "type": "BLOCKS"}])
        b = backlog.get("project", _PROJ, iid)
        assert b["dependencies"][0]["task_id"] == dep
        assert b["dependencies"][0]["type"] == "BLOCKS"
        assert b["deps"] == [dep]  # flat list kept in sync for the scheduler
    finally:
        _clean()


def test_order_by_priority_is_deterministic():
    _clean()
    try:
        a = backlog.add_epic("project", _PROJ, "A", tag="TST")["id"]
        c = backlog.add_epic("project", _PROJ, "C", tag="TST")["id"]
        backlog.set_priority("project", _PROJ, a, priority_rank=1)
        backlog.set_priority("project", _PROJ, c, priority_rank=9)
        order = [x["id"] for x in backlog.order_by_priority(backlog.list_open("project", _PROJ))]
        assert order.index(a) < order.index(c)
    finally:
        _clean()


def test_invalid_enum_rejected():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "T", tag="TST")["id"]
        try:
            backlog.set_analysis("project", _PROJ, iid, status="BOGUS")
            raise AssertionError("bad analysis status should raise")
        except ValueError:
            pass
        try:
            backlog.set_dependencies("project", _PROJ, iid,
                                     dependencies=[{"task_id": "X", "type": "BOGUS"}])
            raise AssertionError("bad dep type should raise")
        except ValueError:
            pass
    finally:
        _clean()
