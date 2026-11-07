"""Spec-chain tests: functional spec, conditional spec pack, and FR conformance."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import conformance_check
import functional_spec
import spec_pack


def _item():
    return json.loads((ROOT / "data" / "backlog" / "items" / ("BI-PF-1531" + "." + "json")).read_text(encoding="utf-8"))


def test_functional_spec_requires_behavior_sections():
    item = _item()
    bad = functional_spec.problems(item)
    assert bad == []
    broken = copy.deepcopy(item)
    broken["functional_spec"].pop("outcome")
    assert any("outcome" in b for b in functional_spec.problems(broken))


def test_functional_spec_rejects_placeholders():
    item = _item()
    broken = copy.deepcopy(item)
    broken["functional_spec"]["requirements"][0]["errors"] = "TBD"
    assert any("placeholder" in b for b in functional_spec.problems(broken))


def test_spec_pack_requires_na_reason():
    item = _item()
    assert spec_pack.problems(item) == []
    broken = copy.deepcopy(item)
    for row in broken["spec_pack"]["applicability"]:
        if row["status"] == "N/A":
            row["reason"] = ""
            break
    assert any("N/A reason" in b for b in spec_pack.problems(broken))


def test_conformance_requires_fr_coverage():
    item = _item()
    assert conformance_check.problems(item) == []
    broken = copy.deepcopy(item)
    broken["design_pack"]["coverage"] = [r for r in broken["design_pack"]["coverage"] if r.get("fr") != "FR-1"]
    assert any("FR-1" in b for b in conformance_check.problems(broken))


def test_fix_guard_requires_row():
    import copy
    import fix_guard
    item = _item()
    broken = copy.deepcopy(item)
    broken["fix_impact"] = []
    assert any("fix_impact" in b for b in fix_guard.problems(broken))
