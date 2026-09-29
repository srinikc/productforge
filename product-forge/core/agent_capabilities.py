"""Capability steering (BI-0221 / BI-0222 / BI-0223).

Per-agent **capability vector** (config/agent-capability-vector.json) + a **capability-aware
request builder** that enables a capability ONLY when the chosen model supports it — otherwise
it degrades and flags it (so a call never asks a model for something it cannot do, and the
pipeline does not over-generate reasoning/structured output where it is not needed).
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json
import os
from typing import Dict, List

_CFG = os.path.join(str(_PF_ROOT), "config", "agent-capability-vector.json")
_cache = None


def config() -> Dict:
    global _cache
    if _cache is not None:
        return _cache
    data = {}
    try:
        with open(_CFG, "r", encoding="utf-8-sig") as f:
            data = json.load(f) or {}
    except Exception:
        data = {}
    _cache = {"defaults": data.get("defaults") or {}, "agents": data.get("agents") or {}}
    return _cache


def vector(agent_id: str) -> Dict:
    """The full capability vector for an agent (defaults merged with the agent's overrides)."""
    c = config()
    v = dict(c["defaults"])
    v.update(c["agents"].get(str(agent_id), {}) or {})
    return v


def reasoning_enabled(agent_id: str) -> bool:
    return bool(vector(agent_id).get("needs_reasoning"))


def build_request(agent_id: str, model_caps: Dict) -> Dict:
    """Capability-aware request params for one call (BI-0222).

    Enables each capability only if the agent needs it AND the model supports it.
    Returns the chosen params plus a ``degraded`` list of capabilities that were needed
    but could not be satisfied (the caller may fall back / escalate — BI-0227).
    """
    v = vector(agent_id)
    caps = model_caps or {}
    mods = caps.get("modalities") or []
    structured = bool(v.get("needs_structured")) and bool(caps.get("structured_outputs", False))
    reasoning = bool(v.get("needs_reasoning")) and bool(caps.get("reasoning", True))
    vision = bool(v.get("needs_vision")) and (bool(caps.get("vision")) or ("image" in mods))
    tools = bool(v.get("needs_tools"))
    out = {
        "reasoning": reasoning,
        "reasoning_effort": str(v.get("reasoning_effort") or "low"),
        "structured": structured,
        "vision": vision,
        "tools": tools,
        "min_output": int(v.get("min_output") or 0),
        "min_context": int(v.get("min_context") or 0),
    }
    degraded: List[str] = []
    if v.get("needs_reasoning") and not reasoning:
        degraded.append("reasoning")
    if v.get("needs_structured") and not structured:
        degraded.append("structured")
    if v.get("needs_vision") and not vision:
        degraded.append("vision")
    out["degraded"] = degraded
    return out


def apply_to_request(request: Dict, decision: Dict, provider: str = "") -> Dict:
    """Apply a capability decision to an API request dict (BI-0222 execution).

    Only mutates what the decision justifies; a falsy/empty decision is a safe no-op.
    Reasoning is only attached for providers known to accept it (openrouter); when the
    decision says no reasoning, any stale ``reasoning`` key is dropped.
    """
    if not isinstance(request, dict) or not decision:
        return request
    try:
        want = int(decision.get("min_output") or 0)
        if want and int(request.get("max_tokens") or 0) < want:
            request["max_tokens"] = want
    except Exception:
        pass
    if decision.get("reasoning"):
        if provider in ("openrouter", "openrouter.ai"):
            request["reasoning"] = {"effort": str(decision.get("reasoning_effort") or "low")}
    else:
        request.pop("reasoning", None)
    return request
