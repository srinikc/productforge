"""Section D P1 (BI-PF-0244): trace context on events."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import events, tracing  # noqa: E402


def test_span_ids_unique_and_trace_id_equals_run():
    assert tracing.new_span_id() != tracing.new_span_id()
    assert tracing.trace_id(run_id="run-9") == "run-9"


def test_events_carry_trace_and_span(tmp_path):
    ev = events.emit(str(tmp_path), "agent_completed", run_id="run-7", stage="1", agent="design")
    assert ev["trace_id"] == "run-7" and ev["span_id"]
