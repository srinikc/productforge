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
