"""M0.7 execution contract: missing fields => BLOCKED (fail closed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import execution_contract as ec  # noqa: E402


def test_full_contract_is_ok():
    c = ec.build("proj", "run-1", "1", "design", "produce the design", ["design-output.md"])
    assert ec.validate(c)["status"] == "OK" and ec.validate(c)["ok"] is True


def test_missing_fields_block():
    bad = ec.build("", "", "1", "design", "", [])
    v = ec.validate(bad)
    assert v["status"] == "BLOCKED" and v["missing"]
