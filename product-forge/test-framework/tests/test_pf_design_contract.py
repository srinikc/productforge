"""Generic design/delivery framework checks."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import design_contract_check as dcc  # noqa: E402
import ownership_check as own  # noqa: E402
import review_ledger as rl  # noqa: E402


def valid_item():
    return {
        "id": "PF-TEST", "created_at": "2026-10-28T00:00:00", "status": "new",
        "epic": "PF-EPIC", "brief": {"problem": "p", "what_adds": "w", "why": "y", "who_feels": "h"},
        "risks": ["risk with mitigation: guard"],
        "review": {"impact_review": [{"claim": "API CHECK", "verdict": "aligned",
                                       "evidence": "code", "recommendation": "keep"}]},
        "acceptance_criteria": ["works"],
        "affected_files": ["go/edpsvc/main.go"],
        "design_pack": {
            "contract_version": 1,
            "standards": ["AGENTS.md", "docs/ENGINEERING_OPERATING_STANDARD.md",
                          "docs/REVIEW-GATES-LIFECYCLE.md", "docs/DESIGN-QUALITY-RCCA.md",
                          "docs/WORK-EXECUTION-CONTRACT.md"],
            "code_guidelines": ["docs/guidelines/coding/go/pf-go.md", "docs/guidelines/coding/go/style-guide.md"],
            "controls": [{"id": "CTL-1", "dimension": "runtime", "applies_to": "go/edpsvc/main.go", "check": "go test ./...", "evidence": "config/design-contract.json", "failure_behavior": "block", "owner": "edpsvc"}],
            "guideline_coverage": [
                {"guideline": "docs/guidelines/coding/go/pf-go.md", "applies_to": "go/edpsvc/main.go", "evidence": "config/design-contract.json", "check": "go test ./..."},
                {"guideline": "docs/guidelines/coding/go/style-guide.md", "applies_to": "go/edpsvc/main.go", "evidence": "config/design-contract.json", "check": "go test ./..."},
            ],
            "review_scope": {"ac_ids": ["AC-1"], "components": ["go/edpsvc"], "files": ["go/edpsvc/main.go"], "exclude": ["unrelated refactors"]},
            "requirements": ["works"],
            "coverage": [{
                "ac": "AC-1", "entrypoint": "go/edpsvc/main.go::main",
                "call_sites": ["main"], "adapter": "postgres", "contract": "GET /x",
                "failure_cases": ["401"], "tests": ["test-framework/tests/test_pf_design_contract.py::test_contract_accepts_valid_item"],
                "evidence": ["config/design-contract.json"],
            }],
            "runtime_contract": {"trigger": "GET /x", "entrypoint": "go/edpsvc/main.go::main",
                                 "call_sites": ["main"], "adapter": "postgres", "contract": "GET /x",
                                 "failure_behavior": "401", "observable_result": "200"},
            "proof_plan": {"failing_test": "x", "red_evidence": "404", "green_evidence": "200"},
            "scope": ["x"], "non_goals": ["y"], "failure_matrix": ["x"], "test_matrix": ["x"],
            "observability": ["x"], "rollout": "x", "rollback": "x", "stop_conditions": ["x"],
        },
        "review_dispositions": {},
    }


def test_contract_rejects_missing_coverage():
    item = valid_item()
    item["design_pack"]["coverage"] = []
    assert any("coverage missing" in p for p in dcc.problems("PF-TEST", item))


def test_contract_rejects_placeholder():
    item = valid_item()
    item["design_pack"]["contract"] = "TBD"
    assert any("placeholder" in p for p in dcc.problems("PF-TEST", item))


def test_contract_accepts_valid_item():
    assert dcc.problems("PF-TEST", valid_item()) == []


def test_actioned_requires_evidence_reference():
    item = valid_item()
    item["review_dispositions"] = {"design": {"sig:x": {"status": "ACTIONED", "note": "done"}}}
    assert any("ACTIONED without evidence" in p for p in dcc.problems("PF-TEST", item))


def test_ownership_rejects_unowned_file():
    item = valid_item()
    item["affected_files"] = ["unknown/file.go"]
    item["design_pack"]["contracts"] = {"files": []}
    assert own.problems("PF-TEST", item)


def test_ledger_rejects_second_review_without_material_approval():
    item = {"review_ledger": [
        {"mode": "diff", "review_sha": "a", "at": "2026-01-01T00:00:00+00:00"},
        {"mode": "diff", "review_sha": "b", "at": "2026-01-02T00:00:00+00:00"},
    ], "decisions": []}
    assert rl.problems(item, "diff")

def test_ledger_requires_contract_items_to_have_a_ledger():
    item = valid_item()
    assert any("REVIEW_LEDGER_MISSING" in p for p in rl.problems(item, "design"))
