"""F1 (BI-PF-0234): terminal events carry run_id and reconcile leftover 'running' state."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import run_status as rs  # noqa: E402


def test_terminal_failed_reconciles_running(tmp_path):
    d = str(tmp_path)
    rs.update(d, "run_started", run_id="run-1")
    rs.update(d, "stage_started", stage="1")
    rs.update(d, "agent_started", stage="1", agent="design", status="running")
    out = rs.update(d, "run_failed", run_id="run-1")
    assert out["state"] == "failed"
    assert out["run_id"] == "run-1"
    assert out["stages"].get("1") == "interrupted"
    assert out["agents"].get("1:design") == "failed"


def test_terminal_completed_reconciles_running(tmp_path):
    d = str(tmp_path)
    rs.update(d, "stage_started", stage="2")
    out = rs.update(d, "run_completed", run_id="run-2")
    assert out["state"] == "completed"
    assert out["stages"].get("2") == "interrupted"
