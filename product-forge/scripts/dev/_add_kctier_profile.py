"""One-shot helper: add the `kctier` profile to both model-tier.json files.

Never removes existing keys; only creates/overwrites `profiles.kctier`.
Run: python scripts/dev/_add_kctier_profile.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TARGETS = [
    os.path.join(ROOT, "config", "model-tier.json"),
    os.path.join(ROOT, "products", "ProductForge-Dashboard", "model-tier.json"),
]

ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"

HEAVY = {
    "design", "architect", "product-design-spec", "design_critic", "ux-ia",
    "review", "security", "security-audit", "a11y-audit", "validate",
    "code-review", "quality_gate", "static_verifier", "performance",
}
CODE = {
    "implement", "implement-api", "implement-db", "implement-logic",
    "implement-ui", "fix", "devops", "package",
}


def mapping_for(agent_id):
    if agent_id in HEAVY:
        return {"model": "deepseek-v4.1-flash",
                "fallback_models": ["deepseek-v4-flash", "mimo-v2.5"]}
    if agent_id in CODE:
        return {"model": "deepseek-v4-flash",
                "fallback_models": ["deepseek-v4.1-flash", "mimo-v2.5"]}
    return {"model": "mimo-v2.5",
            "fallback_models": ["deepseek-v4-flash"]}


def collect_agents(cfg):
    names = []
    for a in (cfg.get("agents") or {}).keys():
        if a not in names:
            names.append(a)
    ft = (cfg.get("profiles") or {}).get("free-trial") or {}
    for a in (ft.get("agents") or {}).keys():
        if a not in names:
            names.append(a)
    return names


def build_profile(cfg):
    agents = {}
    for name in collect_agents(cfg):
        agents[name] = mapping_for(name)
    return {
        "description": "Custom tier: opencode-go (mimo-v2.5, deepseek-v4-flash, deepseek-v4.1-flash).",
        "provider": "opencode-go",
        "default_tier": "kctier",
        "api_endpoint": ENDPOINT,
        "default_model": "deepseek-v4.1-flash",
        "default_fallback_models": ["deepseek-v4-flash", "mimo-v2.5"],
        "models": {
            "mimo-v2.5": {"provider": "opencode-go", "api_endpoint": ENDPOINT},
            "deepseek-v4-flash": {"provider": "opencode-go", "api_endpoint": ENDPOINT},
            "deepseek-v4.1-flash": {"provider": "opencode-go", "api_endpoint": ENDPOINT},
        },
        "agents": agents,
        "stages": {
            "1": {"model": "deepseek-v4.1-flash"},
            "2": {"model": "deepseek-v4.1-flash"},
        },
    }


def main():
    for path in TARGETS:
        with open(path, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
        profiles = cfg.setdefault("profiles", {})
        profiles["kctier"] = build_profile(cfg)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("updated:", path, "agents:", len(profiles["kctier"]["agents"]))


if __name__ == "__main__":
    main()
