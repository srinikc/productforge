"""BI-PF-0457: duplicate backlog id audit."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from scripts.dev import backlog_id_audit as a  # noqa: E402


def test_duplicate_detection(tmp_path, monkeypatch):
    root = tmp_path / "products" / "zzz_ids" / "backlog" / "items"
    root.mkdir(parents=True)
    (root / ("a" + ".json")).write_text(json.dumps({"id": "BI-Z-0001"}), encoding="utf-8")
    (root / ("b" + ".json")).write_text(json.dumps({"id": "BI-Z-0001"}), encoding="utf-8")
    monkeypatch.setattr(a, "PRODUCTS_DIR", str(tmp_path / "products"))
    dups = a.duplicates()
    assert any("BI-Z-0001" in x for x in dups), dups
    assert a.main() == 1
    # fix the collision -> unique -> OK
    (root / ("b" + ".json")).write_text(json.dumps({"id": "BI-Z-0002"}), encoding="utf-8")
    assert not any("BI-Z-0001" in x for x in a.duplicates())
    assert a.main() == 0
