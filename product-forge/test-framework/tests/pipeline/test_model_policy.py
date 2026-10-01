"""BI-PF-0278: per-model eligibility policy — schema, eligibility, gate/strategy integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import model_policy as P  # noqa: E402


def test_schema_valid():
    assert P.validate() == []
    assert P.SCHEMA_VERSION == 1


def test_policy_for_resolves_and_defaults():
    pol = P.policy_for("gpt-5.6-sol")
    assert pol and "allowed_tasks" in pol and "fallback" in pol


def test_allowed_and_restricted_tasks():
    # gpt-5.6-luna allows chat, restricts medical_advice
    assert P.eligible("gpt-5.6-luna", "chat")["ok"] is True
    assert P.eligible("gpt-5.6-luna", "medical_advice")["ok"] is False
    # coding not in luna's allowed list -> denied
    assert P.eligible("gpt-5.6-luna", "coding")["ok"] is False


def test_max_task_cost_denies():
    r = P.eligible("gpt-5.6-luna", "chat", est_cost=999.0)
    assert r["ok"] is False
    assert any("max_task_cost" in x for x in r["reasons"])


def test_fallback_and_independent_review_returned():
    r = P.eligible("gpt-5.6-terra", "chat")
    assert r["policy_found"] is True
    assert r["fallback"] == ["gpt-5.6-luna"]
    assert P.eligible("gpt-5.6-sol", "chat")["independent_review"] is True


def test_unknown_model_fail_open_unless_strict(monkeypatch):
    monkeypatch.delenv("MODEL_GATE_REJECT_UNKNOWN", raising=False)
    assert P.eligible("_no_policy_model", "chat")["ok"] is True
    monkeypatch.setenv("MODEL_GATE_REJECT_UNKNOWN", "1")
    assert P.eligible("_no_policy_model", "chat")["ok"] is False


def test_gate_marks_policy_blocked():
    from core import model_gate as G
    profile = {"default_tier": "t", "agents": {"a1": {"model": "gpt-5.6-luna", "task": "medical_advice"}}}
    rep = G.evaluate(profile)
    st = rep["entries"][0]["status"]
    assert st == "POLICY_BLOCKED"
    assert rep["summary"]["policy_blocked"] == 1


def test_strategy_report_surfaces_policy(tmp_path):
    from core import model_strategy as M
    rep = M.assess(str(tmp_path), phase="b")
    assert "model_policy" in rep
