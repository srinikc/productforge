"""S4 capability steering (BI-0221/0222/0223): vector + capability-aware request builder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import agent_capabilities as ac  # noqa: E402


def test_vector_merge_and_defaults():
    d = ac.vector("design")
    assert d["needs_structured"] is True and d["min_output"] == 8000
    u = ac.vector("no-such-agent")
    assert u["needs_structured"] is False and u["needs_tools"] is False


def test_reasoning_control():
    assert ac.reasoning_enabled("architect") is True
    assert ac.reasoning_enabled("researcher") is False


def test_build_request_enables_only_supported():
    r = ac.build_request("design", {"structured_outputs": True, "reasoning": True})
    assert r["structured"] is True and r["reasoning"] is True and r["degraded"] == []


def test_build_request_degrades_and_flags():
    r = ac.build_request("design", {"structured_outputs": False, "reasoning": True})
    assert r["structured"] is False and "structured" in r["degraded"]
