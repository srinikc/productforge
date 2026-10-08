"""BI-PF-0444 (F2/D2): Epic entity - child linking, children rollup, no-dispatch, close-guard; context gate."""
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, scheduler  # noqa: E402

PROJ = "_test_bl_ctx"
_DIR = ROOT / "products" / PROJ


def _clean():
    shutil.rmtree(_DIR, ignore_errors=True)


def test_epic_child_link_and_done_rollup():
    _clean()
    try:
        ep = backlog.add_epic("project", PROJ, title="EPIC: a feature",
                              type_="epic", brief={"problem": "p", "what_adds": "w"},
                              objective="o", summary="s")
        c1 = backlog.add_epic("project", PROJ, title="child alpha work", epic=ep["id"],
                              acceptance_criteria=["a"])
        c2 = backlog.add_epic("project", PROJ, title="child beta work", epic=ep["id"],
                              acceptance_criteria=["b"])
        e = backlog.get("project", PROJ, ep["id"])
        assert sorted(e["children"]) == sorted([c1["id"], c2["id"]])          # bidirectional link
        assert backlog.get("project", PROJ, c1["id"])["epic"] == ep["id"]
        assert backlog.is_epic(e) and not backlog.is_epic(backlog.get("project", PROJ, c1["id"]))
        assert backlog.epic_done("project", PROJ, ep["id"]) is False
        with pytest.raises(ValueError):
            backlog.set_status("project", PROJ, ep["id"], "completed")        # rollup guard
        backlog.set_status("project", PROJ, c1["id"], "completed")
        assert backlog.epic_done("project", PROJ, ep["id"]) is False
        backlog.set_status("project", PROJ, c2["id"], "completed")
        assert backlog.epic_done("project", PROJ, ep["id"]) is True
        backlog.set_status("project", PROJ, ep["id"], "completed")            # now allowed
        assert backlog.get("project", PROJ, ep["id"])["status"] == "completed"
    finally:
        _clean()


def test_epic_is_not_dispatchable():
    _clean()
    try:
        ep = backlog.add_epic("project", PROJ, title="EPIC: not dispatchable", type_="epic")
        r = scheduler.eligible(ep)
        assert r["ok"] is False and any("epic" in x for x in r["reasons"])
    finally:
        _clean()


def test_context_gate_flags_missing_fields():
    from scripts.dev import backlog_context_check as g
    bad = {"id": "BI-X", "type": "feature", "brief": {}, "objective": "", "acceptance_criteria": []}
    probs = g._problems_for("product_forge", None, [bad], [bad])
    assert any("brief" in p for p in probs) and any("acceptance_criteria" in p for p in probs)
