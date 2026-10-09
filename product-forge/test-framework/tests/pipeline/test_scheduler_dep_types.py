"""Scheduler dependency handling: completed deps are met; RELATED never blocks (scheduler bug fix).

Root cause: the dependency map was built from OPEN items only, so a dep on a COMPLETED item read as unmet;
and `eligible` blocked on every dependency type including advisory RELATED.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import scheduler  # noqa: E402


def _item(iid, status="new", deps=None):
    it = {"id": iid, "status": status, "analysis": {"status": "COMPLETE"}, "title": iid}
    if deps is not None:
        it["dependencies"] = deps
    return it


def test_requires_on_completed_is_met():
    a = _item("A", deps=[{"task_id": "B", "type": "REQUIRES", "required_state": "completed"}])
    b = _item("B", status="completed")
    assert scheduler.eligible(a, by_id={"A": a, "B": b})["ok"] is True


def test_requires_on_open_blocks():
    a = _item("A", deps=[{"task_id": "B", "type": "REQUIRES"}])
    b = _item("B", status="new")
    assert scheduler.eligible(a, by_id={"A": a, "B": b})["ok"] is False


def test_related_never_blocks():
    a = _item("A", deps=[{"task_id": "B", "type": "RELATED"}])
    b = _item("B", status="new")
    assert scheduler.eligible(a, by_id={"A": a, "B": b})["ok"] is True


def test_unknown_dep_blocks_fail_closed():
    a = _item("A", deps=[{"task_id": "NOPE", "type": "REQUIRES"}])
    assert scheduler.eligible(a, by_id={"A": a})["ok"] is False
