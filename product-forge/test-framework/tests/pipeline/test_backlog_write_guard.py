"""BI-PF-1327 (WG-O3): backlog API-only write guard - tests that can fail.

The durable backlog store has a single writer (``core/backlog.py``) and one sanctioned surface for callers
(the backlog API). The guard flags other modules that reach the store's private writers. Pure-function tests
(no repo-state dependence) + a repo-clean assertion.
"""
import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

_ROOT = Path(__file__).resolve().parents[3]


def _load():
    spec = importlib.util.spec_from_file_location(
        "bwg", _ROOT / "scripts" / "dev" / "backlog_write_guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reaches_private_detects_bypass():
    g = _load()
    assert g.reaches_private("from core import backlog\nbacklog._save_item(d, it)") is True
    assert g.reaches_private("backlog._write_indexes(s, p, op, cl)") is True
    assert g.reaches_private("from core.backlog import _load_all\n") is True
    # going through the module's PUBLIC API is fine
    assert g.reaches_private("from core import backlog\nbacklog.update(s, p, iid, title='x')") is False
    assert g.reaches_private("backlog.get_epic(s, p, iid)") is False


def test_allowed_paths_are_the_sanctioned_publishers():
    g = _load()
    for p in ("core/backlog.py", "api/routers/backlog.py", "core/state_checkpoint.py",
              "core/delivery.py", "scripts/dev/pf_merge_driver.py"):
        assert g.is_allowed(p) is True
    assert g.is_allowed("core/some_new_module.py") is False


def test_baseline_grandfathers_pre_existing_offenders(monkeypatch):
    g = _load()
    monkeypatch.setattr(g, "_BASELINE", {"core/legacy_bypass.py"})
    assert g.new_offenders(["core/legacy_bypass.py", "core/fresh_bypass.py"]) == ["core/fresh_bypass.py"]


def test_repo_has_no_new_bypasses():
    g = _load()
    assert g.new_offenders(g.offenders()) == []
