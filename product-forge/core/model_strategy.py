"""Two-phase model & capability strategy gate (BI-0192 + BI-0210).

Gate A (post-ideation ``0a``): detect modality -> enable capability packs -> pick coarse model KINDS
(text/vision/audio/video/generator) + a provisional free/paid mix.
Gate B (post-architect ``2``): refine to concrete models/providers per agent using the tech stack.

Single writer of ``products/<project>/model-strategy.json``. LLM model changes are applied through the
existing per-agent override store (``core.agent_model_override``, BI-0178); media-OUT is a *generator id*,
never a chat model. Plain-text projects: NO-OP (byte-identical).

Reuses (never duplicates): ``modality``, ``capability_packs``, ``feasibility``, ``generator_adapters``,
``model_catalog``, ``tier_builder``, ``model_router``, ``pipeline_composition``, ``provider_kinds``.
See docs/MODEL-STRATEGY-DESIGN.md.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

REPORT_NAME = "model-strategy." + "json"
ITEM = "BI-0192"

# kind per modality for media-OUT (generator kinds)
_MEDIA_KIND = {"image": "image-gen", "video": "video-gen", "audio": "tts", "music": "music", "3d": "3d"}
_TEXTISH = {"", "text", "none"}


def report_path(project_dir: str) -> str:
    return os.path.join(project_dir, REPORT_NAME)


def load_report(project_dir: str) -> Dict:
    try:
        with open(report_path(project_dir), encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_report(project_dir: str, data: Dict) -> None:
    p = report_path(project_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _apply_mode() -> str:
    try:
        from core import env_flags as _ef
        return str(_ef.get("PIPELINE_MODEL_STRATEGY", "warn") or "warn").lower()
    except Exception:
        return os.getenv("PIPELINE_MODEL_STRATEGY", "warn").lower()


def _gate_b_enabled() -> bool:
    try:
        from core import env_flags as _ef
        return str(_ef.get("PIPELINE_MODEL_STRATEGY_GATE_B", "1") or "1") not in ("0", "false", "no", "off")
    except Exception:
        return os.getenv("PIPELINE_MODEL_STRATEGY_GATE_B", "1") not in ("0", "false", "no", "off")


def required(project_dir: str) -> List[str]:
    try:
        from core import capability_packs as _cp
        prof = _cp.load_profile(project_dir)
        req = prof.get("required_capabilities") or []
        if req:
            return [m for m in req if str(m).lower() not in _TEXTISH]
    except Exception:
        pass
    return []


def _is_noop(project_dir: str) -> bool:
    """No required media capability => strategy is a no-op (plain-text project, byte-identical)."""
    return not required(project_dir)


# ── assessment ──────────────────────────────────────────────────────────────
def assess(project_dir: str, phase: str = "a") -> Dict:
    """Compute the strategy decision (pure; no writes except pack profile by caller)."""
    mods = required(project_dir)
    enabled: List[str] = []
    warnings: List[str] = []
    try:
        from core import capability_packs as _cp
        res = _cp.resolve(mods) if mods else {"enabled": [], "warnings": []}
        enabled = [e.get("key") for e in res.get("enabled", [])]
        warnings.extend(res.get("warnings", []))
    except Exception:
        pass
    # per-modality: generator + build mode + license (reuse feasibility)
    feas: Dict = {}
    try:
        from core import feasibility as _fs
        fb = _fs.assess_build(project_dir)
        feas = fb
    except Exception:
        pass
    assignments: List[Dict] = []
    for row in (feas.get("per_modality") or []):
        m = row.get("modality")
        if m in _TEXTISH:
            continue
        gen = ""
        provider = row.get("provider_kind", "")
        billing = ""
        try:
            from core import generator_adapters as _ga
            g = _ga.select(_MEDIA_KIND.get(m, ""), [m])
            if g:
                gen = g.get("id", "")
                provider = g.get("provider", provider)
                billing = g.get("billing_unit", "")
        except Exception:
            pass
        assignments.append({
            "modality": m, "kind": "generator", "model": "", "generator": gen,
            "provider": provider, "provider_kind": row.get("provider_kind", ""),
            "billing_unit": billing, "build_mode": row.get("build_mode", ""),
            "license": row.get("license", ""), "bundle_allowed": row.get("bundle_allowed", False),
        })
    return {"phase": phase, "modalities": mods, "enabled_packs": enabled,
            "generators_needed": (feas.get("verdict") and [] or []),
            "feasibility_verdict": feas.get("verdict", ""),
            "assignments": assignments, "warnings": warnings}


def _resolve_agent_models(assignments: List[Dict]) -> Dict[str, Dict]:
    """Gate B: map per-agent LLM kinds to concrete models via the catalog + tier. Best-effort,
    recommend-only; keep it small and deterministic. Media-OUT generators are not chat models."""
    out: Dict[str, Dict] = {}
    try:
        from core import agent_capabilities as _ac
        from core import model_catalog as _mc
    except Exception:
        return out
    # agents needing vision (media input) -> require an image-input model
    for aid in (_ac.config().get("agents") or {}):
        vec = _ac.vector(aid)
        kind = "text"
        model = ""
        if vec.get("needs_vision"):
            kind = "vision"
            try:
                from core import modality as _mo
                ids = _mo.models_for_input("image", limit=5)
                model = ids[0] if ids else ""
            except Exception:
                model = ""
        if model:
            out[aid] = {"kind": kind, "model": model, "source": "strategy-gate-b"}
    return out


# ── gates ───────────────────────────────────────────────────────────────────
def gate_a(project_dir: str) -> Dict:
    """Post-0a: enable packs + coarse kinds + recompose. No-op when nothing media-relevant."""
    if _is_noop(project_dir):
        return {"gate": "a", "noop": True}
    dec = assess(project_dir, phase="a")
    data = load_report(project_dir)
    data.update({"schema": "product-forge/model-strategy@1",
                 "project": os.path.basename(os.path.normpath(project_dir)),
                 "item_id": ITEM, "related_items": ["BI-0210", "BI-0214"],
                 "generated_at": datetime.now().isoformat(),
                 "gate_a": {**dec, "at": datetime.now().isoformat()},
                 "gate_b": data.get("gate_b") or {},
                 "applied": data.get("applied") or {}})
    save_report(project_dir, data)
    return data


def gate_b(project_dir: str) -> Dict:
    """Post-architect: refine concrete models from the tech stack. No-op when nothing media-relevant."""
    if not _gate_b_enabled() or _is_noop(project_dir):
        return {"gate": "b", "noop": True}
    data = load_report(project_dir)
    assignments = _resolve_agent_models((data.get("gate_a") or {}).get("assignments") or [])
    data["gate_b"] = {"at": datetime.now().isoformat(), "architecture_ref": "docs/tech-stack.json",
                      "assignments": [{"agent": a, **v} for a, v in assignments.items()],
                      "warnings": []}
    save_report(project_dir, data)
    return data


def apply(project_dir: str, executor=None, mode: str = "") -> Dict:
    """Apply Gate B LLM assignments via the per-agent override store (opt-in ``apply`` mode)."""
    mode = mode or _apply_mode()
    data = load_report(project_dir)
    applied: Dict[str, Dict] = {}
    if mode == "apply":
        try:
            from core import agent_model_override as _ov
        except Exception:
            _ov = None
        for row in ((data.get("gate_b") or {}).get("assignments") or []):
            a, m = row.get("agent"), row.get("model")
            if _ov and a and m:
                try:
                    _ov.set(project_dir, a, m, note="BI-0192 gate B")
                    applied[a] = {"model": m, "source": "strategy-gate-b"}
                except Exception:
                    pass
    data["applied"] = {"mode": mode, "store": "agent-model-overrides.json",
                       "overrides": applied, "applied_at": datetime.now().isoformat()}
    save_report(project_dir, data)
    return data


def verdict(project_dir: str) -> Dict:
    d = load_report(project_dir)
    return {"enabled_packs": (d.get("gate_a") or {}).get("enabled_packs", []),
            "applied": (d.get("applied") or {}).get("overrides", {})}


def kind_of_agent(project_dir: str, agent_id: str) -> str:
    d = load_report(project_dir)
    for row in ((d.get("gate_b") or {}).get("assignments") or []):
        if row.get("agent") == agent_id:
            return row.get("kind", "text")
    return "text"
