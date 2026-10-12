"""BI-PF-1258: restamp (signature-only) + regroom (full, change-aware)."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_regroom"
_BODY = "## Problem\nExport is missing.\n\n## Goal\nAdd export API.\n\n## Acceptance\n- returns a file\n"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _mk(title="Export CSV"):
    return backlog.add_epic("project", _PROJ, title, body=_BODY, tag="TST")["id"]


def _force_stale(iid):
    it = backlog.get_epic("project", _PROJ, iid)
    a = dict(it.get("analysis") or {})
    a["status"] = "COMPLETE"
    a["arch_fingerprint"] = "deadbeefdeadbeef"
    backlog.update("project", _PROJ, iid, analysis=a)


def test_restamp_clears_stale_signature_only():
    _clean()
    try:
        iid = _mk()
        _force_stale(iid)
        assert backlog.analysis_is_stale(backlog.get_epic("project", _PROJ, iid))
        r = grooming.restamp("project", _PROJ, ids=[iid], reason="test")
        assert iid in r["restamped"]
        assert not backlog.analysis_is_stale(backlog.get_epic("project", _PROJ, iid))
    finally:
        _clean()


def test_regroom_updates_context_and_approves():
    _clean()
    try:
        iid = _mk()
        # clear context + simulate the architecture change (stale) so regroom must act
        backlog.update("project", _PROJ, iid, objective="", acceptance_criteria=[], in_scope=[],
                       out_of_scope=[], approach="")
        _force_stale(iid)
        r = grooming.regroom("project", _PROJ, ids=[iid], mode="deterministic", approve=True)
        assert iid in r["regroomed"]
        it = backlog.get_epic("project", _PROJ, iid)
        assert it.get("objective")  # context authored
        assert str((it.get("analysis") or {}).get("status")) == "COMPLETE"
        assert not backlog.analysis_is_stale(it)
    finally:
        _clean()


def test_regroom_epic_scope_only():
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "Epic", type_="epic", tag="TST")["id"]
        inside = _mk("inside")
        backlog.update("project", _PROJ, inside, epic=ep, parent=ep)
        outside = _mk("outside")
        _force_stale(inside)
        _force_stale(outside)
        r = grooming.regroom("project", _PROJ, epic=ep, mode="deterministic", approve=True)
        assert inside in r["regroomed"] and outside not in r["regroomed"]
    finally:
        _clean()
