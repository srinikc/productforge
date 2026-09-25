"""
Tests for the 360-degree discovery panel (core/discovery_panel.py).

Guarantees covered:
  * config loads (agents / sub-agent rollup / question cap)
  * hierarchy exposes a lead's sub-agents
  * panel builds from an injected llm_call and parses fenced JSON questions
  * offline fallback builds curated questions when no LLM is available
  * answers: empty == accept the recommendation; override == not accepted
  * store round-trips; panel converts to DiscoveryAnswers for synthesis
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.discovery_panel as dp  # noqa: E402


def _small_cfg():
    cfg = dict(dp.load_config())
    cfg["agents"] = ["ux-ia", "architect"]
    return cfg


def test_config_defaults():
    cfg = dp.load_config()
    assert len(cfg["agents"]) >= 15
    assert cfg["max_questions_per_agent"] == 3
    assert cfg["include_sub_agents"] is True


def test_sub_agents_from_hierarchy():
    subs = dp.sub_agents_of("design")
    assert "ux-ia" in subs and "design_critic" in subs


def test_offline_fallback_builds_questions():
    p = dp.build_panel("A pipeline dashboard", "P", "", llm_call=None, config=_small_cfg())
    assert p["totals"]["agents"] == 2
    assert p["totals"]["questions"] > 0
    for q in dp.all_questions(p):
        assert q["question"] and q["source_agent"] in ("ux-ia", "architect")


def test_parses_fenced_json_questions():
    reply = ('sure:\n```json\n{"questions": [{"question": "Who uses it?", '
             '"recommendation": "agents"}]}\n```')
    qs = dp._parse_questions(reply, 3)
    assert qs == [{"question": "Who uses it?", "recommendation": "agents"}]


def test_llm_panel_uses_generated_questions():
    def fake_llm(prompt, agent_id):
        return json.dumps({"questions": [
            {"question": f"Q from {agent_id}?", "recommendation": f"rec-{agent_id}"}]})

    p = dp.build_panel("idea", "P", "", llm_call=fake_llm, config=_small_cfg())
    q = dp.all_questions(p)[0]
    assert q["recommendation"].startswith("rec-")
    assert q["id"].endswith(":1")


def test_live_only_skips_agent_on_llm_failure():
    """live_questions_only=True: a failing agent is skipped, NOT given curated questions."""
    calls = []

    def bad_llm(prompt, agent_id):
        calls.append(agent_id)
        return "no json here at all"

    cfg = _small_cfg()
    cfg["live_questions_only"] = True
    p = dp.build_panel("idea", "P", "", llm_call=bad_llm, config=cfg)
    assert p["totals"]["questions"] == 0
    assert p["agents"] == []
    assert set(p["skipped_agents"]) == {"ux-ia", "architect"}
    assert calls.count("ux-ia") == 2  # one retry


def test_record_answers_accept_vs_override():
    def fake_llm(prompt, agent_id):
        return json.dumps({"questions": [
            {"question": f"Q from {agent_id}?", "recommendation": f"rec-{agent_id}"}]})

    p = dp.build_panel("idea", "P", "", llm_call=fake_llm, config=_small_cfg())
    qs = dp.all_questions(p)
    # BI-0048: an EMPTY answer is NO LONGER auto-accepted; explicit "accept" accepts.
    answers = {q["id"]: "" for q in qs}          # left blank -> unanswered
    answers[qs[1]["id"]] = "accept"              # explicitly accept the recommendation
    answers[qs[0]["id"]] = "my own clarification"  # override the first
    dp.record_answers(p, answers)
    assert qs[0]["answer"] == "my own clarification" and qs[0]["accepted"] is False
    assert qs[1]["answer"] == qs[1]["recommendation"] and qs[1]["accepted"] is True
    # the blank one is recorded as unanswered, not silently accepted
    if len(qs) > 2:
        assert qs[2].get("unanswered") is True and qs[2]["accepted"] is False


def test_synthesis_agent_mapping():
    """BI-0080: panel agents must map to synthesis buckets used by discovery_engine."""
    assert dp.synthesis_agent("product-analyzer") == "product_analyst"
    assert dp.synthesis_agent("researcher") == "product_analyst"
    assert dp.synthesis_agent("ux-ia") == "ux_researcher"
    assert dp.synthesis_agent("design") == "ux_researcher"
    assert dp.synthesis_agent("architect") == "business_analyst"
    assert dp.synthesis_agent("") == "business_analyst"


def test_panel_answers_stamped_with_synthesis_bucket():
    def fake_llm(prompt, agent_id):
        return json.dumps({"questions": [
            {"question": f"Q {agent_id}?", "recommendation": "r"}]})

    cfg = dict(dp.load_config())
    cfg["agents"] = ["product-analyzer", "ux-ia"]
    p = dp.build_panel("idea", "P", "", llm_call=fake_llm, config=cfg)
    dp.record_answers(p, {q["id"]: "" for q in dp.all_questions(p)})
    buckets = {a.agent for a in dp.to_discovery_answers(p)}
    assert buckets == {"product_analyst", "ux_researcher"}


def test_store_roundtrip_and_discovery_answers(tmp_path):
    def fake_llm(prompt, agent_id):
        return json.dumps({"questions": [
            {"question": f"Q from {agent_id}?", "recommendation": f"rec-{agent_id}"}]})

    p = dp.build_panel("idea", "P", "", llm_call=fake_llm, config=_small_cfg())
    dp.record_answers(p, {q["id"]: "" for q in dp.all_questions(p)})
    path = dp.save_panel(str(tmp_path), p)
    assert Path(path).exists()
    reloaded = dp.load_panel(str(tmp_path))
    assert reloaded["totals"] == p["totals"]
    assert len(dp.to_discovery_answers(reloaded)) == p["totals"]["questions"]


def test_round2_followups_for_vague_and_overridden():
    """BI-0037: round-2 asks sharper follow-ups for vague/overridden/unanswered answers."""
    p = {"agents": [{"id": "design", "questions": [
        {"id": "design:1", "question": "Users?", "recommendation": "devs", "answer": "", "unanswered": True},
        {"id": "design:2", "question": "DB?", "recommendation": "postgres", "answer": "mysql", "accepted": False},
        {"id": "design:3", "question": "Scope?", "recommendation": "mvp", "answer": "a full production build with many things", "accepted": True},
    ]}]}
    need = dp.needs_followup(p)
    assert len(need) == 2  # unanswered + overridden; the accepted long answer is fine
    p = dp.build_round2(p)
    assert p["round2"]["status"] == "generated" and p["round2"]["followups"] == 2
    r2 = [q for q in p["agents"][0]["questions"] if q.get("round") == 2]
    assert len(r2) == 2 and all(q.get("follows") for q in r2)
