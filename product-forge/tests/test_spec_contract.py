import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import spec_contract as sc


def row(**kw):
    r = {"id": "C-1", "ac": "AC-1", "fr": "FR-1", "kind": "failure",
         "control": "x", "symbol": "scripts/dev/spec_contract.py:problems",
         "positive_test": "tests/test_spec_contract.py", "negative_test": "tests/test_spec_contract.py",
         "evidence": "pytest tests/test_spec_contract.py", "candidate_sha": "abc123"}
    r.update(kw)
    return r


def item(rows=None):
    return {
        "id": "BI-PF-9999", "acceptance_criteria": ["AC"],
        "api_impact": {"needs_api": False},
        "design_pack": {
            "rollback": "revert", "contracts": {"config": {"A": "1"}, "api": {}},
            "implementation_controls": rows if rows is not None else [row()],
            "ac_evidence": [{"ac": "AC-1", "candidate_sha": "abc123"}],
            "coverage": [{"fr": "FR-1", "candidate_sha": "abc123"}],
        },
        "functional_spec": {"rollback": "revert", "config_contract": {"A": "1"},
                            "traceability": [{"fr": "FR-1", "candidate_sha": "abc123"}]},
        "spec_pack": {"applicability": []},
    }


def full_rows():
    return [row(), row(id="C-2", kind="security", symbol="scripts/dev/spec_contract.py:impact_table"),
            row(id="C-3", kind="config", symbol="scripts/dev/spec_contract.py:main"),
            row(id="C-4", kind="observability", symbol="scripts/dev/spec_contract.py:enforced")]


def test_compile_valid():
    assert sc.problems(item(full_rows())) == []


def test_config_drift_fails():
    it = item(full_rows()); it["functional_spec"]["config_contract"] = {"A": "2"}
    assert any("config_contract differs" in p for p in sc.problems(it))


def test_rollback_drift_fails():
    it = item(full_rows()); it["functional_spec"]["rollback"] = "other"
    assert any("rollback differs" in p for p in sc.problems(it))


def test_missing_control_fails():
    assert any("AC-1 has no control" in p for p in sc.problems(item([])))


def test_missing_sha_fails():
    rows = full_rows(); rows[0].pop("candidate_sha")
    assert any("candidate_sha missing" in p for p in sc.problems(item(rows)))


def test_api_contract_required():
    it = item(full_rows()); it["api_impact"] = {"needs_api": True}
    assert any("api contract missing method" in p for p in sc.problems(it))


def test_invalid_na_fails():
    it = item(full_rows()); it["spec_pack"] = {"applicability": [{"spec": "x", "status": "N/A", "reason": "no"}]}
    assert any("N/A reason too short" in p for p in sc.problems(it))


def test_impact_table_generated():
    table = sc.impact_table(item(full_rows()))
    assert table and table[0]["control"] == "C-1"


def test_duplicate_symbol_fails():
    rows = full_rows(); rows[1]["symbol"] = rows[0]["symbol"]
    assert any("duplicate symbol" in p for p in sc.problems(item(rows)))


def test_fr_without_control_fails():
    it = item(full_rows()); it["functional_spec"]["requirements"] = [{"id": "FR-9"}]
    assert any("FR-9 has no control" in p for p in sc.problems(it))


def test_precheck_orders_spec_contract_before_architect_review():
    import sys
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))
    import precheck
    ids = [g[0] for g in precheck._GATES]
    assert ids.index("spec-contract") < ids.index("architect-review")
