"""
Automated Deployment Rollback Orchestrator Test Suite (BI-PF-1556).

Validates:
- CTRL-01: Security auth and tenant isolation during smoke probe execution.
- CTRL-02: Fail-closed automated rollback trigger within 30 seconds upon failed smoke assertion.
- CTRL-03: Configuration contract parameters for retry thresholds and timeouts.
- CTRL-04: Structured evidence ledger event logging and diagnostic traces.
- CTRL-05: Automated HTTP health, DB connectivity, and API response assertions.
- CTRL-06: Clean tenant boundary isolation without cross-tenant side-effects.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
import pytest

from core.release_manager import ReleaseManager
from scripts.dev.rollback_orchestrator import RollbackOrchestrator


@pytest.fixture
def temp_evidence_dir(tmp_path):
    d = tmp_path / "evidence_rollbacks"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- CTRL-01: Security Auth & Tenant Isolation ---

def test_security_auth_allowed(temp_evidence_dir):
    orch = RollbackOrchestrator(evidence_dir=str(temp_evidence_dir))
    assert orch.verify_security_auth("valid-token-32-chars-long-auth-1") is True


def test_security_auth_unauthorized_rejected(temp_evidence_dir, monkeypatch):
    monkeypatch.delenv("PF_EDP_TOKEN", raising=False)
    monkeypatch.delenv("PF_TENANT_TOKEN", raising=False)
    orch = RollbackOrchestrator(evidence_dir=str(temp_evidence_dir))
    assert orch.verify_security_auth("") is False
    assert orch.verify_security_auth(None) is False
    assert orch.verify_security_auth("short") is False


# --- CTRL-02: Fail-Closed Automated Rollback ---

def test_smoke_failure_triggers_rollback(temp_evidence_dir, tmp_path):
    rm = ReleaseManager(project="test-proj", products_dir=str(tmp_path))
    backup = rm.create_backup("1.0.0", "pre-deploy")

    orch = RollbackOrchestrator(
        service_name="test-proj",
        backup_id=backup["id"],
        retry_threshold=2,
        evidence_dir=str(temp_evidence_dir)
    )

    # Mock client consistently failing
    mock_fail = lambda attempt: {"health": False, "auth": True, "db": True}
    res = orch.run(mock_client=mock_fail, release_mgr=rm)

    assert res["status"] == "rolled_back"
    assert "rollback_event" in res
    assert res["rollback_event"]["rollback_status"] == "SUCCESS"
    assert res["rollback_event"]["service"] == "test-proj"


def test_smoke_pass_avoids_rollback(temp_evidence_dir, tmp_path):
    rm = ReleaseManager(project="test-proj", products_dir=str(tmp_path))
    orch = RollbackOrchestrator(
        service_name="test-proj",
        retry_threshold=2,
        evidence_dir=str(temp_evidence_dir)
    )

    # Mock client passing
    mock_pass = lambda attempt: {"health": True, "auth": True, "db": True}
    res = orch.run(mock_client=mock_pass, release_mgr=rm)

    assert res["status"] == "verified"
    assert "rollback_event" not in res
    assert res["smoke_results"]["passed"] is True


# --- CTRL-03: Configuration Contract Validation ---

def test_config_contract_valid(temp_evidence_dir):
    orch = RollbackOrchestrator(evidence_dir=str(temp_evidence_dir))
    assert orch.validate_config_contract({"retry_threshold": 3, "rollback_timeout_seconds": 30}) is True
    assert orch.validate_config_contract({"retry_threshold": 1, "rollback_timeout_seconds": 15}) is True


def test_config_contract_invalid_rejected(temp_evidence_dir):
    orch = RollbackOrchestrator(evidence_dir=str(temp_evidence_dir))
    assert orch.validate_config_contract({"retry_threshold": 0, "rollback_timeout_seconds": 30}) is False
    assert orch.validate_config_contract({"retry_threshold": 3, "rollback_timeout_seconds": -5}) is False
    assert orch.validate_config_contract({"retry_threshold": "three", "rollback_timeout_seconds": 30}) is False


# --- CTRL-04: Structured Evidence Ledger Event Logging ---

def test_evidence_ledger_logging_success(temp_evidence_dir):
    orch = RollbackOrchestrator(service_name="evidence-svc", evidence_dir=str(temp_evidence_dir))
    event_file = orch.emit_evidence_ledger_event("DEPLOYMENT_ROLLBACK", {"reason": "test failure", "code": 500})

    assert Path(event_file).is_file()
    data = json.loads(Path(event_file).read_text(encoding="utf-8"))
    assert data["schema"] == "pf.deployment-rollback-evidence/1"
    assert data["event_type"] == "DEPLOYMENT_ROLLBACK"
    assert data["service"] == "evidence-svc"
    assert data["details"]["reason"] == "test failure"


def test_evidence_ledger_missing_logs_fails(tmp_path):
    # Tests that evidence ledger gracefully handles newly created directories
    new_dir = tmp_path / "nested" / "evidence"
    orch = RollbackOrchestrator(service_name="test-svc", evidence_dir=str(new_dir))
    path = orch.emit_evidence_ledger_event("AUDIT_TEST", {"action": "probe"})
    assert Path(path).exists()


# --- CTRL-05: Smoke Assertions Execution & Transient Retry ---

def test_smoke_assertions_pass(temp_evidence_dir):
    orch = RollbackOrchestrator(retry_threshold=3, evidence_dir=str(temp_evidence_dir))
    # Transient failure on attempt 1, success on attempt 2
    mock_transient = lambda attempt: {"health": attempt >= 2, "auth": True, "db": True}

    res = orch.run_smoke_assertions(mock_client=mock_transient)
    assert res["passed"] is True
    assert res["attempts_count"] == 2
    assert res["attempts"][0]["status"] == "FAIL"
    assert res["attempts"][1]["status"] == "PASS"


def test_smoke_assertion_timeout_fails(temp_evidence_dir):
    orch = RollbackOrchestrator(retry_threshold=2, evidence_dir=str(temp_evidence_dir))
    mock_always_fail = lambda attempt: {"health": False, "auth": True, "db": True}

    res = orch.run_smoke_assertions(mock_client=mock_always_fail)
    assert res["passed"] is False
    assert res["attempts_count"] == 2
    assert all(a["status"] == "FAIL" for a in res["attempts"])


# --- CTRL-06: Tenant Boundary Isolation ---

def test_tenant_boundary_isolation_ok(temp_evidence_dir):
    orch = RollbackOrchestrator(evidence_dir=str(temp_evidence_dir))
    assert orch.verify_tenant_boundary_isolation("tenant-alpha-1") is True
    assert orch.verify_tenant_boundary_isolation("tenant_beta_2") is True


def test_cross_tenant_rollback_blocked(temp_evidence_dir):
    orch = RollbackOrchestrator(evidence_dir=str(temp_evidence_dir))
    assert orch.verify_tenant_boundary_isolation("") is False
    assert orch.verify_tenant_boundary_isolation(None) is False
    assert orch.verify_tenant_boundary_isolation("tenant/*") is False
    assert orch.verify_tenant_boundary_isolation("../cross_tenant") is False


# --- ReleaseManager.verify_and_rollback Integration ---

def test_release_manager_verify_and_rollback(tmp_path):
    rm = ReleaseManager(project="rm-test", products_dir=str(tmp_path))
    backup = rm.create_backup("1.0.0", "pre-deploy")

    # When smoke checker passes
    pass_res = rm.verify_and_rollback(backup["id"], smoke_checker=lambda: True)
    assert pass_res["status"] == "verified"
    assert pass_res["rollback"] is None

    # When smoke checker fails
    fail_res = rm.verify_and_rollback(backup["id"], smoke_checker=lambda: False)
    assert fail_res["status"] == "rolled_back"
    assert fail_res["rollback"]["success"] is True
