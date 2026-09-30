"""Capability-pack registry + discovery->enablement (BI-0189).

The pluggable-core foundation for multimodal/media: a catalog of **capability packs** (keyed by
modality) and a per-project **capability profile** derived from discovery.

Ownership (single writer for the two new stores):
  * ``config/capability-packs.json``        - the pack catalog (this module)
  * ``products/<project>/capabilities.json`` - the project's required/enabled capabilities (this module)

Reuse (do NOT duplicate truth):
  * agent->knowledge/skills/MCP bindings  -> ``config/agent-capabilities.json`` (core.skills_registry)
  * which optional stages run             -> run_plan / plan_evaluator / pipeline_tailoring
  * discover->recommend->HIL->enable      -> core.integration_advisor + core.feature_flags
  * modality detection                    -> core.modality (we only persist its result)
  * model capability/fit                  -> core.model_catalog / core.model_gate

Fail-closed: an unknown required capability or an unknown enabled pack is reported as a warning and
never silently enabled. See docs/CAPABILITY-PACKS-DESIGN.md.
"""

from datetime import datetime
from typing import Dict, List, Optional
import json
import os

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # executed as a script: seed the repo root, then retry
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

CATALOG = os.path.join(str(_ROOT), "config", "capability-packs.json")
PROFILE_NAME = "capabilities." + "json"


def _load(path: str) -> Dict:
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _atomic_write(path: str, data: Dict) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


# ── catalog (config/capability-packs.json) ──────────────────────────────────
def catalog() -> Dict:
    return _load(CATALOG).get("packs") or {}


def defaults() -> List[str]:
    return list(_load(CATALOG).get("defaults") or [])


def list_packs(modality: str = "") -> List[Dict]:
    out = []
    for key, p in catalog().items():
        if modality and p.get("modality") != modality:
            continue
        out.append({"key": key, **p})
    return sorted(out, key=lambda x: x.get("key", ""))


def view(key: str) -> Optional[Dict]:
    p = catalog().get(key)
    return {"key": key, **p} if p else None


def pack_for_modality(modality: str) -> Optional[Dict]:
    for key, p in catalog().items():
        if p.get("modality") == modality:
            return {"key": key, **p}
    return None


def resolve(required: List[str]) -> Dict:
    """Map a list of required capabilities (modalities/pack keys) to packs. Fail-closed:
    unknown capabilities become warnings and are never enabled."""
    enabled: List[Dict] = []
    warnings: List[str] = []
    for cap in (required or []):
        cap = str(cap).strip().lower()
        if not cap:
            continue
        p = catalog().get(cap)
        if p:
            p = {"key": cap, **p}
        else:
            p = pack_for_modality(cap)
        if not p:
            warnings.append(f"unknown capability/pack: {cap}")
            continue
        # dependency check (fail-closed)
        missing = [r for r in (p.get("requires") or []) if r not in catalog()]
        if missing:
            warnings.append(f"pack '{p['key']}' requires missing pack(s): {missing}")
            continue
        if p["key"] not in [e["key"] for e in enabled]:
            enabled.append(p)
    return {"enabled": enabled, "warnings": warnings}


# ── project profile (products/<project>/capabilities.json) ──────────────────
def profile_path(project_dir: str) -> str:
    return os.path.join(project_dir, PROFILE_NAME)


def load_profile(project_dir: str) -> Dict:
    return _load(profile_path(project_dir))


def save_profile(project_dir: str, required: Optional[List[str]] = None,
                 enabled_packs: Optional[List[str]] = None, source: str = "discovery") -> Dict:
    """Write the project's capability profile (single writer of this store)."""
    prev = load_profile(project_dir)
    req = list(required if required is not None else (prev.get("required_capabilities") or []))
    res = resolve(req) if enabled_packs is None else {"enabled": [], "warnings": []}
    enabled = ([e["key"] for e in res["enabled"]] if enabled_packs is None
               else list(enabled_packs))
    data = {"required_capabilities": req, "enabled_packs": enabled,
            "warnings": res.get("warnings", []), "source": source,
            "at": datetime.now().isoformat()}
    _atomic_write(profile_path(project_dir), data)
    return data


def required_from_idea(idea: str) -> List[str]:
    """Derive required capabilities from the idea text via core.modality (+ the iot signal)."""
    try:
        from core import modality as _m
        mods = [m for m in _m.detect(idea or "") if m != "text"]
        if "sensor" in mods and "sensor" not in catalog():
            mods = [m for m in mods if m != "sensor"]
        return mods
    except Exception:
        return []


def persist_required(project_dir: str, idea: str) -> Dict:
    """Extend modality detection to PERSIST required capabilities (config profile)."""
    return save_profile(project_dir, required=required_from_idea(idea), source="modality")


def active_packs(project_dir: str) -> List[Dict]:
    """Packs enabled for a project (from its profile)."""
    prof = load_profile(project_dir)
    out = []
    for key in (prof.get("enabled_packs") or []):
        p = view(key)
        if p:
            out.append(p)
    return out
