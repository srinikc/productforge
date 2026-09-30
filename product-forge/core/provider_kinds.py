"""Provider-kind abstraction + kind-aware request shaping/routing (BI-0193).

One place that answers "what KIND of provider is this, and how do I talk to it?" so the model
router and llm_client work uniformly across all kinds:

  * ``direct``      — first-party API (opencode-go/zen, gemini, openai, anthropic, ...)
  * ``aggregator``  — multi-model gateway (openrouter, replicate, fal, kie, ...)
  * ``self-host``   — locally-hosted endpoint (OpenAI-compatible server)

Kind metadata is owned by ``core/credentials.py`` (single source of truth: providers.<p>.kind).
This module owns the *behaviour* (adapters) and *selection* (ordering/validation) — not config.
No new store. Fail-closed on unknown provider/kind/feature.

Design: docs/PROVIDER-KINDS-DESIGN.md
"""

from typing import Dict, List, Optional

KINDS = ("direct", "aggregator", "self-host")

# Features a provider may or may not support; unknown => not supported (fail-closed).
FEATURES = ("chat", "tools", "json_mode", "images", "audio", "video")

# Per-provider feature support. Absent => the kind defaults below apply.
_PROVIDER_FEATURES: Dict[str, Dict[str, bool]] = {
    "openai": {"images": True, "audio": True, "tools": True, "json_mode": True},
    "gemini": {"images": True, "tools": True, "json_mode": True},
    "anthropic": {"tools": True, "json_mode": True},
    "openrouter": {"tools": True, "json_mode": True},
}

# Kind-level capability defaults (coarse), applied when a provider has no explicit entry.
_KIND_FEATURES: Dict[str, Dict[str, bool]] = {
    "direct": {"chat": True, "tools": True, "json_mode": True},
    "aggregator": {"chat": True, "tools": True, "json_mode": True},
    "self-host": {"chat": True, "tools": True, "json_mode": True},
}

# Providers whose transport needs a session header (kept from the legacy special-case).
_SESSION_HEADER_PROVIDERS = ("opencode-go", "opencode-zen", "opencode")


def kinds() -> List[str]:
    return list(KINDS)


def kind_of(provider: str) -> str:
    """The provider's kind, from the single source of truth (credentials). Unknown => ''.

    NOTE: ``credentials.provider_kind`` defaults an unknown provider to 'direct'; this registry
    treats a provider that is NOT in the credentials registry as unknown (''), fail-closed.
    """
    try:
        from core import credentials as _c
        if provider not in (_c.providers() or {}):
            return ""
        k = str(_c.provider_kind(provider) or "").strip()
    except Exception:
        k = ""
    return k if k in KINDS else ""


def resolve_endpoint(provider: str, model: str = "", fallback: str = "") -> str:
    """Per-kind endpoint resolution. Self-host/direct/aggregator all use OpenAI-compatible
    ``/chat/completions`` today; the caller's configured fallback wins when set."""
    if fallback:
        return fallback
    base = _env_endpoint(provider)
    if base:
        return base
    return ""


def _env_endpoint(provider: str) -> str:
    import os
    key = "PIPELINE_ENDPOINT_" + str(provider or "").upper().replace("-", "_")
    return os.getenv(key, "")


def headers(provider: str, api_key: str, session_id: str = "") -> Dict[str, str]:
    """Per-kind request headers (OpenAI-compatible: Bearer auth + JSON)."""
    import os as _os
    h = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    h["User-Agent"] = _os.getenv("PIPELINE_USER_AGENT", "product-forge-pipeline/1.0")
    if provider in _SESSION_HEADER_PROVIDERS:
        h["x-opencode-session"] = session_id
    return h


def adapt_body(provider: str, body: Dict) -> Dict:
    """Per-kind request-body shaping. Default (all kinds): pass through unchanged."""
    return body


def extract_content(provider: str, result: Dict) -> str:
    """Extract assistant text from an OpenAI-shaped response (shared by all kinds)."""
    try:
        msg = result["choices"][0]["message"]
        content = msg.get("content")
        if isinstance(content, list):
            content = "".join(
                str(p.get("text") or p.get("content") or "") if isinstance(p, dict) else str(p)
                for p in content
            )
        return content if isinstance(content, str) else ("" if content is None else str(content))
    except (KeyError, IndexError, TypeError):
        return ""


def supports(provider: str, feature: str) -> bool:
    """Whether a provider supports a feature. Unknown provider/feature => False (fail-closed)."""
    if feature not in FEATURES:
        return False
    k = kind_of(provider)
    if not k:
        return False
    explicit = _PROVIDER_FEATURES.get(provider)
    if explicit is not None and feature in explicit:
        return bool(explicit[feature])
    return bool(_KIND_FEATURES.get(k, {}).get(feature, False))


def order_candidates(candidates: List[Dict], prefer_kind: str = "",
                     reject_unknown: Optional[bool] = None) -> List[Dict]:
    """Stable kind-aware ordering of candidate configs.

    Each candidate is a dict possibly carrying ``provider``/``kind``. An unknown provider is
    annotated ``kind=''`` (a custom/unregistered provider with an explicit endpoint is legal).
    When ``reject_unknown`` is explicitly True, unknown-kind candidates are DROPPED (strict
    fail-closed mode); default is annotate-only, leaving blocking to ``core/model_gate``. When
    ``prefer_kind`` is set, its candidates come first while preserving relative order.
    """
    out: List[Dict] = []
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        prov = str(c.get("provider") or "")
        k = str(c.get("kind") or "") or kind_of(prov)
        if k not in KINDS:
            if reject_unknown:
                continue  # strict mode: unknown provider/kind => drop
            k = ""
        cc = dict(c)
        cc["kind"] = k
        out.append(cc)
    if prefer_kind and prefer_kind in KINDS:
        out.sort(key=lambda c: 0 if c.get("kind") == prefer_kind else 1)  # stable
    return out
