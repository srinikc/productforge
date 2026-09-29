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


# ── auto-route (BI-0227 execution) ───────────────────────────────────────────
# In-process, per-run overrides: agent_id -> tier. Consulted by the model resolver so a
# retry after a failed gate runs on the stronger tier. Never persisted (state) — the loop
# clears it on success. Opt-in via PIPELINE_AUTO_ESCALATE=1 (default off).
_OVERRIDES: Dict[str, str] = {}

_PROFILE_CACHE = None


def _config() -> Dict:
    global _PROFILE_CACHE
    if _PROFILE_CACHE is None:
        try:
            with open(_TIER_CFG, "r", encoding="utf-8-sig") as f:
                _PROFILE_CACHE = json.load(f) or {}
        except Exception:
            _PROFILE_CACHE = {}
    return _PROFILE_CACHE


def auto_enabled() -> bool:
    return os.getenv("PIPELINE_AUTO_ESCALATE", "0").strip().lower() in ("1", "true", "yes", "on")


def set_override(agent_id: str, tier: str) -> None:
    if agent_id:
        _OVERRIDES[str(agent_id)] = str(tier or "")


def get_override(agent_id: str) -> str:
    return _OVERRIDES.get(str(agent_id), "")


def clear_override(agent_id: str = "") -> None:
    if agent_id:
        _OVERRIDES.pop(str(agent_id), None)
    else:
        _OVERRIDES.clear()


def tier_agent_model(tier: str, agent_id: str):
    """Resolve a profile's model/provider/endpoint for an agent, or None if the profile
    defines no usable model (e.g. the base ``actual`` profile - no cross-profile change)."""
    prof = (_config().get("profiles") or {}).get(str(tier or ""))
    if not isinstance(prof, dict):
        return None
    entry = (prof.get("agents") or {}).get(str(agent_id)) or {}
    model = entry.get("model") or prof.get("default_model")
    if not model:
        return None
    meta = (prof.get("models") or {}).get(model) or {}
    return {"model": model,
            "provider": meta.get("provider") or prof.get("provider") or "",
            "api_endpoint": meta.get("api_endpoint") or prof.get("api_endpoint") or ""}
