"""Rebuild a tier's per-agent allocation from LEAD role->model + hierarchy.

Sub-agents are derived via core.agent_hierarchy (sub.model := parent.model),
so the mapping is a rule, not hand-maintained.

Usage: python scripts/dev/build_tier_allocation.py [tier]   (default free-trial-fast)
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from core.agent_hierarchy import descendants, parents

P = "config/model-tier.json"
M1 = "nvidia/nemotron-3.5-lightning:free"
M2 = "cohere/north-mini-code:free"
M3 = "dots-studio/dots-3-note-preview:free"
M4 = "nemotron-3.5-lightning-free"
FREE = [M1, M2, M3]

# LEAD agents -> capability-appropriate primary model
LEAD = {
    # reasoning / planning
    "ideation": M1, "discovery": M1, "design": M1, "architect": M1, "researcher": M1,
    "orchestrator": M1, "consensus": M1, "iterative_evaluator": M1, "guardian": M1,
    "observer": M1, "strategist": M1, "analyst": M1, "inference": M1, "product-analyzer": M1,
    "security": M1,
    # code / build / ops
    "implement": M2, "fix": M2, "devops": M2, "code-review": M2,
    # verification / QA
    "validate": M2,
    # content / docs / analysis
    "document": M3, "finops": M3, "customer-onboarding": M3, "agent_config": M2, "ingestion": M2,
}
DEFAULT = M1


def fallbacks(m):
    return [x for x in FREE if x != m] + [M4]


def build(tier):
    d = json.load(open(P, encoding="utf-8"))
    prof = d["profiles"][tier]
    agents = {}
    for lead, m in LEAD.items():
        agents[lead] = {"model": m, "fallback_models": fallbacks(m)}
    for lead in parents():
        pm = LEAD.get(lead)
        if not pm:
            # parent itself is a sub of something: resolve via root lead
            from core.agent_hierarchy import root_of
            pm = LEAD.get(root_of(lead), DEFAULT)
        for sub in descendants(lead):
            if sub not in agents:
                agents[sub] = {"model": pm, "fallback_models": fallbacks(pm)}
    prof["agents"] = agents
    prof["default_model"] = DEFAULT
    prof["default_fallback_models"] = fallbacks(DEFAULT)
    prof["models"] = {
        M1: {"provider": "openrouter", "api_endpoint": "https://openrouter.ai/api/v1/chat/completions"},
        M2: {"provider": "openrouter", "api_endpoint": "https://openrouter.ai/api/v1/chat/completions"},
        M3: {"provider": "openrouter", "api_endpoint": "https://openrouter.ai/api/v1/chat/completions"},
        M4: {"provider": "opencode-go", "api_endpoint": "https://opencode.ai/zen/v1/chat/completions"},
    }
    json.dump(d, open(P, "w", encoding="utf-8"), indent=2)
    return agents


def normalize(tier):
    """Make every sub-agent's stored model equal its root lead's model (sub==parent),
    preserving the tier's existing lead (parent) model choices."""
    from core.agent_hierarchy import descendants, root_of
    d = json.load(open(P, encoding="utf-8"))
    prof = d["profiles"][tier]
    ag = dict(prof.get("agents") or {})
    default = prof.get("default_model")
    dflt_fb = prof.get("default_fallback_models") or []
    changed = 0
    for parent in parents():
        root = root_of(parent)
        rcfg = ag.get(root, {})
        pm = rcfg.get("model") or default
        pfb = rcfg.get("fallback_models") or dflt_fb
        for sub in descendants(parent):
            new = {"model": pm, "fallback_models": list(pfb)}
            if ag.get(sub) != new:
                changed += 1
            ag[sub] = new
    prof["agents"] = ag
    json.dump(d, open(P, "w", encoding="utf-8"), indent=2)
    print(f"normalized {tier}: {len(ag)} agents ({changed} subs realigned)")
    return ag


if __name__ == "__main__":
    import sys as _s
    mode = _s.argv[1] if len(_s.argv) > 1 else "build"
    if mode == "normalize":
        for t in (_s.argv[2:] or ["free-trial", "actual-balanced"]):
            normalize(t)
    else:
        tier = _s.argv[2] if len(_s.argv) > 2 else "free-trial-fast"
        ag = build(tier)
        print(f"rebuilt {tier}: {len(ag)} agents")
