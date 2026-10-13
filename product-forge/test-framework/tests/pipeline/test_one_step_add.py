"""BI-PF-1282: a FIRST add leaves the item worker-claimable (epic assigned, groomed+approved, ordered)."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, scheduler  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_one_step_add"
_BODY = ("## Problem / why\nnothing works\n## Goal\nadd a hello endpoint\n## In scope\nthe route\n"
         "## Acceptance criteria\nGET /hello returns 200\n## Approach\nadd a handler\n")


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_add_autogrooms_and_is_claimable():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "add a hello endpoint", body=_BODY, tag="TST")["id"]
        cur = backlog.get_epic("project", _PROJ, iid)
        # 1. epic auto-assigned (best match else the Unscoped holding epic) - never left epic-less
        assert cur.get("epic"), "item has no epic after add"
        assert backlog.is_epic(backlog.get_epic("project", _PROJ, cur["epic"]))
        # 2. groomed AND auto-approved -> analysis COMPLETE + readiness (no separate later step)
        assert (cur.get("analysis") or {}).get("status") == "COMPLETE", cur.get("analysis")
        assert (cur.get("readiness") or {}).get("ready") is True
        # 3. therefore executable right now
        el = scheduler.eligible(cur)
        assert el["ok"] is True, el["reasons"]
    finally:
        _clean()


def test_epic_is_not_groomed_but_children_are():
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "EPIC: scaffold", type_="epic", tag="TST")["id"]
        epc = backlog.get_epic("project", _PROJ, ep)
        assert (epc.get("analysis") or {}).get("status") != "COMPLETE"   # containers are not "groomed"
        c = backlog.add_epic("project", _PROJ, "child task", body=_BODY, tag="TST", epic=ep)["id"]
        cc = backlog.get_epic("project", _PROJ, c)
        assert str(cc.get("epic")) == str(ep)
        assert (cc.get("analysis") or {}).get("status") == "COMPLETE"
    finally:
        _clean()


def test_first_time_only_idempotent():
    _clean()
    try:
        a = backlog.ensure_item("project", _PROJ, "ext-1", "first title", tag="TST")
        b = backlog.ensure_item("project", _PROJ, "ext-1", "first title", tag="TST")
        assert a["id"] == b["id"]           # re-add reuses the item (create-only grooming)
        assert (backlog.get_epic("project", _PROJ, a["id"]).get("analysis") or {}).get("status") == "COMPLETE"
    finally:
        _clean()


def test_epic_execution_order_persisted_on_add():
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "EPIC: order here", type_="epic", tag="TST")["id"]
        c = backlog.add_epic("project", _PROJ, "ordered child", body=_BODY, tag="TST", epic=ep)["id"]
        order = backlog.get_epic("project", _PROJ, ep).get("execution_order") or []
        assert any(str(r.get("id")) == str(c) for r in order), order
    finally:
        _clean()


def test_delete_resyncs_parent_epic_children():
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "EPIC: del", type_="epic", tag="TST")["id"]
        c = backlog.add_epic("project", _PROJ, "child", body=_BODY, tag="TST", epic=ep)["id"]
        assert str(c) in (backlog.get_epic("project", _PROJ, ep).get("children") or [])
        backlog.delete("project", _PROJ, c)
        assert str(c) not in (backlog.get_epic("project", _PROJ, ep).get("children") or [])
    finally:
        _clean()
