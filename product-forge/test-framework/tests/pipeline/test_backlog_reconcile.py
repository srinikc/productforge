"""BI-PF-0764: backlog id reconcile reports (and can renumber) duplicate ids."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog  # noqa: E402
from scripts.dev import backlog_id_reconcile as rec  # noqa: E402


def test_reconcile_reports_duplicate(tmp_path, monkeypatch):
    scope_dir = tmp_path / "scope"
    (scope_dir / "items").mkdir(parents=True)
    (scope_dir / "items" / ("BI-T-0001" + ".json")).write_text(
        json.dumps({"id": "BI-T-0001", "tag": "T", "created_at": "2026-01-01", "status": "new"}), encoding="utf-8")
    (scope_dir / "items" / ("BI-T-0001b" + ".json")).write_text(
        json.dumps({"id": "BI-T-0001", "tag": "T", "created_at": "2026-02-01", "status": "new"}), encoding="utf-8")

    monkeypatch.setattr(rec, "_scopes", lambda include_all=True: [("product_forge", None)])
    monkeypatch.setattr(backlog, "_dir", lambda scope, project=None: str(scope_dir))
    monkeypatch.setattr(rec, "_on_base", lambda p: False)
    monkeypatch.setattr(rec.id_allocator, "OUT", str(tmp_path / ("idb" + ".json")))

    moves = rec.reconcile(write=False)
    assert len(moves) == 1, moves
    assert moves[0]["old"] == "BI-T-0001" and moves[0]["new"].startswith("BI-T-")
    assert moves[0]["new"] != "BI-T-0001"
