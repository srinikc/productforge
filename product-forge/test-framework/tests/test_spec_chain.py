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
    _fixture = {
        "id": "BI-PF-TEST", "created_at": "2026-11-08T00:00:00",
        "functional_spec": {
            "version": 1, "status": "APPROVED", "owner": "test", "source": "fixture",
            "design_ref": "engineering/design/BI-PF-TEST.md",
            "outcome": ["test outcome"], "actors": ["tester"], "scope": ["test"],
            "non_goals": ["none"], "assumptions": ["fixture"], "dependencies": ["none"],
            "domain": ["test"], "requirements": [{
                "id": "FR-1", "title": "test", "priority": "Must", "source": "test",
                "preconditions": "ready", "trigger": "call", "inputs": "input", "outputs": "output",
                "errors": "error", "auth": "test", "idempotency": "yes", "data_rules": "none",
                "edge_cases": "none", "acceptance": ["Given x When y Then z"], "verification": "pytest"
            }], "operation_matrix": [{"mode": "on", "operation": "read", "scope": "test", "actor": "tester", "expected": "ok", "error": "none"}],
            "config_contract": [{"name": "X", "default": "on", "precedence": "env", "valid_values": "on/off", "empty_behavior": "on", "invalid_behavior": "fail", "startup_validation": "yes"}],
            "nfr": ["test"], "data_lifecycle": ["test"], "compatibility": ["test"],
            "rollback": ["test"], "observability": ["test"],
            "traceability": [{"fr": "FR-1", "design": "coverage", "test": "pytest", "evidence": ["test-framework/tests/test_spec_chain.py"]}],
            "open_questions": ["none"], "dod": ["test"],
            "functional_sha": "x"
        },
        "design_pack": {"functional_ref": "engineering/specs/BI-PF-TEST.md", "coverage": [{"fr": "FR-1", "ac": "AC-1", "tests": ["pytest"], "evidence": ["test-framework/tests/test_spec_chain.py"]}]},
        "spec_pack": {"version": 1, "status": "APPROVED", "functional_ref": "engineering/specs/BI-PF-TEST.md", "design_ref": "engineering/design/BI-PF-TEST.md", "applicability": []},
        "fix_impact": []
    }
    item = _fixture
    item["functional_spec"]["functional_sha"] = functional_spec._sha(item["functional_spec"])
    item["spec_pack"]["applicability"] = [
        {"spec": name, "status": "N/A", "owner": "test", "reason": "fixture does not exercise this conditional spec"}
        for name in spec_pack._cfg()["required_specs"]
    ]
    return item


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
    assert any("coverage" in b for b in conformance_check.problems(broken))


def test_fix_guard_requires_row():
    import copy
    import fix_guard
    item = _item()
    broken = copy.deepcopy(item)
    broken["fix_impact"] = []
    assert any("fix_impact" in b for b in fix_guard.problems(broken))
