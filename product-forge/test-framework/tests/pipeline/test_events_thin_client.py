"""BI-PF-1272: Contract tests for Python thin-client cutover of core/events.py.

Verifies:
1. emit() delegates to go_host.event_append and receives monotonic seq from Go core.
2. Strangler fallback cleanly preserves local append if Go host is unavailable or errors.
3. Backward compatibility of TYPES, EVENT_VERSION, path(), read(), counts().
4. Seamless Go-to-Python envelope parity without creating duplicate event files.
"""
import json
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import events
from core import go_host


def _go_bin():
    found = shutil.which("go")
    if found:
        return found
    local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "go", "bin",
                         "go" + (".exe" if os.name == "nt" else ""))
    return local if os.path.exists(local) else None


@pytest.mark.skipif(_go_bin() is None, reason="go toolchain not installed")
def test_emit_delegates_to_go_core_monotonic_seq(tmp_path):
    project_dir = str(tmp_path / "proj_alpha")

    # 1. Emit three events sequentially
    ev1 = events.emit(project_dir, "run_started", run_id="r1", task_id="T-01")
    assert ev1 is not None
    assert ev1.get("seq") == 1
    assert ev1["event_type"] == "run_started"
    assert ev1["run_id"] == "r1"

    ev2 = events.emit(project_dir, "stage_started", run_id="r1", stage="plan")
    assert ev2 is not None
    assert ev2.get("seq") == 2
    assert ev2["event_type"] == "stage_started"

    ev3 = events.emit(project_dir, "run_completed", run_id="r1")
    assert ev3 is not None
    assert ev3.get("seq") == 3
    assert ev3["event_type"] == "run_completed"

    # 2. Verify on-disk file parity: exactly 3 lines, sequential seq, no duplicate file
    store_file = Path(events.path(project_dir))
    assert store_file.exists()
    lines = [json.loads(line) for line in store_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 3
    assert [ln["seq"] for ln in lines] == [1, 2, 3]

    # Verify read() returns the exact 3 records
    records = events.read(project_dir)
    assert len(records) == 3
    assert [r["seq"] for r in records] == [1, 2, 3]


def test_fallback_strangler_when_go_host_fails(tmp_path):
    project_dir = str(tmp_path / "proj_fallback")

    # Mock go_host.event_append to return ok=False
    with patch("core.go_host.event_append", return_value={"ok": False, "error": "simulated go host down"}):
        ev = events.emit(project_dir, "run_started", run_id="r_fb", stage="init")
        assert ev is not None
        assert ev["event_type"] == "run_started"
        assert ev["run_id"] == "r_fb"

    # Mock go_host.event_append raising an exception
    with patch("core.go_host.event_append", side_effect=RuntimeError("Go host exploded")):
        ev2 = events.emit(project_dir, "stage_started", run_id="r_fb", stage="plan")
        assert ev2 is not None
        assert ev2["event_type"] == "stage_started"

    # Verify both events persisted to disk via fallback strangler path
    records = events.read(project_dir)
    assert len(records) == 2
    assert records[0]["event_type"] == "run_started"
    assert records[1]["event_type"] == "stage_started"


def test_public_api_and_constants_backward_compatibility(tmp_path):
    project_dir = str(tmp_path / "proj_compat")

    # Verify constants
    assert events.EVENT_VERSION == "1"
    assert "run_started" in events.TYPES
    assert "run_completed" in events.TYPES
    assert "agent_started" in events.TYPES

    # Verify path helper
    expected_path = os.path.join(project_dir, "events.jsonl")
    assert events.path(project_dir) == expected_path

    # Emit test events
    events.emit(project_dir, "run_started", run_id="r100")
    events.emit(project_dir, "run_completed", run_id="r100")
    events.emit(project_dir, "run_started", run_id="r101")

    # Verify counts() helper
    c = events.counts(project_dir)
    assert c.get("run_started") == 2
    assert c.get("run_completed") == 1

    # Verify read(limit=2)
    recent = events.read(project_dir, limit=2)
    assert len(recent) == 2
    assert recent[-1]["run_id"] == "r101"


def test_envelope_parity_and_extra_fields(tmp_path):
    project_dir = str(tmp_path / "proj_envelope")

    ev = events.emit(
        project_dir,
        "run_started",
        run_id="run-42",
        stage="s1",
        agent="builder",
        task_id="TK-99",
        worker_id="WK-1",
        actor="operator",
        correlation_id="corr-1",
        causation_id="cause-0",
        custom_tag="alpha_beta",
    )
    assert ev is not None

    # Check additive formal envelope
    assert "event_id" in ev and len(ev["event_id"]) > 0
    assert ev["event_type"] == "run_started"
    assert ev["event_version"] == "1"
    assert "occurred_at" in ev
    assert ev["run_id"] == "run-42"
    assert ev["task_id"] == "TK-99"
    assert ev["worker_id"] == "WK-1"
    assert ev["actor"] == "operator"
    assert ev["correlation_id"] == "corr-1"
    assert ev["causation_id"] == "cause-0"
    assert ev["custom_tag"] == "alpha_beta"

    # Check legacy flat fields (back-compat)
    assert ev["type"] == "run_started"
    assert ev["level"] == "INFO"
    assert ev["stage"] == "s1"
    assert ev["agent"] == "builder"
    assert ev["trace_id"] == "run-42"
