"""
Regression for BI-0072: max_duration_per_stage must measure the STAGE's elapsed
time (not total pipeline time) and must EXCLUDE human-wait time.
"""
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.pipeline_executor import PipelineExecutor  # noqa: E402
from core.stop_conditions import StopConditionManager  # noqa: E402


def _executor(tmp_path, pipeline_started_hours_ago, stage_started_seconds_ago,
              human_wait_seconds):
    ex = PipelineExecutor.__new__(PipelineExecutor)  # bypass __init__
    ex.project = "TestProj"
    ex.iteration_count = 0
    ex.stop_conditions = StopConditionManager(str(tmp_path))
    ex.execution = types.SimpleNamespace(
        total_tokens=0, total_cost=0.0, stage_executions={},
        started_at=(datetime.now() - timedelta(hours=pipeline_started_hours_ago)).isoformat(),
    )
    ex._stage_started_at = (datetime.now() - timedelta(seconds=stage_started_seconds_ago)).isoformat()
    ex._stage_human_wait_seconds = human_wait_seconds
    return ex


def test_long_pipeline_total_does_not_trip_stage_limit(tmp_path):
    """A 5h-old pipeline in a just-started stage must NOT trip max_duration_per_stage."""
    ex = _executor(tmp_path, pipeline_started_hours_ago=5, stage_started_seconds_ago=10,
                   human_wait_seconds=0)
    should_stop, triggered = ex.check_stop_conditions("0a")
    names = [getattr(c, "name", c) for c in (triggered or [])]
    assert not should_stop, names
    assert "max_duration_per_stage" not in names


def test_human_wait_excluded_from_stage_duration(tmp_path):
    """A stage that has waited 5h on a human but ran ~10s must NOT trip."""
    ex = _executor(tmp_path, pipeline_started_hours_ago=5, stage_started_seconds_ago=5 * 3600,
                   human_wait_seconds=5 * 3600 - 10)
    should_stop, triggered = ex.check_stop_conditions("0a")
    names = [getattr(c, "name", c) for c in (triggered or [])]
    assert not should_stop, names


def test_real_long_stage_does_trip(tmp_path):
    """A genuinely long stage (2h of work, no human wait) must trip the 1h per-stage limit."""
    ex = _executor(tmp_path, pipeline_started_hours_ago=2, stage_started_seconds_ago=2 * 3600,
                   human_wait_seconds=0)
    should_stop, triggered = ex.check_stop_conditions("0a")
    names = [getattr(c, "name", c) for c in (triggered or [])]
    assert should_stop
    assert "max_duration_per_stage" in names
