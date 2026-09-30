"""BI-PF-0294: scoped learnings (project/area) + need-based render + memory read-back opt-in."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import learnings as L  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_scoped_learn"
_GLOBAL = os.path.join(str(ROOT), "data", "learnings." + "json")


def _snapshot_global():
    try:
        with open(_GLOBAL, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _restore_global(snap):
    try:
        if snap is None:
            if os.path.exists(_GLOBAL):
                os.remove(_GLOBAL)
        else:
            with open(_GLOBAL, "w", encoding="utf-8") as f:
                f.write(snap)
    except Exception:
        pass


def _clean():
    # never delete shared state: restore the global file instead
    shutil.rmtree(os.path.join(str(ROOT), "products", _PROJECT), ignore_errors=True)


def test_global_render_unchanged():
    snap = _snapshot_global()
    try:
        L.add("global rule alpha unique-zulu")
        out = L.render()
        assert "global rule alpha unique-zulu" in out
    finally:
        _restore_global(snap); _clean()


def test_project_learning_scoped_and_unioned():
    snap = _snapshot_global()
    try:
        L.add("always pin dependency versions uniquely-quebec")
        L.add("media assets must be validated before publish", project=_PROJECT)
        # project view = project + global
        proj = L.all_learnings(_PROJECT)
        rules = " ".join(e["rule"] for e in proj)
        assert "media assets must be validated before publish" in rules
        assert "always pin dependency versions uniquely-quebec" in rules
        # a DIFFERENT project must NOT see the project-only rule
        other = L.all_learnings("_other_project")
        assert not any("validated before publish" in e["rule"] for e in other)
        # render(project=...) includes both; render() (global) excludes the project rule
        assert "validated before publish" in L.render(project=_PROJECT)
        assert "validated before publish" not in L.render()
    finally:
        _restore_global(snap); _clean()


def test_area_filter_applies():
    snap = _snapshot_global()
    try:
        L.add("backend rule unique-alpha", area="backend", project=_PROJECT)
        L.add("frontend rule unique-bravo", area="frontend", project=_PROJECT)
        r = L.render(area="backend", project=_PROJECT)
        assert "backend rule unique-alpha" in r
        assert "frontend rule unique-bravo" not in r
    finally:
        _restore_global(snap); _clean()


def test_learning_synth_approve_writes_project_store():
    snap = _snapshot_global()
    _clean()
    from core import learning_synth as ls
    try:
        if os.path.exists(ls.STORE):
            os.remove(ls.STORE)
    except Exception:
        pass
    # craft a candidate directly in the store, scoped to the project
    data = {"candidates": {"LC-0001": {
        "id": "LC-0001", "kind": "learning", "text": "scoped rule from candidate unique-echo",
        "scope": f"project:{_PROJECT}", "status": "proposed", "evidence": [{"source": "x"}],
        "confidence": 0.9, "proposed_at": "2026-01-01"}}}
    ls._save(data)
    r = ls.approve("LC-0001", by="test")
    assert r["ok"]
    # written to the PROJECT store, not global
    assert any("unique-echo" in e["rule"] for e in L.all_learnings(_PROJECT))
    assert not any("unique-echo" in e["rule"] for e in L.all_learnings())
    _restore_global(snap); _clean()
