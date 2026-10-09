"""BI-PF-0865: KNOWN_AGENTS must be complete (every agent card is known) + ordered core preserved."""
import glob
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core.agent_structure import KNOWN_AGENTS  # noqa: E402


def test_known_agents_covers_every_agent_card():
    cards = {os.path.basename(p)[: -len(".agent.json")]
             for p in glob.glob(str(ROOT / "agents" / "*.agent.json"))}
    assert cards, "no agent cards found"
    missing = cards - set(KNOWN_AGENTS)
    assert not missing, f"agents with cards but not KNOWN: {sorted(missing)}"


def test_core_pipeline_order_preserved():
    for a in ("orchestrator", "ideation", "design", "architect", "implement", "code-review"):
        assert a in KNOWN_AGENTS
    assert KNOWN_AGENTS[:6] == ["orchestrator", "ideation", "design", "architect", "implement", "code-review"]
