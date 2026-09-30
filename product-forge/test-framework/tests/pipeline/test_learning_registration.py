"""BI-PF-0295: operator-gated knowledge/skill registration from approved candidates."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import learning_synth as ls  # noqa: E402
from core.paths import ROOT  # noqa: E402


def _reset_store():
    try:
        if os.path.exists(ls.STORE):
            os.remove(ls.STORE)
    except Exception:
        pass


def test_live_layer_check():
    assert ls._live_layer("shared") is True
    assert ls._live_layer("nope-does-not-exist") is False


def test_knowledge_candidate_requires_live_layer():
    _reset_store()
    ls._save({"candidates": {"LC-K": {
        "id": "LC-K", "kind": "knowledge", "text": "prefer immutable infra",
        "scope": "area:does-not-exist", "status": "proposed",
        "evidence": [{"source": "x"}], "confidence": 0.9, "proposed_at": "2026-01-01"}}})
    # approval attempt on a non-live layer => not applied (fail-closed), status still approved
    r = ls.approve("LC-K", by="test")
    assert r["ok"]
    assert r["candidate"]["applied"] is False
    _reset_store()


def test_knowledge_candidate_with_live_layer_registers():
    _reset_store()
    from core import knowledge_registry as kr
    before = len(kr.list_entries())
    ls._save({"candidates": {"LC-K2": {
        "id": "LC-K2", "kind": "knowledge", "text": "shared infra lesson",
        "scope": "area:shared", "status": "proposed",
        "evidence": [{"source": "x"}], "confidence": 0.9, "proposed_at": "2026-01-01"}}})
    r = ls.approve("LC-K2", by="test")
    assert r["ok"] and r["candidate"]["applied"] is True
    assert len(kr.list_entries()) >= before
    # cleanup the registered entry
    try:
        kr.remove("LC-K2")
    except Exception:
        pass
    _reset_store()
