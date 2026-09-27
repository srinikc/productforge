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
# Live OpenRouter free models (verified live by scripts/dev/check_tier_models.py).
M1 = "nvidia/nemotron-3.5-lightning:free"   # fast reasoning / light planning
M2 = "qwen/qwen3.8-27b:free"                # structured specs, code, build, verify
M3 = "google/gemma-4-31b-it:free"           # content, docs, business writing
# Cross-provider fallback: OpenCode GO (paid, cheap). NOTE: OpenCode Zen FREE models
# are rejected by the API ("free tier can only be used from within OpenCode"), so we
# use the go endpoint's deepseek-v4.1-flash (verified 200 with the same key).
MZ = "deepseek-v4.1-flash"
ZEN_PROVIDER = "opencode-go"
ZEN_ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"
FREE = [M1, M2, M3]

# LEAD agents -> capability-appropriate primary model
LEAD = {
    # reasoning / planning (light, fast)
    "ideation": M1, "discovery": M1, "researcher": M1,
    "orchestrator": M1, "consensus": M1, "iterative_evaluator": M1, "guardian": M1,
    "observer": M1, "strategist": M1, "analyst": M1, "inference": M1, "product-analyzer": M1,
    "security": M1,
    # structured specs / architecture / product definition
    "design": M2, "architect": M2, "product-owner": M2,
    # code / build / ops
    "implement": M2, "implement-ui": M2, "fix": M2, "devops": M2, "code-review": M2,
    "production-deploy": M2, "agent_config": M2, "ingestion": M2,
    # verification / QA
    "validate": M2,
    # content / docs / business
    "document": M3, "finops": M3, "customer-onboarding": M3,
    "marketing": M3, "growth": M3, "customer-success": M3,
}
DEFAULT = M2


def fallbacks(m):
    # OpenCode Zen first (separate quota => survives OpenRouter 429s), then the
    # remaining OpenRouter free models.
    return [MZ] + [x for x in FREE if x != m]


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
        MZ: {"provider": ZEN_PROVIDER, "api_endpoint": ZEN_ENDPOINT},
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
