"""Generic plugin / registry framework (ports & adapters) — BI-0200.

Extensions register as a config ENTRY + a small ADAPTER (resolved by dotted name), with NO core edit.
The core depends only on ports; each plugin kind maps to an EXISTING port (never a fork):

  provider  -> core.provider_kinds shape (headers/adapt_body/extract_content/supports)
  tool      -> core.tool_registry.ToolRegistry.register(ToolSpec)
  stage     -> pack-shaped dict consumed by core.pipeline_composition.effective_definition
  validator -> pack-shaped validators consumed by composition
  agent     -> AgentSpec dict materialized via core.agent_spec

Owns (single writer): ``config/plugins-registry.json``.
Reuses: the ``module:callable`` resolver convention of core.pipeline_capabilities (_mk/_fn).

Fail-closed: unknown kind / unresolved adapter / missing `requires` => warning, never enabled; run()
never raises into the pipeline. See docs/PLUGINS-DESIGN.md.
"""

import json
import os
from typing import Dict, List, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

STORE = os.path.join(str(_ROOT), "config", "plugins-registry." + "json")
KINDS = ("provider", "tool", "stage", "validator", "agent")


def _load() -> Dict:
    try:
        with open(STORE, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(data: Dict) -> None:
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STORE)


def catalog() -> Dict:
    return _load().get("plugins") or {}


def list_plugins(kind: str = "", enabled_only: bool = True) -> List[Dict]:
    out = []
    for pid, p in catalog().items():
        if kind and p.get("kind") != kind:
            continue
        if enabled_only and not p.get("enabled", True):
            continue
        out.append({"id": pid, **p})
    return sorted(out, key=lambda p: p.get("id", ""))


def view(pid: str) -> Optional[Dict]:
    p = catalog().get(pid)
    return {"id": pid, **p} if p else None


def enabled(kind: str = "") -> List[Dict]:
    return list_plugins(kind=kind, enabled_only=True)


def kinds() -> List[str]:
    return list(KINDS)


# ── resolver (reuse the pipeline_capabilities convention) ───────────────────
def _resolve_dotted(dotted: str):
    """Resolve 'module.path:callable' -> callable. Returns None on failure (never raises)."""
    try:
        from core import pipeline_capabilities as _pc
        if hasattr(_pc, "_fn"):
            # _fn calls it; but we want the raw callable -> mirror the logic
            import importlib
            mod_name, _, fn_name = str(dotted).partition(":")
            mod = importlib.import_module(mod_name)
            return getattr(mod, fn_name, None)
    except Exception:
        pass
    try:
        import importlib
        mod_name, _, fn_name = str(dotted).partition(":")
        mod = importlib.import_module(mod_name)
        return getattr(mod, fn_name, None)
    except Exception:
        return None


def resolve(pid: str) -> Dict:
    """Load a plugin's adapter and return its port. Fail-closed: never raises."""
    p = view(pid)
    if not p:
        return {"ok": False, "error": "unknown_plugin", "plugin": pid}
    kind = str(p.get("kind") or "")
    if kind not in KINDS:
        return {"ok": False, "error": f"unknown_kind:{kind}"}
    # dependency check (fail-closed)
    missing = [r for r in (p.get("requires") or []) if r not in catalog()]
    if missing:
        return {"ok": False, "error": f"missing_requires:{missing}"}
    builder = _resolve_dotted(str(p.get("adapter") or ""))
    if builder is None:
        return {"ok": False, "error": f"unresolved_adapter:{p.get('adapter')}"}
    context = {"plugin_id": pid, "kind": kind, "config": p.get("config") or {}, "root": str(_ROOT)}
    try:
        port = builder(context)
    except Exception as e:
        return {"ok": False, "error": f"adapter_failed:{e}"}
    return {"ok": True, "kind": kind, "port": port, "plugin": pid}


def run(pid: str, *args, **kwargs) -> Dict:
    """Resolve and (for stage/validator) return the pack contribution; never raises."""
    return resolve(pid)


def stage_contributions() -> List[Dict]:
    """Enabled stage/validator plugins as pack-shaped dicts for pipeline_composition (no new path)."""
    out: List[Dict] = []
    for p in enabled():
        if p.get("kind") not in ("stage", "validator"):
            continue
        r = resolve(p["id"])
        if r.get("ok") and isinstance(r.get("port"), dict):
            contrib = dict(r["port"])
            contrib.setdefault("key", p["id"])
            out.append(contrib)
    return out


def register(pid: str, kind: str, adapter: str, *, enabled: bool = True,
             provides: Optional[Dict] = None, requires: Optional[List[str]] = None,
             config: Optional[Dict] = None, title: str = "") -> Dict:
    if kind not in KINDS:
        return {"ok": False, "error": f"unknown_kind:{kind}"}
    if not pid or not adapter:
        return {"ok": False, "error": "id_and_adapter_required"}
    data = _load()
    plugins = data.get("plugins") or {}
    plugins[pid] = {"kind": kind, "title": title or pid, "adapter": adapter,
                    "enabled": bool(enabled), "provides": provides or {},
                    "requires": requires or [], "config": config or {}}
    data["plugins"] = plugins
    _save(data)
    return {"ok": True, "plugin": view(pid)}


def set_enabled(pid: str, enabled_: bool) -> Dict:
    data = _load()
    plugins = data.get("plugins") or {}
    if pid not in plugins:
        return {"ok": False, "error": "unknown_plugin"}
    plugins[pid]["enabled"] = bool(enabled_)
    data["plugins"] = plugins
    _save(data)
    return {"ok": True, "plugin": view(pid)}


def validate() -> Dict:
    """Resolve every enabled plugin; report ok/warnings. Fail-closed, never raises."""
    ok, warnings = 0, []
    for p in enabled():
        r = resolve(p["id"])
        if r.get("ok"):
            ok += 1
        else:
            warnings.append(f"{p['id']}: {r.get('error')}")
    return {"total": len(list_plugins(enabled_only=False)), "enabled": len(enabled()),
            "resolved": ok, "warnings": warnings}


def describe() -> Dict:
    return {"kinds": kinds(),
            "ports": {"provider": "provider_kinds shape", "tool": "{spec,handler}",
                      "stage": "pack-shaped (pipeline_composition)", "validator": "pack-shaped",
                      "agent": "AgentSpec dict"},
            "count": len(list_plugins(enabled_only=False))}
