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


def test_execute_stage_excludes_already_executed():
    """BI-PF-0416: the worker claim path (stage=execute) must not return executed items."""
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Feature X", tag="TST")["id"]
        _approve(iid)
        assert scheduler.eligible(backlog.get("project", _PROJ, iid), stage="execute")["ok"] is True
        backlog.set_status("project", _PROJ, iid, "verifying", note="executed by a worker")
        it = backlog.get("project", _PROJ, iid)
        # default gate unchanged (a verification stage may still pick it up) ...
        assert scheduler.eligible(it)["ok"] is True
        # ... but the execution claim excludes it
        e = scheduler.eligible(it, stage="execute")
        assert e["ok"] is False and any("execution-eligible" in r for r in e["reasons"]), e
        assert scheduler.next_eligible("project", _PROJ, stage="execute")["found"] is False
    finally:
        _clean()


def test_dependency_blocks_then_unblocks():
    _clean()
    try:
        a = backlog.add_epic("project", _PROJ, "Feature A", tag="TST")["id"]
        _approve(a)
        b = backlog.add_epic("project", _PROJ, "Feature B", tag="TST")["id"]
        # B REQUIRES A -> B waits on A (A6.4 direction). BLOCKS would be the inverse edge.
        backlog.set_dependencies("project", _PROJ, b, dependencies=[{"task_id": a, "type": "REQUIRES"}])
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
        nxt = scheduler.next_eligible("project", _PROJ)
        assert nxt["item"] == hi
        # PIDL pickup contract rides along (BI-PF-0379): the worker carries context + policy
        assert "pidl_context" in nxt and "execution_policy" in nxt
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


def test_epic_scope_filters_next_and_eligible():
    """An epic filter restricts selection to that epic's children (deps still resolve globally)."""
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "Epic A", type_="epic", tag="TST")["id"]
        other = backlog.add_epic("project", _PROJ, "Outside", tag="TST")["id"]
        lo = backlog.add_epic("project", _PROJ, "Child low", epic=ep, tag="TST")["id"]
        hi = backlog.add_epic("project", _PROJ, "Child high", epic=ep, tag="TST")["id"]
        for i in (other, lo, hi):
            _approve(i)
        backlog.set_priority("project", _PROJ, other, priority_rank=0)
        backlog.set_priority("project", _PROJ, lo, priority_rank=9)
        backlog.set_priority("project", _PROJ, hi, priority_rank=1)
        nxt = scheduler.next_eligible("project", _PROJ, epic=ep)
        assert nxt["found"] and nxt["item"] == hi and nxt["epic"] == ep, nxt
        eb = scheduler.eligible_backlog("project", _PROJ, epic=ep)
        assert {r["id"] for r in eb["items"]} == {lo, hi}
        assert eb["total"] == 2 and eb["eligible"] == 2
        # unscoped: the higher-ranked outside item still wins
        assert scheduler.next_eligible("project", _PROJ)["item"] == other
    finally:
        _clean()


def test_epic_order_waves_and_status():
    """epic_order: dependency wave -> priority, with READY/wait status; a done dep unlocks the next wave."""
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "Epic W", type_="epic", tag="TST")["id"]
        a = backlog.add_epic("project", _PROJ, "A", epic=ep, tag="TST")["id"]
        b = backlog.add_epic("project", _PROJ, "B", epic=ep, tag="TST")["id"]
        c = backlog.add_epic("project", _PROJ, "C", epic=ep, tag="TST")["id"]
        for i in (a, b, c):
            _approve(i)
        backlog.set_dependencies("project", _PROJ, b, dependencies=[{"task_id": a, "type": "REQUIRES"}])
        backlog.set_dependencies("project", _PROJ, c, dependencies=[{"task_id": b, "type": "REQUIRES"}])
        order = scheduler.epic_order("project", _PROJ, epic=ep)
        by = {r["id"]: r for r in order["items"]}
        assert by[a]["wave"] == 0 and by[a]["status"] == "READY", by[a]
        assert by[b]["wave"] == 1 and by[b]["status"] == "wait", by[b]
        assert by[c]["wave"] == 2 and by[c]["status"] == "wait", by[c]
        assert order["counts"] == {"total": 3, "ready": 1, "wait": 2, "waves": 3}
        assert order["items"][0]["id"] == a
        backlog.set_status("project", _PROJ, a, "completed")
        by = {r["id"]: r for r in scheduler.epic_order("project", _PROJ, epic=ep)["items"]}
        # A is done: B's prerequisite is satisfied (wave 0); C stays one wave behind.
        assert by[b]["wave"] == 0 and by[c]["wave"] == 1, by
    finally:
        _clean()


def test_epic_order_save_persists_execution_order():
    """epic_order(save=True) stores execution_order[] on the epic; read-only does not change it."""
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "Epic SV", type_="epic", tag="TST")["id"]
        a = backlog.add_epic("project", _PROJ, "SVA", epic=ep, tag="TST")["id"]
        b = backlog.add_epic("project", _PROJ, "SVB", epic=ep, tag="TST")["id"]
        _approve(a)
        _approve(b)
        backlog.set_dependencies("project", _PROJ, b, dependencies=[{"task_id": a, "type": "REQUIRES"}])
        out = scheduler.epic_order("project", _PROJ, epic=ep, save=True)
        assert out["saved"] is True
        stored = backlog.get_epic("project", _PROJ, ep).get("execution_order")
        assert [r["id"] for r in stored] == [a, b]
        assert stored[0]["wave"] == 0 and stored[1]["wave"] == 1
        out2 = scheduler.epic_order("project", _PROJ, epic=ep)  # read-only
        assert out2["saved"] is False
        assert backlog.get_epic("project", _PROJ, ep).get("execution_order") == stored
    finally:
        _clean()


def test_epic_status_lists_all_children_and_rollup():
    """epic_status: open + closed children with groomed/needs_reanalysis + epic rollup."""
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "Epic ST", type_="epic", tag="TST")["id"]
        a = backlog.add_epic("project", _PROJ, "STA", epic=ep, tag="TST")["id"]
        b = backlog.add_epic("project", _PROJ, "STB", epic=ep, tag="TST")["id"]
        c = backlog.add_epic("project", _PROJ, "STC", epic=ep, tag="TST")["id"]
        _approve(a)
        _approve(b)
        # c is intentionally left un-groomed -> needs_reanalysis
        backlog.set_status("project", _PROJ, b, "completed")  # a closed child must still be listed
        st = scheduler.epic_status("project", _PROJ, epic=ep)
        rows = {r["id"]: r for r in st["children"]}
        assert rows[a]["state"] == "open" and rows[a]["groomed"] is True
        assert rows[c]["state"] == "open" and rows[c]["needs_reanalysis"] is True
        assert rows[b]["state"] == "closed" and rows[b]["order_status"] == "closed"
        assert st["rollup"] == {"total": 3, "open": 2, "closed": 1, "groomed": 1,
                                "need_reanalysis": 1, "ready": 1, "wait": 1, "done": False}
        assert st["order"][:2] == [a, c]
    finally:
        _clean()


def test_backlog_status_rollup():
    """backlog_status: per-epic rollups for the whole scope."""
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "Epic BS", type_="epic", tag="TST")["id"]
        a = backlog.add_epic("project", _PROJ, "BSA", epic=ep, tag="TST")["id"]
        _approve(a)
        st = scheduler.backlog_status("project", _PROJ)
        row = next(e for e in st["epics"] if e["id"] == ep)
        assert row["rollup"]["open"] == 1 and row["rollup"]["total"] == 1
        assert st["rollup"]["epics"] >= 1 and ep in {e["id"] for e in st["epics"]}
    finally:
        _clean()


def test_grooming_reorders_epic():
    """Grooming/approving a child refreshes+saves the parent epic's execution_order (BI-PF-1235)."""
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "Epic GR", type_="epic", tag="TST")["id"]
        a = backlog.add_epic("project", _PROJ, "GRA", epic=ep, tag="TST")["id"]
        b = backlog.add_epic("project", _PROJ, "GRB", epic=ep, tag="TST")["id"]
        grooming.groom("project", _PROJ, a, mode="deterministic")
        grooming.decide("project", _PROJ, a, "APPROVE")  # approve -> reorder parent epic
        eo = backlog.get_epic("project", _PROJ, ep).get("execution_order") or []
        assert {r["id"] for r in eo} == {a, b}, eo
    finally:
        _clean()
