"""Dynamic tool selection per agent — from role + knowledge + project need, not a fixed card.

The agent card lists a BASE tool set; this adds/removes tools based on the agent's role and
declared knowledge (e.g. a research/market/domain role gets `http_get`), so tools follow the
agent's *need*, not a static list. Conservative: never removes a tool the card granted; only
adds when the role clearly needs it.

Owner: this module (pure function).
"""
import json
import os
from typing import Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WEB_TOOLS = ("http_get",)
RESEARCH_MARKERS = ("research", "market", "competit", "domain", "analyst", "analysis",
                    "pricing", "gtm", "growth", "trend")


def _capabilities(agent_id: str) -> Dict:
    try:
        caps = json.load(open(os.path.join(REPO, "config", "agent-capabilities.json"),
                              encoding="utf-8")).get("agents", {})
        return caps.get(agent_id, {}) or {}
    except Exception:
        return {}


def tools_for(agent_id: str, base_tools: Optional[List[str]] = None,
              project_dir: str = "", knowledge: Optional[List[str]] = None,
              description: str = "") -> List[str]:
    """Effective tools for an agent = base (card) + role/need-driven additions."""
    out = list(base_tools or [])
    caps = _capabilities(agent_id)
    know = [str(x).lower() for x in (knowledge or caps.get("knowledge") or [])]
    blob = " ".join([agent_id.lower(), (description or "").lower()]
                    + know + [str(x).lower() for x in (caps.get("skills") or [])])
    if any(m in blob for m in RESEARCH_MARKERS):
        for t in WEB_TOOLS:
            if t not in out:
                out.append(t)
    return sorted(set(out))


def describe(agent_id: str, base_tools=None, **kw) -> Dict:
    base = set(base_tools or [])
    eff = set(tools_for(agent_id, base_tools=base_tools, **kw))
    return {"agent": agent_id, "base": sorted(base), "effective": sorted(eff),
            "added": sorted(eff - base), "removed": sorted(base - eff)}
