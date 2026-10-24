"""Gate decision guards (BI-PF-1471): HIL confirmation is mandatory."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import gate_decisions as gd  # noqa: E402


class FakeBacklog:
    def __init__(self):
        self.item = {"id": "BI-T", "decisions": []}

    def get_epic(self, scope, project, eid):
        return self.item

    def update(self, scope, project, eid, **fields):
        self.item.update(fields)
        return self.item


def test_requires_hil_confirmation():
    assert gd.record_gate_decision(FakeBacklog(), "product_forge", None, "BI-T", 1, "APPROVE", "hil:test") is None
    assert gd.record_gate_decision(FakeBacklog(), "product_forge", None, "BI-T", 1, "APPROVE", "system:auto",
                                   hil_confirmed=True) is None
