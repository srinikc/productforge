"""Model Catalog — real, per-model capability metadata fetched from providers.

Enriches the model list with the fields that decide AGENT fit: context, max output,
input/output **modality**, and **supported_parameters** (function/tool calling,
reasoning, structured_outputs/response_format, seed…) + pricing.

Sources: OpenRouter `/api/v1/models` (public), OpenCode Zen `/v1/models`.
Output: `config/model-catalog.json` (this module is the single writer). Additive —
it never changes tier/agent assignments; it only supplies data for fit-checks and
recommendations. Offline-safe: on fetch failure the existing catalog is kept.

CLI: `python -m core.model_catalog --refresh`
"""
import json
import os
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "config", "model-catalog.json")
REGISTRY = os.path.join(REPO, "products", ".pipeline", "model_registry.json")
OR_URL = "https://openrouter.ai/api/v1/models"
ZEN_URL = "https://opencode.ai/zen/v1/models"

_TOOL_PARAMS = {"tools", "tool_choice"}


def _get(url: str, key_env: str = "") -> Dict:
    headers = {"User-Agent": "product-forge-model-catalog/1.0"}
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(REPO, ".env"))
    except Exception:
        pass
    if key_env and os.getenv(key_env):
        headers["Authorization"] = "Bearer " + os.environ[key_env]
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[ModelCatalog] fetch failed {url}: {e}")
        return {}


def _load_registry_names() -> List[str]:
    try:
        return [m.get("name") for m in
                (json.load(open(REGISTRY, encoding="utf-8")).get("models", [])) if m.get("name")]
    except Exception:
        return []


def _enrich_one(or_model: Dict) -> Dict:
    params = set(or_model.get("supported_parameters") or [])
    arch = or_model.get("architecture") or {}
    top = or_model.get("top_provider") or {}
    pricing = or_model.get("pricing") or {}
    return {
        "id": or_model.get("id", ""),
        "name": or_model.get("name") or or_model.get("id", ""),
        "provider": str(or_model.get("id", "")).split("/")[0],
        "context_window": or_model.get("context_length"),
        "max_output": top.get("max_completion_tokens"),
        "input_modalities": arch.get("input_modalities") or ["text"],
        "output_modalities": arch.get("output_modalities") or ["text"],
        "supported_parameters": sorted(params),
        "tools": bool(params & _TOOL_PARAMS),
        "reasoning": ("reasoning" in params) or bool(or_model.get("reasoning")),
        "structured_outputs": ("structured_outputs" in params) or ("response_format" in params),
        "json_mode": "response_format" in params,
        "seed": "seed" in params,
        "pricing": {"prompt": pricing.get("prompt"), "completion": pricing.get("completion")},
        "source": "openrouter",
    }


def _match(or_by_id: Dict, name: str) -> Optional[Dict]:
    if name in or_by_id:
        return or_by_id[name]
    tail = name.split("/")[-1]
    for mid, m in or_by_id.items():
        if mid.split("/")[-1] == tail or mid.endswith(name) or name.endswith(mid.split("/")[-1]):
            return m
    return None


def refresh() -> Dict:
    """Fetch provider metadata and (re)write config/model-catalog.json. Offline-safe."""
    or_data = _get(OR_URL)
    or_models = or_data.get("data", []) if isinstance(or_data, dict) else []
    by_id = {m.get("id"): m for m in or_models if m.get("id")}
    zen = _get(ZEN_URL, "OPENCODE_ZEN_API_KEY")
    zen_ids = [m.get("id") for m in (zen.get("data", []) if isinstance(zen, dict) else [])]

    models: Dict[str, Dict] = {}
    # our registry names -> try to enrich from OpenRouter
    for name in _load_registry_names():
        m = _match(by_id, name)
        if m:
            entry = _enrich_one(m)
            entry["registry_name"] = name
            models[name] = entry
        else:
            models[name] = {"registry_name": name, "source": "registry-only",
                            "context_window": None, "tools": None, "reasoning": None}
    # keep any existing catalog entries we couldn't re-fetch this run
    try:
        prev = json.load(open(OUT, encoding="utf-8")).get("models", {})
        for k, v in prev.items():
            models.setdefault(k, v)
    except Exception:
        pass

    catalog = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {"openrouter_count": len(or_models), "zen_count": len(zen_ids)},
        "legend": {"tools": "function/tool calling", "reasoning": "reasoning/thinking",
                   "structured_outputs": "JSON schema / response_format"},
        "models": models,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"[ModelCatalog] wrote {OUT} ({len(models)} models; "
          f"openrouter={len(or_models)}, zen={len(zen_ids)})")
    return catalog


def load() -> Dict:
    try:
        return json.load(open(OUT, encoding="utf-8")).get("models", {})
    except Exception:
        return {}


def capabilities(model_name: str) -> Dict:
    """The capability fields for a model (from the catalog; {} if unknown)."""
    c = load().get(model_name) or {}
    return c


def fit(model_name: str, needs: Dict) -> Dict:
    """Judge whether a model fits an agent's needs, WITH reasons."""
    c = capabilities(model_name)
    if not c:
        return {"ok": None, "reasons": [f"no catalog data for '{model_name}'"]}
    reasons, ok = [], True

    def need(key, want):
        nonlocal ok
        if not want:
            return
        have = c.get(key)
        if have is None:
            reasons.append(f"? {key} unknown for this model")
            return
        if bool(have) != bool(want):
            ok = False
            reasons.append(f"BAD {key}: model={have}, agent needs {want}")
        else:
            reasons.append(f"ok {key}")

    for k in ("tools", "reasoning", "structured_outputs"):
        if needs.get(k):
            need(k, True)
    mo = needs.get("min_output")
    if mo:
        if (c.get("max_output") or 0) and c["max_output"] < mo:
            ok = False
            reasons.append(f"BAD max_output {c['max_output']} < required {mo}")
        elif not c.get("max_output"):
            reasons.append("? max_output unknown")
        else:
            reasons.append(f"ok max_output {c['max_output']} >= {mo}")
    mc = needs.get("min_context")
    if mc:
        if (c.get("context_window") or 0) and c["context_window"] < mc:
            ok = False
            reasons.append(f"BAD context {c['context_window']} < required {mc}")
        elif not c.get("context_window"):
            reasons.append("? context unknown")
        else:
            reasons.append(f"ok context {c['context_window']} >= {mc}")
    return {"ok": ok, "model": model_name, "reasons": reasons,
            "capabilities": {k: c.get(k) for k in ("context_window", "max_output", "tools",
                                                   "reasoning", "structured_outputs",
                                                   "input_modalities", "provider")}}


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Model catalog (provider metadata)")
    ap.add_argument("--refresh", action="store_true", help="fetch + rewrite config/model-catalog.json")
    ap.add_argument("--model", default="", help="show capabilities for a model")
    ap.add_argument("--fit", default="", help="judge fit for a model (JSON)",)
    a = ap.parse_args(argv)
    if a.refresh:
        refresh()
        return 0
    if a.model:
        print(json.dumps(capabilities(a.model), indent=2, ensure_ascii=False))
        return 0
    print(json.dumps({"models": len(load())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
