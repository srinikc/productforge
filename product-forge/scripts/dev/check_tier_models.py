"""Advisory drift check: config/model-tier.json vs the model registry + known agents/stages.

Read-only. Prints drifts and ALWAYS exits 0 (advisory) so it can run inside wired_audit.

Checks:
  1. every model id (profile `default_model`, `default_fallback_models`, `models` map keys,
     and each `agents`/`stages` entry's `model` + `fallback_models`; plus the top-level base
     agents/stages = the "actual" profile) exists in products/.pipeline/model_registry.json.
  2. every key in an `agents` map is a known agent id (agents/*.agent.json).
  3. every key in a `stages` map is a known stage id (pipeline-definition.json stages).

Run: python scripts/dev/check_tier_models.py
"""
import glob
import json
import os

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(path):
    with open(os.path.join(_REPO, path), encoding="utf-8") as f:
        return json.load(f)


def _known_agents():
    out = set()
    for p in glob.glob(os.path.join(_REPO, "agents", "*.agent.json")):
        out.add(os.path.basename(p)[:-len(".agent.json")])
    return out


def _known_stages():
    try:
        st = _load("pipeline-definition.json").get("stages", {})
        return set(st.keys()) if isinstance(st, dict) else set()
    except Exception:
        return set()


def _registry_models():
    data = _load(os.path.join("products", ".pipeline", "model_registry.json"))
    return {m.get("name") for m in data.get("models", []) if m.get("name")}


def _models_in_section(section):
    ids = set()
    if isinstance(section, dict):
        for cfg in section.values():
            if not isinstance(cfg, dict):
                continue
            if cfg.get("model"):
                ids.add(cfg["model"])
            for m in cfg.get("fallback_models") or []:
                ids.add(m)
    return ids


def _check(name, prof, reg, agents, stages, unknown):
    models = set()
    models |= _models_in_section(prof.get("agents") or {})
    models |= _models_in_section(prof.get("stages") or {})
    for mid in (prof.get("models") or {}):
        models.add(mid)
    if prof.get("default_model"):
        models.add(prof["default_model"])
    for m in prof.get("default_fallback_models") or []:
        models.add(m)
    for mid in sorted(m for m in models if m not in reg):
        unknown["models"].setdefault(name, set()).add(mid)
    for k in (prof.get("agents") or {}):
        if k not in agents:
            unknown["agents"].setdefault(name, set()).add(k)
    for k in (prof.get("stages") or {}):
        if k not in stages:
            unknown["stages"].setdefault(name, set()).add(k)


def main():
    tier = _load(os.path.join("config", "model-tier.json"))
    reg = _registry_models()
    agents = _known_agents()
    stages = _known_stages()

    unknown = {"models": {}, "agents": {}, "stages": {}}
    _check("actual", {"agents": tier.get("agents") or {},
                      "stages": tier.get("stages") or {}}, reg, agents, stages, unknown)
    for pname, prof in (tier.get("profiles") or {}).items():
        if isinstance(prof, dict):
            _check(pname, prof, reg, agents, stages, unknown)

    labels = {"models": "model ids not in registry",
              "agents": "agent keys not known (agents/*.agent.json)",
              "stages": "stage keys not known (pipeline-definition.json)"}
    total = 0
    for kind in ("models", "agents", "stages"):
        mapping = unknown[kind]
        n = sum(len(v) for v in mapping.values())
        total += n
        if not n:
            print(f"tier-models: {labels[kind]}: 0 drift")
            continue
        print(f"tier-models: {labels[kind]}: {n} drift(s)")
        for prof in sorted(mapping):
            vals = sorted(mapping[prof])
            shown = ", ".join(vals[:12]) + (" ..." if len(vals) > 12 else "")
            print(f"   [{prof}] {len(vals)}: {shown}")
    print(f"tier-models: advisory total={total} (never fatal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
