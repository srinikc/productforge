"""BI-0198: AG-UI typed event stream — mapping + run filter + no-content."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import agui  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_agui"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)


def test_lifecycle_mapping():
    assert agui.map_event({"type": "run_started"})["type"] == "RUN_STARTED"
    assert agui.map_event({"type": "run_completed"})["type"] == "RUN_FINISHED"
    assert agui.map_event({"type": "run_failed", "message": "x"})["type"] == "RUN_ERROR"


def test_step_and_usage_and_state_mapping():
    assert agui.map_event({"type": "agent_started", "agent": "design"})["type"] == "STEP_STARTED"
    assert agui.map_event({"type": "stage_completed"})["type"] == "STEP_FINISHED"
    assert agui.map_event({"type": "agent_failed"})["status"] == "error"
    assert agui.map_event({"type": "plan_confirmed"})["type"] == "STATE_DELTA"
    u = agui.map_event({"type": "gen_ai_call", "input_tokens": 10, "output_tokens": 5, "model": "m"})
    assert u["type"] == "USAGE" and u["input_tokens"] == 10


def test_unknown_is_custom_not_dropped():
    m = agui.map_event({"type": "totally_unknown"})
    assert m["type"] == "CUSTOM" and m["event"] == "totally_unknown"


def test_map_all_filters_by_run_and_order():
    _clean()
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        from core import events as ev
        ev.emit(d, "run_started", run_id="run-1")
        ev.emit(d, "agent_started", run_id="run-1", agent="design")
        ev.emit(d, "run_completed", run_id="run-1")
        ev.emit(d, "run_started", run_id="run-2")
        all_ev = agui.map_all(d)
        assert [e["type"] for e in all_ev][:3] == ["RUN_STARTED", "STEP_STARTED", "RUN_FINISHED"]
        only1 = agui.map_all(d, run_id="run-1")
        assert all(e["runId"] == "run-1" for e in only1)
        assert len(only1) == 3
        # no content leaked
        import json
        assert "prompt" not in json.dumps(all_ev).lower()
    finally:
        _clean()
