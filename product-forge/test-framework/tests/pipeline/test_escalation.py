"""BI-0227: capability fallback / escalate-on-failure ladder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import escalation as e  # noqa: E402


def test_ladder_is_subset_of_profiles():
    assert set(e.ladder()).issubset(set(e.profiles()) | set(e.ladder()))


def test_next_tier_escalates_and_tops_out():
    lad = e.ladder()
    assert lad, "expected configured tiers"
    assert e.next_tier(lad[0]) == lad[1]
    assert e.next_tier(lad[-1]) == ""
    assert e.next_tier("unknown-tier") == lad[-1]


def test_override_set_get_clear():
    e.clear_override()
    assert e.get_override("architect") == ""
    e.set_override("architect", "actual-balanced")
    assert e.get_override("architect") == "actual-balanced"
    e.clear_override("architect")
    assert e.get_override("architect") == ""


def test_tier_agent_model_resolves_profile():
    sub = e.tier_agent_model("actual-balanced", "architect")
    assert sub and sub["model"] == "deepseek-v4-pro" and sub["provider"] == "opencode-go"
    assert e.tier_agent_model("actual", "architect") is None
