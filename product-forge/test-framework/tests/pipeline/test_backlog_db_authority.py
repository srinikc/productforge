"""DB backlog authority: DB-mode writes are delegated; ID reservations have no fallback."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import core.backlog as backlog  # noqa: E402
from core import id_allocator as ia  # noqa: E402


def test_db_mode_save_does_not_write_authoritative_file(monkeypatch):
    calls = []
    monkeypatch.setenv("PF_BACKLOG_DB", "on")
    monkeypatch.setattr(backlog, "_mirror_item_to_db", lambda item: calls.append(item))
    monkeypatch.setattr(backlog, "_wj", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("file write")))
    backlog._save_item("ignored", {"id": "BI-PF-1", "scope": "product_forge"})
    backlog._save_item("ignored", {"id": "BI-GP-2", "scope": "project", "project": "demo"})
    assert calls == [{"id": "BI-PF-1", "scope": "product_forge"},
                     {"id": "BI-GP-2", "scope": "project", "project": "demo"}]


def test_shared_db_reservation_never_falls_back(monkeypatch):
    monkeypatch.setattr(ia, "_db_enabled", lambda _scope=None: True)
    monkeypatch.setattr(ia, "_reserve_db", lambda scope, project, size: {"start": 11, "end": 20})
    assert ia.reserve_shared("product_forge", None, 10)["source"] == "db"
    monkeypatch.setattr(ia, "_reserve_db", lambda *_a: None)
    try:
        ia.reserve_shared("product_forge", None, 10)
    except RuntimeError as e:
        assert "refusing fallback" in str(e)
    else:
        raise AssertionError("missing DB authority must fail closed")
