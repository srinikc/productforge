"""Credentials + budget caps registry (BI-0207).

Single owner for "where do provider API keys come from". Loads ENV VAR references
(never raw secrets) from `config/provider-keys.json`, resolves them ROOT-anchored
(PF_ROOT/.env, PF_ROOT/.env.local) so it works from any CWD, and exposes:

    key_for(provider)        -> str        ("" if missing)
    has(provider)            -> bool
    provider_kind(provider)  -> direct|aggregator|self-host
    required_for(provider)   -> [llm|image|video|...]
    missing_for(kinds)       -> [(provider, env)]
    check_budget(provider, spent_usd, run_spent_usd) -> (ok, reason)

Wired into core/orchestrator/llm_client.py (and, later, the media adapters).
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

from core.paths import ROOT

_CONFIG = ROOT / "config" / "provider-keys.json"
_DEFAULT_LLM_ENV = "OPENCODE_ZEN_API_KEY"

_env_loaded = False
_cache: Optional[Dict] = None


def _config() -> Dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(_CONFIG, encoding="utf-8-sig") as f:
            _cache = json.load(f)
    except Exception:
        _cache = {}
    return _cache


def _load_env_files() -> None:
    """Load PF_ROOT/.env then PF_ROOT/.env.local WITHOUT overriding existing env.

    ROOT-anchored (not CWD), best-effort, values never logged.
    """
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    for name in (".env", ".env.local"):
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            continue


def providers() -> Dict:
    return dict(_config().get("providers") or {})


def _entry(provider: str) -> Dict:
    return dict(providers().get(provider) or {})


def env_var(provider: str) -> str:
    _load_env_files()
    return str(_entry(provider).get("env") or _DEFAULT_LLM_ENV)


def key_for(provider: str) -> str:
    """Resolve a provider's API key: process env first, then PF_ROOT/.env(.local)."""
    _load_env_files()
    return os.getenv(env_var(provider), "")


def has(provider: str) -> bool:
    return bool(key_for(provider))


def provider_kind(provider: str) -> str:
    return str(_entry(provider).get("kind") or "direct")


def required_for(provider: str) -> List[str]:
    return list(_entry(provider).get("required_for") or [])


def missing_for(kinds: List[str]) -> List[Tuple[str, str]]:
    """[(provider, env_var)] that are required for any of `kinds` but have no key."""
    want = {str(k) for k in (kinds or [])}
    out: List[Tuple[str, str]] = []
    for name in providers():
        req = set(required_for(name))
        if want and (want & req) and not has(name):
            out.append((name, env_var(name)))
    return out


# ── budget caps ──────────────────────────────────────────────────────────────
def budget() -> Dict:
    return dict(_config().get("budget") or {})


def check_budget(provider: str = "", spent_usd: float = 0.0,
                 run_spent_usd: float = 0.0) -> Tuple[bool, str]:
    """Enforce per-provider + per-run caps. 0 (or missing) = uncapped.

    Returns (ok, reason). `reason` is "" when ok.
    """
    b = budget()
    def _cap(key: str) -> float:
        try:
            return float(b.get(key) or 0)
        except Exception:
            return 0.0
    run_cap = _cap("per_run_cap_usd")
    if run_cap and run_spent_usd > run_cap:
        return False, f"per-run budget cap exceeded: ${run_spent_usd:.2f} > ${run_cap:.2f}"
    prov_cap = _cap("per_provider_cap_usd")
    if prov_cap and spent_usd > prov_cap:
        return False, f"per-provider cap exceeded for {provider or '?'}: ${spent_usd:.2f} > ${prov_cap:.2f}"
    return True, ""


def status() -> Dict:
    """Redacted readiness report (which providers are keyed)."""
    _load_env_files()
    return {
        "root": str(ROOT),
        "providers": {
            name: {"env": env_var(name), "kind": provider_kind(name),
                   "required_for": required_for(name), "key_set": has(name)}
            for name in providers()
        },
        "budget": budget(),
    }


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Provider credential + budget registry (BI-0207)")
    ap.add_argument("--status", action="store_true", help="redacted readiness report")
    ap.add_argument("--missing", default="", help="comma list of kinds, e.g. llm,image,tts")
    a = ap.parse_args(argv)
    if a.missing:
        kinds = [k.strip() for k in a.missing.split(",") if k.strip()]
        miss = missing_for(kinds)
        print(json.dumps({"missing": [{"provider": p, "env": e} for p, e in miss]}, indent=2))
        return 0
    print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
