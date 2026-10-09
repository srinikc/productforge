"""BI-PF-1195: grooming completeness - one groom fills priority, structured deps, and full context.

Deterministic-path coverage (no live model): context/priority/deps population, gap-fill vs --force, and
mapping of explicit deps. Items must remain gate-safe (no '(derived)' placeholders; brief source set).
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_groom_complete"
_BODY = ("## Problem\nExport is missing.\n\n## Goal\nAdd export API.\n\n## In scope\n- export endpoint\n\n"
         "## Acceptance\n- returns a file")


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _mk(title="Add export API", body=_BODY, deps=None):
    return backlog.add_epic("project", _PROJ, title, body=body, tag="TST", deps=deps)["id"]


def _reset(iid):
    backlog.set_analysis("project", _PROJ, iid, status="NOT_ANALYZED", analysis={}, analyzed_by="")
    backlog.update("project", _PROJ, iid, objective="", acceptance_criteria=[], in_scope=[],
                   priority=None, priority_class="", moscow="", dependencies=[], deps=[])


def _get(iid):
    return backlog.get("project", _PROJ, iid) or {}


def test_deterministic_fills_context_and_priority():
    _clean()
    try:
        iid = _mk()
        _reset(iid)
        grooming.groom("project", _PROJ, iid, mode="deterministic")
        it = _get(iid)
        assert str(it.get("objective") or "").strip()
        assert it.get("acceptance_criteria")
        assert it.get("in_scope")
        assert it.get("out_of_scope")
        assert it.get("approach")
        assert it.get("verification")
        assert it.get("rollback")
        assert str(it.get("owner") or "").strip()
        assert it.get("priority") == "P2"           # default priority
        assert it.get("brief", {}).get("source") in ("authored", "extracted")
    finally:
        _clean()


def test_gap_fill_vs_force_overwrite():
    _clean()
    try:
        iid = _mk()
        _reset(iid)
        backlog.update("project", _PROJ, iid, objective="HUMAN AUTHORED objective")
        grooming.groom("project", _PROJ, iid, mode="deterministic")          # gap-fill: keep authored
        assert _get(iid)["objective"] == "HUMAN AUTHORED objective"
        grooming.groom("project", _PROJ, iid, mode="deterministic", force=True)  # --force: overwrite
        assert _get(iid)["objective"] != "HUMAN AUTHORED objective"
    finally:
        _clean()


def test_explicit_deps_mapped_to_structured():
    _clean()
    try:
        iid = _mk(deps=["BI-PF-0001"])
        _reset(iid)
        backlog.update("project", _PROJ, iid, deps=["BI-PF-0001"], dependencies=[])  # keep explicit dep
        grooming.groom("project", _PROJ, iid, mode="deterministic")
        deps = _get(iid).get("dependencies") or []
        assert any(str(d.get("task_id")) == "BI-PF-0001" for d in deps if isinstance(d, dict))
    finally:
        _clean()
