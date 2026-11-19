import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.orchestrator.prompt_builder import design_spec_mandates, implementation_mandates
from core.orchestrator.agent_runner import AgentRunnerMixin


def test_implementation_mandates_are_binding_and_complete():
    text = implementation_mandates()
    for phrase in ("no shortcuts", "UNDERSTAND COMPLETELY", "IMPLEMENT COMPLETELY",
                   "360 IMPACT", "COMPREHENSIVE VALIDATION", "INDEPENDENT QUALITY REVIEW",
                   "DELIVERY COMPLETE"):
        assert phrase in text


def test_design_spec_mandates_are_complete():
    text = design_spec_mandates()
    for phrase in ("REQUIREMENT UNDERSTANDING", "COMPLETE FUNCTIONAL & TECHNICAL DESIGN",
                   "360 SCENARIO", "IMPLEMENTATION & VALIDATION READINESS",
                   "QUALITY & COMPLETENESS REVIEW"):
        assert phrase in text


def test_code_prompt_stops_without_control_matrix():
    class Dummy:
        project = ""
    text = AgentRunnerMixin._implementation_controls_block(Dummy(), "BI-PF-9999")
    assert "IMPLEMENTATION CONTROL CONTRACT" in text
    assert "STOP and create the control matrix" in text
