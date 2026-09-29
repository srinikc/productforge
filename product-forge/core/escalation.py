"""Capability fallback + escalate-on-failure routing (BI-0227).

When an agent fails a gate (compliance/quality), the pipeline should be able to route to a
STRONGER tier (escalate). This module provides the escalation ladder (weak -> strong),
filtered to the tiers present in config/model-tier.json, plus a recommendation record.
"""
import json
import os
from typing import Dict, List

try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import sys as _pf_sys
    _pf_d = os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = os.path.dirname(_pf_d)
        if os.path.isfile(os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

_TIER_CFG = os.path.join(str(_PF_ROOT), "config", "model-tier.json")
# weak -> strong escalation ladder (filtered to configured profiles)
_LADDER = ["free-trial-fast", "free-trial", "kctier", "actual-balanced", "actual"]


def profiles() -> List[str]:
    try:
        with open(_TIER_CFG, "r", encoding="utf-8-sig") as f:
            return list(((json.load(f) or {}).get("profiles") or {}).keys())
    except Exception:
        return []


def ladder() -> List[str]:
    prof = profiles()
    lad = [t for t in _LADDER if t in prof]
    return lad or prof


def next_tier(tier: str) -> str:
    """The next stronger tier, or '' if already at the top. Unknown -> strongest."""
    lad = ladder()
    if not lad:
        return ""
    t = str(tier or "")
    if t in lad:
        i = lad.index(t)
        return lad[i + 1] if i + 1 < len(lad) else ""
    return lad[-1]


def recommend(agent_id: str, tier: str = "") -> Dict:
    """Escalation recommendation for an agent that failed a gate."""
    return {"agent": agent_id, "from_tier": tier, "escalate_to": next_tier(tier)}
