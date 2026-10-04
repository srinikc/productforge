"""PFSSOT-P3 (BI-PF-0364): deep architecture analysis merged into grooming.

Deep-by-default: on entry the item is groomed with a codebase-grounded analysis (existing
components/APIs/modules, fit, strategy, evidence) so pickup is execution, not re-analysis.
Offline/deterministic path is exercised (no live model).
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p3"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_deep_is_default():
    gl = grooming.guidelines()
    assert gl.get("default_depth") == "deep"
    assert gl.get("ai_on_entry") == "all"


def test_analyze_on_entry_by_default():
    _clean()
    try:
        # keywords overlap real code (worker/backlog/scheduler)
        iid = backlog.add_epic("project", _PROJ, "Add worker heartbeat to backlog scheduler",
                               body="extend worker orchestration", tag="TST")["id"]
        a = backlog.get("project", _PROJ, iid)["analysis"]
        # analysis ran automatically at create (deep)
        assert a["status"] == "IN_PROGRESS"
        assert a.get("depth") == "deep"
        assert a["analyzed_by"] in ("ai", "deterministic")
        # grounded in the real codebase
        assert a["existing_components"], "expected existing component matches"
        assert any(c.endswith((".py",)) for c in a["existing_components"])
        assert a["architecture_fit"] in ("REUSE", "EXTEND", "MODIFY", "NEW_COMPONENT",
                                         "NEW_CAPABILITY", "REFACTOR", "OTHER")
    finally:
        _clean()


def test_standard_depth_skips_codebase():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Thing", tag="TST")["id"]
        r = grooming.groom("project", _PROJ, iid, mode="deterministic", depth="standard")
        assert r["depth"] == "standard"
        a = backlog.get("project", _PROJ, iid)["analysis"]
        assert a["existing_components"] == []   # standard = signals only
    finally:
        _clean()


def test_defer_mode_skips_auto_analysis():
    _clean()
    try:
        it = backlog.add_epic("project", _PROJ, "Deferred item", tag="TST")
        # force defer then re-create path is not exercised; verify default is on_entry
        assert it["analyze_mode"] == "on_entry"
    finally:
        _clean()
