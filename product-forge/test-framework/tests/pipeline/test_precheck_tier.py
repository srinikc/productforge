"""BI-PF-1374: precheck runs a minimal (docs-fresh + compile) tier for a derived/bookkeeping-only change."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from scripts.dev import precheck  # noqa: E402

_BK = ["product-forge/data/backlog/open.json",
       "product-forge/data/backlog/items/BI-PF-0001.json",
       "product-forge/docs/BACKLOG-SUMMARY.md",
       "product-forge/docs/documentation-index.html"]


def test_bookkeeping_only_true_for_derived_set():
    assert precheck._bookkeeping_only(_BK) is True


def test_bookkeeping_only_false_when_source_changed():
    assert precheck._bookkeeping_only(_BK + ["product-forge/core/scheduler.py"]) is False


def test_bookkeeping_only_false_for_config_or_tests():
    assert precheck._bookkeeping_only(["product-forge/config/env-flags.json"]) is False
    assert precheck._bookkeeping_only(["product-forge/test-framework/tests/pipeline/test_x.py"]) is False


def test_bookkeeping_only_false_when_empty():
    assert precheck._bookkeeping_only([]) is False


def test_steps_minimal_for_bookkeeping(monkeypatch):
    monkeypatch.setattr(precheck, "_changed_paths", lambda: list(_BK))
    names = [n for n, _ in precheck._steps(scope_csv="")]
    assert names == ["compile", "docs-fresh"], names    # minimal tier only


def test_steps_full_tier_for_source(monkeypatch):
    monkeypatch.setattr(precheck, "_changed_paths", lambda: ["product-forge/core/scheduler.py"])
    names = [n for n, _ in precheck._steps(scope_csv="")]
    assert "compile" in names and len(names) > 2         # full fast tier, not the minimal one


def test_groups_ignore_bookkeeping_shortcut(monkeypatch):
    # BI-PF-1419: the bookkeeping shortcut only applies to the default fast path (`_steps`);
    # --full churns the NAMED groups, which always run (so `--full` ignores the shortcut).
    monkeypatch.setattr(precheck, "_changed_paths", lambda: list(_BK))
    steps, _label = precheck._group_steps("backlog")
    assert steps and len(steps) > 2


def test_integration_ref_falls_back_to_origin(monkeypatch):
    def fake_git(*args):
        ref = args[-1].replace("^{commit}", "")
        if ref == "develop":
            raise precheck.GitError("no local develop")
        assert ref == "origin/develop"
        return "abc123"

    monkeypatch.setattr(precheck, "_git", fake_git)
    assert precheck._integration_ref() == "origin/develop"


def test_integration_ref_fails_closed_when_missing(monkeypatch):
    def fake_git(*args):
        raise precheck.GitError("missing ref")

    monkeypatch.setattr(precheck, "_git", fake_git)
    with pytest.raises(precheck.GitError):
        precheck._integration_ref()
