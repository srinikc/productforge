"""BI-PF-1399 Phase 1: the backlog dual-write mirror behaviour (off = no-op; dual = best-effort; on = strict)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from core import backlog  # noqa: E402


def test_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("PF_BACKLOG_DB", raising=False)
    assert backlog._backlog_db_mode() == "off"


def test_mirror_noop_when_off(monkeypatch):
    monkeypatch.delenv("PF_BACKLOG_DB", raising=False)
    # No network attempted; must not raise.
    backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x"})


def test_mirror_skips_without_id(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "dual")
    backlog._mirror_item_to_db({"title": "no id"})  # no id -> no-op


def test_mirror_dual_is_best_effort(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "dual")
    monkeypatch.setenv("PF_BACKLOG_API", "http://127.0.0.1:1")  # unreachable
    # best-effort: swallows the failure (files remain the source of truth)
    backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x", "type": "feature", "status": "new"})


def test_mirror_on_propagates_failure(monkeypatch):
    monkeypatch.setenv("PF_BACKLOG_DB", "on")
    monkeypatch.setenv("PF_BACKLOG_API", "http://127.0.0.1:1")
    with pytest.raises(Exception):
        backlog._mirror_item_to_db({"id": "BI-PF-0000", "title": "x", "type": "feature", "status": "new"})
