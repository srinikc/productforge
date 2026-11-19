import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import delivery_state_check as dsc


def test_requires_all_states():
    item = {"delivery_states": {"code_complete": True, "integration_complete": True,
                                "validation_complete": True, "quality_approved": True,
                                "delivery_complete": False}}
    assert any("delivery state not true" in p for p in dsc.problems(item))


def test_delivery_complete_requires_predecessors():
    item = {"delivery_states": {"delivery_complete": True}}
    assert any("without" in p for p in dsc.problems(item))


def test_escaped_defect_requires_rcca():
    item = {"delivery_states": {s: True for s in dsc.STATES}, "escaped_defect": True, "rcca": {}}
    assert any("RCCA" in p for p in dsc.problems(item))
