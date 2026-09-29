"""F1 (BI-PF-0233): project-scoped bus events mirror into the canonical per-project stream."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import event_bus as eb  # noqa: E402

ROOT = Path(__file__).parent.parent.parent.parent


def test_bus_event_mirrors_to_project_stream(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "_EVENTS", str(tmp_path / "events.jsonl"))
    proj = "_test_event_ssot"
    base = ROOT / "products" / proj
    try:
        eb.emit("stuck", project=proj, run_id="r1", stage="1")
        p = base / "events.jsonl"
        assert p.exists()
        lines = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert any(e.get("type") == "stuck" and e.get("run_id") == "r1" for e in lines)
    finally:
        if base.is_dir():
            shutil.rmtree(base, ignore_errors=True)
