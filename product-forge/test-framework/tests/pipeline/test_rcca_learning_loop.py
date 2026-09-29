"""BI-PF-0270: RCCA -> learning -> guideline loop is wired + the close gate is fail-closed.

Proves: raise_issue(backlog_ref=...) sets up the reciprocal link so a linked backlog item
CANNOT close until the issue records a complete RCCA; and a generalized RCCA routes a
de-duplicated learning into the learnings registry.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog as b  # noqa: E402
from core import compliance_check as cc  # noqa: E402
from core import issues as I  # noqa: E402
from core import learnings as L  # noqa: E402

_SCOPE = "product_forge"


def _wipe(scope):
    import core.issues as _I
    d, _a, _b, _c = _I._paths(scope, None)
    import os
    for n in ("open.json", "closed.json", "counters.json"):
        p = os.path.join(d, n)
        if os.path.exists(p):
            os.remove(p)
    import core.learnings as _L
    try:
        if os.path.exists(_L._path()):
            os.remove(_L._path())
    except Exception:
        pass


def test_raise_issue_links_backlog_and_gate_fails_closed():
    # use a scratch project scope so we never touch real shared state
    scope = "project"
    project = "_test_bi_pf_0270"
    item = b.add_epic(scope, project, "temp gate item", type_="task", tag="TST")
    bid = item["id"]

    iss = I.raise_issue(scope, project, "temp defect", module="core/x.py", backlog_ref=bid)
    iid = iss["id"]

    # (1) reciprocal link on the backlog side must exist (so set_status can find it)
    linked = b.get(scope, project, bid) or {}
    assert (linked.get("links") or {}).get("issue"), "backlog item not linked to issue"

    # (2) fail-closed: cannot complete while RCCA incomplete
    b.set_status(scope, project, bid, "completed")
    assert (b.get(scope, project, bid) or {}).get("status") != "completed"

    # (3) complete the RCCA with generalization -> learning routed (add OR merge is correct:
    # dedup merges similar rules, so assert the loop produced a rule attributable to this RCCA)
    I.set_rcca(scope, project, iid,
               root_cause="r", corrective="c", fixed_where="f",
               generalized=True, guideline_ref="EOS G8",
               preventive="scratch loop-learning marker 0270")
    after = L.all_learnings()
    assert after, "no learning routed from generalized RCCA"
    assert any(iid in (l.get("sources") or []) for l in after), \
        f"{iid} not recorded as a learning source"

    # (4) now the close succeeds (gate satisfied)
    ok, reason = I.can_close_ref(b.qualify(scope, project, iid))
    assert ok, reason
    b.set_status(scope, project, bid, "completed")
    assert (b.get(scope, project, bid) or {}).get("status") == "completed"

    # cleanup scratch
    try:
        b.delete(scope, project, bid)
    except Exception:
        pass
    try:
        I.set_status(scope, project, iid, "closed", force=True)
    except Exception:
        pass


def test_derived_checklist_has_g8_failure_mode_check():
    cl = cc.derived_checklist("any-agent")
    ids = [i["id"] for cat in cl.values() for i in cat.get("items", [])]
    assert "failure-modes" in ids
