"""Tests for core/project_archive.py (BI-0071)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.project_archive as pa  # noqa: E402


def _isolate(tmp_path, monkeypatch):
    products = tmp_path / "products"
    products.mkdir()
    monkeypatch.setattr(pa, "PRODUCTS", str(products))
    monkeypatch.setattr(pa, "ARCHIVE_DIR", str(products / ".archive"))
    monkeypatch.setattr(pa, "REGISTRY", str(tmp_path / "archive-registry.json"))


def test_archive_and_restore(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    proj = Path(pa.PRODUCTS) / "demo"
    proj.mkdir()
    (proj / "project.json").write_text("{}", encoding="utf-8")

    r = pa.archive("demo")
    assert r["ok"] and not proj.exists()
    assert any(a["name"] == "demo" for a in pa.list_archived())

    r2 = pa.restore("demo")
    assert r2["ok"] and proj.exists()
    assert pa.list_archived() == []


def test_purge_only_past_retention(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    proj = Path(pa.PRODUCTS) / "old"
    proj.mkdir()
    pa.archive("old")
    # force expiry
    reg = pa._rj(pa.REGISTRY, {})
    reg["old"]["expires_at"] = "2000-01-01T00:00:00"
    pa._wj(pa.REGISTRY, reg)
    purged = pa.purge_due()
    assert "old" in purged
    assert pa.list_archived() == []
