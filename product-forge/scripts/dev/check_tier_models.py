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

import glob
import json
import os

_REPO = str(_PF_ROOT)


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


def _live_provider_models(provider):
    """Live model ids for a provider from its /models endpoint (best-effort, cached).

    Returns (ids:set, note:str). Empty set + note on any failure (missing key,
    network, unknown provider) so the caller can SKIP silently - never fatal.
    """
    provider = str(provider or "").lower()
    endpoints = {
        "openrouter": ("https://openrouter.ai/api/v1/models", "OPENROUTER_API_KEY"),
        "openai": ("https://api.openai.com/v1/models", "OPENAI_API_KEY"),
        "deepinfra": ("https://api.deepinfra.com/v1/openai/models", "DEEPINFRA_API_KEY"),
    }
    if provider not in endpoints:
        return set(), f"no live-check for provider {provider!r} (skipped)"
    url, env = endpoints[provider]
    try:
        from core import credentials as _cred
        key = _cred.key_for(provider)
    except Exception:
        key = os.getenv(env, "")
    if not key:
        return set(), f"no key for {provider} (skipped)"
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except Exception as e:
        return set(), f"live fetch failed for {provider}: {e} (skipped)"
    rows = data.get("data") if isinstance(data, dict) else data
    ids = {m.get("id") or m.get("name") for m in (rows or []) if isinstance(m, dict)}
    return {i for i in ids if i}, f"{len(ids)} live models from {provider}"


def _profile_models(prof):
    ids = set()
    ids |= _models_in_section(prof.get("agents") or {})
    ids |= _models_in_section(prof.get("stages") or {})
    ids |= set((prof.get("models") or {}).keys())
    if prof.get("default_model"):
        ids.add(prof["default_model"])
    ids |= set(prof.get("default_fallback_models") or [])
    return ids


def live_provider_audit(tier):
    """Advisory: tier model ids must exist on the tier's LIVE provider catalog.

    Catches upstream model renames/retirements (e.g. ':free' slugs dropped) that the
    offline registry check cannot see. Skips silently with no key/network.
    """
    drift = 0
    for pname, prof in (tier.get("profiles") or {}).items():
        if not isinstance(prof, dict):
            continue
        provider = prof.get("provider") or ""
        live, note = _live_provider_models(provider)
        if not live:
            print(f"tier-live: [{pname}] {provider}: SKIP - {note}")
            continue
        missing = sorted(m for m in _profile_models(prof) if m not in live)
        if missing:
            drift += len(missing)
            shown = ", ".join(missing[:12]) + (" ..." if len(missing) > 12 else "")
            print(f"tier-live: [{pname}] {provider}: {len(missing)} model id(s) NOT on live provider: {shown}")
        else:
            print(f"tier-live: [{pname}] {provider}: ok ({note})")
    print(f"tier-live: advisory drift={drift} (never fatal)")
    return 0


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
    live_provider_audit(tier)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
