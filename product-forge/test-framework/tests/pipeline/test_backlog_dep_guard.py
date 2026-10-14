"""Backlog dependency guard (single writer): invalid deps are dropped, never stored.

self / unknown id / child-depends-on-parent-epic / REQUIRES cycle -> dropped; valid edges kept.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_dep_guard"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _deps(iid):
    return [d["task_id"] for d in (backlog.get("project", _PROJ, iid).get("dependencies") or [])]


def test_guard_drops_self_unknown_parent_epic():
    _clean()
    try:
        parent = backlog.add_epic("project", _PROJ, "Parent", type_="epic")["id"]
        child = backlog.add_epic("project", _PROJ, "Child", epic=parent)["id"]

        backlog.set_dependencies("project", _PROJ, child,
                                 dependencies=[{"task_id": parent, "type": "REQUIRES"}])
        assert _deps(child) == []                       # parent epic dropped

        backlog.set_dependencies("project", _PROJ, child,
                                 dependencies=[{"task_id": child, "type": "REQUIRES"}])
        assert _deps(child) == []                       # self dropped

        backlog.set_dependencies("project", _PROJ, child,
                                 dependencies=[{"task_id": "BI-NOPE-9999", "type": "REQUIRES"}])
        assert _deps(child) == []                       # unknown dropped
    finally:
        _clean()


def test_guard_drops_cycle_keeps_valid():
    _clean()
    try:
        a = backlog.add_epic("project", _PROJ, "A")["id"]
        b = backlog.add_epic("project", _PROJ, "B")["id"]

        backlog.set_dependencies("project", _PROJ, a,
                                 dependencies=[{"task_id": b, "type": "REQUIRES"}])
        assert _deps(a) == [b]

        # b REQUIRES a would form a cycle -> dropped; a's valid edge kept
        backlog.set_dependencies("project", _PROJ, b,
                                 dependencies=[{"task_id": a, "type": "REQUIRES"}])
        assert _deps(b) == []
        assert _deps(a) == [b]
    finally:
        _clean()


def test_guard_keeps_related_and_valid_requires():
    _clean()
    try:
        a = backlog.add_epic("project", _PROJ, "A")["id"]
        b = backlog.add_epic("project", _PROJ, "B")["id"]
        backlog.set_dependencies("project", _PROJ, a, dependencies=[
            {"task_id": b, "type": "RELATED"},
            {"task_id": b, "type": "REQUIRES"},
        ])
        assert _deps(a) == [b, b]
    finally:
        _clean()


def test_blocked_by_replaces_requires_keeps_related_no_stale_edge():
    """BI-PF-1388: `blocked_by` replaces the item's REQUIRES edges (keeps RELATED) and never cycles."""
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "E", type_="epic")["id"]
        a = backlog.add_epic("project", _PROJ, "A", epic=ep)["id"]
        b = backlog.add_epic("project", _PROJ, "B", epic=ep)["id"]
        c = backlog.add_epic("project", _PROJ, "C", epic=ep)["id"]

        # a RELATED c (non-REQUIRES) is preserved across blocked_by changes
        backlog.set_dependencies("project", _PROJ, a, dependencies=[{"task_id": c, "type": "RELATED"}])
        backlog.set_dependencies("project", _PROJ, a, blocked_by=[b])
        by = {(d["task_id"], d["type"]) for d in backlog.get("project", _PROJ, a)["dependencies"]}
        assert (c, "RELATED") in by and (b, "REQUIRES") in by

        # re-setting blocked_by to [c] REPLACES the REQUIRES b edge (the old bug left it stale)
        backlog.set_dependencies("project", _PROJ, a, blocked_by=[c])
        assert backlog.get("project", _PROJ, a)["blocked_by"] == [c]
        reqs_a = {d["task_id"] for d in backlog.get("project", _PROJ, a)["dependencies"]
                  if d["type"] == "REQUIRES"}
        assert reqs_a == {c}                                     # b REQUIRES edge removed; RELATED c kept
        # c REQUIRES a + a REQUIRES c would cycle -> dropped
        backlog.set_dependencies("project", _PROJ, c, blocked_by=[a])
        assert _deps(c) == []
    finally:
        _clean()
