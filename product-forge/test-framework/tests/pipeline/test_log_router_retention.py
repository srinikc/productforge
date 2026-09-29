"""BI-PF-0233: log_router retention (rotate_runs) + canonical event routing."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import log_router as lr  # noqa: E402
from core import events as ev  # noqa: E402


def test_rotate_runs_keeps_newest(tmp_path):
    base = tmp_path / "logs"
    base.mkdir()
    for i in range(5):
        d = base / f"run-{i}"
        d.mkdir()
        (d / "x.log").write_text("x", encoding="utf-8")
    removed = lr.rotate_runs(str(tmp_path), keep_runs=2)
    remaining = [d for d in os.listdir(base) if os.path.isdir(base / d)]
    assert len(remaining) == 2 and removed == 3


def test_events_emit_uses_canonical_path(tmp_path):
    ev.emit(str(tmp_path), "run_started", run_id="r1")
    p = tmp_path / "events.jsonl"
    assert p.exists() and "run_started" in p.read_text(encoding="utf-8")
