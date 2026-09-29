"""Learnings registry: de-duplication + bounded (compact) rendering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import learnings as L  # noqa: E402


def test_duplicate_merges_not_appends(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "_FILE", str(tmp_path / "learnings.json"))
    a = L.add("Use atomic writes for all state stores", "storage", "IS-PF-0001")
    b = L.add("Always use atomic writes for state stores", "storage", "IS-PF-0002")
    assert a["id"] == b["id"]              # merged, not appended
    assert b["count"] >= 2
    assert "IS-PF-0002" in b["sources"]


def test_store_is_capped(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "_FILE", str(tmp_path / "learnings.json"))
    monkeypatch.setattr(L, "STORE_MAX", 2)
    L.add("Prefer connection pooling for postgres databases")
    L.add("Cache HTTP responses with etags and vary headers")
    L.add("Shard write traffic across multiple regional clusters")
    L.add("Rotate encryption keys on a fixed schedule")
    assert len(L.all_learnings()) <= 2


def test_render_is_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "_FILE", str(tmp_path / "learnings.json"))
    L.add("Prefer connection pooling for postgres databases")
    L.add("Cache HTTP responses with etags and vary headers")
    r = L.render(max_learnings=1, max_chars=200)
    assert "LEARNINGS" in r and r.count("\n- ") <= 1
