"""Per-unit cost model — media billed per image/second/char/track/mesh + token costs (BI-0194).

Single owner of per-unit costing. Price sources are existing configs (no new price store):
``config/generators.json`` (media: billing_unit + unit_price) and ``config/model-catalog.json`` /
``core.budget_planner`` (tokens: $/1k in/out). ``project()`` folds token + per-unit media cost into a
per-stage/per-agent projection + free/paid mix. The text path is byte-identical to the legacy per-token
formula. Writes exactly one derived artifact (Cost-Projection). See docs/PER-UNIT-COST-DESIGN.md.
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

PROJECTION_NAME = "Cost-Projection"
UNITS = ("image", "second", "char", "track", "mesh")


def _read_json(path: str) -> Optional[Dict]:
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def _generators() -> Dict:
    d = _read_json(os.path.join(str(_ROOT), "config", "generators." + "json")) or {}
    return d.get("generators") or {}


# ── schema: billing_unit + unit_price ───────────────────────────────────────
def unit_price(model_or_generator_id: str) -> Dict:
    """Look up {billing_unit, unit_price, free} for a media generator (or token default)."""
    g = _generators().get(model_or_generator_id)
    if g:
        return {"billing_unit": g.get("billing_unit") or "call",
                "unit_price": float(g.get("unit_price") or 0.0),
                "free": bool(g.get("free"))}
    return {"billing_unit": "token", "unit_price": 0.0, "free": False}


def cost_of(model_or_generator_id: str, units: float) -> float:
    """cost = unit_price x units (per-unit schema)."""
    p = unit_price(model_or_generator_id)
    return round(float(p["unit_price"]) * float(units or 0), 6)


def token_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Legacy per-token cost (unchanged formula from budget_planner)."""
    try:
        from core.model_registry import ModelCapabilityRegistry
        reg = ModelCapabilityRegistry()
        m = next((x for x in reg.list_models() if x.name == model), None)
        if m is None:
            return 0.0
        return round((input_tokens / 1000.0) * (getattr(m, "cost_per_1k_input", 0.0) or 0.0)
                     + (output_tokens / 1000.0) * (getattr(m, "cost_per_1k_output", 0.0) or 0.0), 6)
    except Exception:
        return 0.0


# ── projection (fold token + per-unit media; text path unchanged) ───────────
def project(project_dir: str, quantities: Optional[Dict] = None,
            token_usage: Optional[Dict] = None) -> Dict:
    """Project cost per stage/agent + total + free/paid mix.

    quantities: {generator_id: units} for media (per-unit pricing).
    token_usage: {model: {input, output}} for text (per-token pricing).
    With no media quantities, the result equals the legacy per-token projection.
    """
    quantities = quantities or {}
    token_usage = token_usage or {}

    per_unit: List[Dict] = []
    total_units = 0.0
    free_units = 0.0
    for gen, units in quantities.items():
        p = unit_price(gen)
        c = round(p["unit_price"] * float(units or 0), 6)
        total_units += float(units or 0)
        if p["free"]:
            free_units += float(units or 0)
        per_unit.append({"generator": gen, "billing_unit": p["billing_unit"],
                         "units": float(units or 0), "unit_price": p["unit_price"],
                         "cost": c, "free": p["free"]})

    per_token: List[Dict] = []
    for model, u in token_usage.items():
        c = token_cost(model, int(u.get("input", 0)), int(u.get("output", 0)))
        per_token.append({"model": model, "input": int(u.get("input", 0)),
                          "output": int(u.get("output", 0)), "cost": c})

    media_cost = round(sum(r["cost"] for r in per_unit), 6)
    text_cost = round(sum(r["cost"] for r in per_token), 6)
    total = round(media_cost + text_cost, 6)
    return {
        "currency": "USD",
        "per_unit": per_unit, "per_token": per_token,
        "media_cost": media_cost, "text_cost": text_cost, "total_cost": total,
        "free_units": free_units, "paid_units": round(total_units - free_units, 6),
        "free_paid_mix": {"free_units": free_units, "paid_units": round(total_units - free_units, 6)},
        "has_media": bool(per_unit),
    }


def estimate(model_or_generator_id: str, units: float) -> Dict:
    """Ad-hoc per-unit estimate for one generator/model."""
    p = unit_price(model_or_generator_id)
    return {"generator": model_or_generator_id, **p, "units": float(units or 0),
            "cost": round(p["unit_price"] * float(units or 0), 6)}


def _projection_path(project_dir: str) -> str:
    return os.path.join(project_dir, "artifacts", "9 - Package", PROJECTION_NAME + "." + "json")


def write_projection(project_dir: str, quantities: Optional[Dict] = None,
                     token_usage: Optional[Dict] = None) -> Dict:
    """Single writer of the Cost-Projection artifact (deterministic, auditable)."""
    proj = project(project_dir, quantities, token_usage)
    try:
        path = _projection_path(project_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(proj, f, indent=2)
    except Exception:
        pass
    return proj


def schema() -> Dict:
    """The per-unit cost schema (for API/discovery)."""
    rows = []
    for gen, g in _generators().items():
        rows.append({"generator": gen, "kind": g.get("kind", ""),
                     "billing_unit": g.get("billing_unit", "call"),
                     "unit_price": float(g.get("unit_price") or 0.0),
                     "free": bool(g.get("free"))})
    return {"units": list(UNITS), "token_basis": "$/1k input + $/1k output",
            "formula": "cost = unit_price x units", "generators": rows}
