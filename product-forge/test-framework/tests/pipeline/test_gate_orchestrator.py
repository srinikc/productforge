"""Unit tests for Enterprise Autonomous Gate Orchestrator (BI-PF-1599)."""
import os
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

from core import backlog
import gate_orchestrator as go


def test_default_mode_is_hil():
    item = {"id": "BI-PF-TEST", "title": "Test Item"}
    assert backlog.get_execution_mode(item) == "hil"

    item_explicit = {"id": "BI-PF-TEST", "execution_mode": "hil"}
    assert backlog.get_execution_mode(item_explicit) == "hil"


def test_auto_mode_resolution():
    item = {"id": "BI-PF-TEST", "execution_mode": "auto"}
    assert backlog.get_execution_mode(item) == "auto"


def test_env_mode_override(monkeypatch):
    monkeypatch.setenv("PF_GATE_MODE", "auto")
    item = {"id": "BI-PF-TEST", "execution_mode": "hil"}
    assert backlog.get_execution_mode(item) == "auto"

    monkeypatch.setenv("PF_GATE_MODE", "hil")
    item_auto = {"id": "BI-PF-TEST", "execution_mode": "auto"}
    assert backlog.get_execution_mode(item_auto) == "hil"


def test_set_execution_mode(monkeypatch):
    test_item = {"id": "BI-PF-9999", "execution_mode": "hil"}
    monkeypatch.setattr(backlog, "update", lambda sc, pr, iid, **kw: dict(test_item, **kw))
    
    updated = backlog.set_execution_mode("product_forge", None, "BI-PF-9999", "auto")
    assert updated["execution_mode"] == "auto"

    with pytest.raises(ValueError, match="Invalid execution_mode"):
        backlog.set_execution_mode("product_forge", None, "BI-PF-9999", "invalid_mode")


def test_hil_mode_halts_at_gate1(monkeypatch):
    fake_item = {
        "id": "BI-PF-TEST",
        "title": "Test Item",
        "execution_mode": "hil",
        "decisions": []
    }
    monkeypatch.setattr(backlog, "get_epic", lambda sc, pr, iid: fake_item)
    orch = go.GateOrchestrator("BI-PF-TEST", mode="hil")
    
    res = orch.run_gate1()
    assert res is False
    assert orch.stages.get("gate1") == "HALTED"


def test_auto_mode_approves_gate1(monkeypatch):
    fake_item = {
        "id": "BI-PF-TEST",
        "title": "Test Item",
        "execution_mode": "auto",
        "decisions": []
    }
    monkeypatch.setattr(backlog, "get_epic", lambda sc, pr, iid: fake_item)
    
    approved = False
    def fake_approve(item_id, scope="product_forge", project=None, by="hil:auto"):
        nonlocal approved
        approved = True
        return {"ok": True, "by": by}

    monkeypatch.setattr(go.gate1_approve, "approve", fake_approve)
    orch = go.GateOrchestrator("BI-PF-TEST", mode="auto")
    
    res = orch.run_gate1()
    assert res is True
    assert approved is True
    assert orch.stages.get("gate1") == "PASS"


def test_execute_all_plan_stops_at_requested_milestone(monkeypatch):
    fake_item = {
        "id": "BI-PF-TEST",
        "title": "Test Item",
        "execution_mode": "auto",
        "decisions": []
    }
    monkeypatch.setattr(backlog, "get_epic", lambda sc, pr, iid: fake_item)
    orch = go.GateOrchestrator("BI-PF-TEST", mode="auto")
    
    def mock_g0():
        orch.stages["gate0"] = "PASS"
        return True
    def mock_g1_5():
        orch.stages["gate1_5"] = "PASS"
        return True
    def mock_g1():
        orch.stages["gate1"] = "PASS"
        return True

    monkeypatch.setattr(orch, "run_gate0", mock_g0)
    monkeypatch.setattr(orch, "run_gate1_5", mock_g1_5)
    monkeypatch.setattr(orch, "run_gate1", mock_g1)
    
    result = orch.execute_all(stop_at="gate1", skip_delivery=True)
    assert result["ok"] is True
    assert "gate0" in orch.stages
    assert "gate1" in orch.stages
    assert "gate2" not in orch.stages
