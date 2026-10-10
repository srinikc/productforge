"""BI-PF-1250: every item belongs to an epic - suggest/auto/Unscoped + coverage warning + gate baseline."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_epic_rule"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_unscoped_epic_is_holding_and_idempotent():
    _clean()
    try:
        uid = backlog.ensure_unscoped_epic("project", _PROJ)
        e = backlog.get_epic("project", _PROJ, uid)
        assert backlog.is_epic(e) and e.get("holding") is True
        assert backlog.ensure_unscoped_epic("project", _PROJ) == uid  # idempotent
    finally:
        _clean()


def test_auto_epic_prefers_a_matching_epic():
    _clean()
    try:
        e = backlog.add_epic("project", _PROJ, "Payment Gateway", type_="epic", tag="TST")
        assert backlog.auto_epic("project", _PROJ, "payment gateway integration work") == e["id"]
    finally:
        _clean()


def test_auto_epic_falls_back_to_unscoped():
    _clean()
    try:
        eid = backlog.auto_epic("project", _PROJ, "zzz qqq unrelated nothing")
        assert backlog.is_holding_epic(backlog.get_epic("project", _PROJ, eid))
    finally:
        _clean()


def test_epic_coverage_flags_unparented_item():
    _clean()
    try:
        backlog.add_epic("project", _PROJ, "orphan item", tag="TST")
        warns = backlog.epic_coverage_warnings("project", _PROJ)
        assert any(w.get("title") == "orphan item" for w in warns)
    finally:
        _clean()


def test_unscoped_children_lists_suggestions():
    _clean()
    try:
        backlog.add_epic("project", _PROJ, "Export", type_="epic", tag="TST")
        uid = backlog.ensure_unscoped_epic("project", _PROJ)
        backlog.add_epic("project", _PROJ, "Export CSV", epic=uid, tag="TST")
        kids = backlog.unscoped_children("project", _PROJ)
        assert kids and kids[0]["item"]
    finally:
        _clean()


def test_move_to_epic_rehomes_and_syncs_both():
    _clean()
    try:
        uid = backlog.ensure_unscoped_epic("project", _PROJ)
        real = backlog.add_epic("project", _PROJ, "Real Epic", type_="epic", tag="TST")
        child = backlog.add_epic("project", _PROJ, "child", epic=uid, tag="TST")["id"]
        r = backlog.move_to_epic("project", _PROJ, child, real["id"])
        assert r["ok"] and r["epic"] == real["id"]
        assert str(backlog.get_epic("project", _PROJ, child).get("epic")) == real["id"]
        assert child in (backlog.get_epic("project", _PROJ, real["id"]).get("children") or [])
        assert child not in (backlog.get_epic("project", _PROJ, uid).get("children") or [])
    finally:
        _clean()


def test_move_to_epic_rejects_bad_target():
    _clean()
    try:
        c = backlog.add_epic("project", _PROJ, "c", tag="TST")["id"]
        assert backlog.move_to_epic("project", _PROJ, c, "NOPE")["ok"] is False
    finally:
        _clean()


def test_unscoped_aging_fresh_item_not_flagged():
    _clean()
    try:
        uid = backlog.ensure_unscoped_epic("project", _PROJ)
        backlog.add_epic("project", _PROJ, "fresh", epic=uid, tag="TST")
        assert backlog.unscoped_aging("project", _PROJ, 14) == []
    finally:
        _clean()
