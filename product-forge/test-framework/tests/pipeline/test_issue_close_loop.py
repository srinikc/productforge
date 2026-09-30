"""BI-PF-0271: the full issue <-> backlog close-loop, end to end and fail-closed.

The exact process: raise issue -> paired backlog raised -> RCCA recorded -> fix -> close the loop
back (backlog AND issue, recording where the fix was done), bidirectionally.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog as b  # noqa: E402
from core import issues as I  # noqa: E402

_SCOPE = "project"
_PROJECT = "_test_bi_pf_0271"


def _cleanup():
    for iid in ("IS-BIPF0271-0001",):
        pass
    try:
        for e in I.list_open(_SCOPE, _PROJECT) + I.list_closed(_SCOPE, _PROJECT):
            I.set_status(_SCOPE, _PROJECT, e["id"], "wontfix", force=True)
    except Exception:
        pass


def test_full_close_loop_bidirectional_fail_closed():
    title = "BI-PF-0271 scratch loop defect tree"
    iss = I.raise_issue(_SCOPE, _PROJECT, title, module="core/x.py",
                        priority="P1", auto_backlog=True)
    iid = iss["id"]

    # (1) paired backlog raised + linked 1:1
    ref = (I.get(_SCOPE, _PROJECT, iid) or {}).get("backlog_ref")
    assert ref, "issue did not raise a paired backlog item"
    bscope, bproj, bid = b.parse_ref(ref) if ":" in ref else (_SCOPE, _PROJECT, ref)
    item = b.get(bscope, bproj, bid) or {}
    assert item.get("id") == bid
    assert (item.get("links") or {}).get("issue"), "backlog not linked back to issue"

    # (2) fail-closed: backlog cannot complete before RCCA
    b.set_status(bscope, bproj, bid, "completed")
    assert (b.get(bscope, bproj, bid) or {}).get("status") != "completed"

    # (3) RCCA on the issue
    I.set_rcca(_SCOPE, _PROJECT, iid, root_cause="rc", corrective="co",
               fixed_where="core/x.py:42", generalized=False)

    # (4) close the issue -> propagates close + fixed_where to the backlog item
    I.set_status(_SCOPE, _PROJECT, iid, "closed", note="done")
    closed_item = b.get(bscope, bproj, bid) or {}
    assert closed_item.get("status") == "completed", "issue close did not close the backlog item"
    assert "core/x.py:42" in str((closed_item.get("links") or {}).get("fixed_where", "")), \
        "fixed_where not recorded on the backlog side"

    # cleanup
    try:
        b.delete(bscope, bproj, bid)
    except Exception:
        pass


def test_backlog_gate_refuses_without_issue_rcca():
    item = b.add_epic(_SCOPE, _PROJECT, "gate scratch item", type_="task", tag="TST")
    bid = item["id"]
    iss = I.raise_issue(_SCOPE, _PROJECT, "gate scratch defect", module="m",
                        backlog_ref=bid)  # no RCCA
    b.set_status(_SCOPE, _PROJECT, bid, "completed")
    assert (b.get(_SCOPE, _PROJECT, bid) or {}).get("status") != "completed"
    try:
        b.delete(_SCOPE, _PROJECT, bid)
    except Exception:
        pass
    try:
        I.set_status(_SCOPE, _PROJECT, iss["id"], "wontfix", force=True)
    except Exception:
        pass
