"""
Model Router (extracted from pipeline_executor - 1A.11).

Resolves the model/provider/endpoint for an agent+stage from the shared tier
config (project override -> repo config -> products -> repo root).
No model names are hardcoded in pipeline logic; only env-overridable fallbacks.
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
from typing import Dict, List, Optional

FALLBACK_MODEL = os.getenv("PIPELINE_FALLBACK_MODEL", "mimo-v2.5")
FALLBACK_PROVIDER = os.getenv("PIPELINE_FALLBACK_PROVIDER", "opencode-go")
FALLBACK_ENDPOINT = os.getenv(
    "PIPELINE_FALLBACK_ENDPOINT",
    "https://opencode.ai/zen/go/v1/chat/completions",
)

_REPO_ROOT = str(_PF_ROOT)


def tier_config_candidates(products_dir: str = "products", project_dir: str = "") -> List[str]:
    # config/ is authoritative (BI-0025); per-project override wins.
    return [
        os.path.join(project_dir, "model-tier.json") if project_dir else "",
        os.path.join(_REPO_ROOT, "config", "model-tier.json"),
        os.path.join(products_dir, "model-tier.json"),
        os.path.join(_REPO_ROOT, "model-tier.json"),
    ]


def load_tier_config_file(products_dir: str = "products", project_dir: str = "") -> Dict:
    for path in tier_config_candidates(products_dir, project_dir):
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception:
                continue
    return {}


def describe_tiers(products_dir: str = "products", project_dir: str = "") -> Dict:
    """List all tier profiles + their details (for CLI/API tier selection)."""
    cfg = load_tier_config_file(products_dir, project_dir)
    profiles = cfg.get("profiles") or {}
    out = {}
    for name, prof in profiles.items():
        agents = prof.get("agents") or {}
        # "actual" profile is empty by design (base config holds it) - reflect base.
        agents_count = len(agents) or len(cfg.get("agents") or {})
        models_count = len(prof.get("models") or {}) or len(cfg.get("agents") or {})
        out[name] = {
            "description": prof.get("description", ""),
            "default_model": prof.get("default_model") or cfg.get("default_tier", ""),
            "provider": prof.get("provider", "opencode-go"),
            "api_endpoint": prof.get("api_endpoint", cfg.get("api_endpoint", "")),
            "agents_mapped": agents_count,
            "models": models_count,
            "sample": dict(list(agents.items())[:3]),
        }
    return {"active_tier": cfg.get("active_tier", "actual"),
            "configured_profiles": list(profiles.keys()) or ["actual"],
            "profiles": out}


class ModelRouter:
    def __init__(self, model_registry, products_dir: str = "products",
                 project_dir: str = "", pipeline_def: Optional[Dict] = None):
        self.model_registry = model_registry
        self.products_dir = products_dir
        self.project_dir = project_dir
        self.pipeline_def = pipeline_def or {}
        self.tier_profile: Optional[str] = None
        self._tier_config_cache = None
        self._cheap_model_cache = None
        self._active_tier_logged = False

    def tier_config_candidates(self) -> List[str]:
        # config/ is authoritative (BI-0025): per-project override > repo config.
        repo_root = str(_PF_ROOT)
        return [
            os.path.join(self.project_dir, "model-tier.json"),
            os.path.join(repo_root, "config", "model-tier.json"),
            os.path.join(self.products_dir, "model-tier.json"),
            os.path.join(repo_root, "model-tier.json"),
        ]

    def load_tier_config(self) -> Dict:
        if self._tier_config_cache is not None:
            return self._tier_config_cache
        config: Dict = {}
        for path in self.tier_config_candidates():
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8-sig") as f:
                        config = json.load(f)
                    print(f"[ModelRouter] Loaded tier config from {path}")
                    break
                except Exception as e:
                    print(f"[ModelRouter] Warning: could not read tier config {path}: {e}")
        self._tier_config_cache = config
        return config

    def active_profile_name(self) -> Optional[str]:
        """Resolve the active tier profile: explicit -> env -> pipeline -> config."""
        name = (self.tier_profile or os.getenv("PIPELINE_MODEL_TIER")
                or (self.pipeline_def or {}).get("model_tier")
                or (self.load_tier_config() or {}).get("active_tier"))
        return name

    def active_profile(self) -> Optional[Dict]:
        """Return the active profile dict, or None to use the base config.

        Profiles named "actual"/"base"/"default" (or unknown) mean no override.
        """
        name = self.active_profile_name()
        if not name or name in ("actual", "base", "default", "none", "real"):
            return None
        profile = (self.load_tier_config().get("profiles") or {}).get(name)
        if profile is None:
            print(f"[ModelRouter] Warning: unknown tier profile '{name}'; using base config")
        return profile

    def get_model_tier(self, agent_id: str, stage_id: str) -> Optional[str]:
        config = self.load_tier_config()
        profile = self.active_profile() or config
        if profile is config:
            if config:
                if stage_id in config.get("stages", {}):
                    tier = config["stages"][stage_id].get("tier")
                    if tier:
                        return tier
                if agent_id in config.get("agents", {}):
                    tier = config["agents"][agent_id].get("tier")
                    if tier:
                        return tier
                if config.get("default_tier"):
                    return config["default_tier"]
            if self.pipeline_def:
                pipeline_config = self.pipeline_def.get("model_config", {})
                if agent_id in pipeline_config.get("agents", {}):
                    return pipeline_config["agents"][agent_id].get("tier")
                return pipeline_config.get("default_tier")
            return "recommended"
        return profile.get("default_tier", "free-trial")

    def parent_stage_id(self, stage_id: str) -> Optional[str]:
        if stage_id and "-" in stage_id:
            return stage_id.rsplit("-", 1)[0]
        return None

    def cheapest_opencode_go_model(self):
        if self._cheap_model_cache is not None:
            return self._cheap_model_cache
        try:
            models = [m for m in self.model_registry.list_models()
                      if getattr(m, "enabled", True) and getattr(m, "provider", "") == "opencode-go"]
            if models:
                cheap = min(models, key=lambda m: (m.cost_per_1k_input or 0) + (m.cost_per_1k_output or 0))
                self._cheap_model_cache = cheap
                return cheap
        except Exception:
            pass
        self._cheap_model_cache = None
        return None

    def _resolve_endpoint(self, model_id: str, source: Optional[Dict], config: Dict):
        """Provider + endpoint for a specific model (per-profile models map first)."""
        entry = ((source or {}).get("models") or {}).get(model_id)
        if entry:
            return (entry.get("provider") or FALLBACK_PROVIDER,
                    entry.get("api_endpoint") or FALLBACK_ENDPOINT)
        provider = (source or {}).get("provider") or config.get("provider") or FALLBACK_PROVIDER
        endpoint = ((source or {}).get("api_endpoint")
                    or config.get("api_endpoint", FALLBACK_ENDPOINT))
        return provider, endpoint

    def _build_candidates(self, model_ids: List[str], source: Optional[Dict], config: Dict) -> List[Dict]:
        """Ordered [{model, provider, api_endpoint}] candidates (deduped)."""
        seen, out = set(), []
        for mid in model_ids:
            if not mid or mid in seen:
                continue
            seen.add(mid)
            provider, endpoint = self._resolve_endpoint(mid, source, config)
            out.append({"model": mid, "provider": provider, "api_endpoint": endpoint})
        return out

    def get_agent_model_config(self, agent_id: str, stage_id: str, force_cheap: bool = False,
                               _depth: int = 0) -> dict:
        config = self.load_tier_config()
        profile = self.active_profile()
        source = profile if profile is not None else config

        if profile is not None and not self._active_tier_logged:
            self._active_tier_logged = True
            print(f"[ModelRouter] Active tier profile: '{self.active_profile_name()}' "
                  f"(default_model={profile.get('default_model')})")

        if force_cheap:
            cheap = self.cheapest_opencode_go_model()
            if cheap:
                return {
                    "model": cheap.name,
                    "provider": cheap.provider,
                    "api_endpoint": source.get("api_endpoint", config.get("api_endpoint", FALLBACK_ENDPOINT)),
                    "fallback_models": [],
                    "tier": source.get("default_tier", config.get("default_tier", "opencode-go-cheap")),
                }

        if source:
            # Per-agent runtime OVERRIDE wins (BI-0178): override > stage > agent > default.
            try:
                from core import agent_model_override as _amo
                _ov = _amo.get(self.project_dir, agent_id)
            except Exception:
                _ov = None
            if _ov and _ov.get("model"):
                _m = _ov["model"]
                _ag = (source.get("agents") or {}).get(agent_id, {})
                _fb = _ag.get("fallback_models") or source.get("default_fallback_models", []) or []
                _cands = self._build_candidates([_m] + list(_fb), source, config)
                _pk = _cands[0]
                return {
                    "model": _pk["model"],
                    "provider": _pk["provider"],
                    "api_endpoint": _pk["api_endpoint"],
                    "fallback_models": _fb,
                    "candidates": _cands,
                    "source": "override",
                    "overridden": True,
                    "tier": source.get("default_tier", config.get("default_tier", "opencode-go-cheap")),
                }
            try:
                default_model = source.get("default_model") or FALLBACK_MODEL
                agent_cfg = (source.get("agents") or {}).get(agent_id, {})
                # Sub-agents ALWAYS inherit their parent's FULLY-RESOLVED model
                # (all tiers): parent may itself be a sub, or resolve via stage/default.
                try:
                    from core.agent_hierarchy import parent_of
                    _p = parent_of(agent_id)
                    if _p and _p != agent_id and _depth < 6:
                        _pc = self.get_agent_model_config(_p, stage_id, force_cheap, _depth + 1)
                        if _pc and _pc.get("model"):
                            return {**_pc, "inherited_from": _p}
                except Exception:
                    pass
                stage_cfg = (source.get("stages") or {}).get(stage_id, {})

                parent_cfg = {}
                if not stage_cfg.get("model"):
                    parent_id = self.parent_stage_id(stage_id)
                    if parent_id:
                        parent_cfg = (source.get("stages") or {}).get(parent_id, {})

                model = (stage_cfg.get("model") or parent_cfg.get("model")
                         or agent_cfg.get("model") or default_model)
                fallbacks = agent_cfg.get("fallback_models") or source.get("default_fallback_models", []) or []
                candidates = self._build_candidates([model] + fallbacks, source, config)
                primary = candidates[0]

                return {
                    "model": primary["model"],
                    "provider": primary["provider"],
                    "api_endpoint": primary["api_endpoint"],
                    "fallback_models": fallbacks,
                    "candidates": candidates,
                    "tier": source.get("default_tier", config.get("default_tier", "opencode-go-cheap")),
                }
            except Exception as e:
                print(f"[WARNING] Error resolving tier config: {e}")

        return {
            "model": FALLBACK_MODEL,
            "provider": FALLBACK_PROVIDER,
            "api_endpoint": FALLBACK_ENDPOINT,
        }
