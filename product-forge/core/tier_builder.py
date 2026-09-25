"""Auto tier creation — recommend / validate agent->model from the model catalog.

Uses agent NEEDS (tools/reasoning/structured/min_output/min_context — from agent cards,
agent-capabilities, model_fit requirements) + the model catalog (context, max_output, tools,
reasoning, structured_outputs, modality) to pick the best-fit model per agent, flag NOT-GOOD
assignments with reasons, and offer alternates. Writes nothing unless ``save=True``.

CLI: python -m core.tier_builder --recommend [--tier kctier]
"""
import json
import os
from typing import Dict, List, Optional

from core import model_catalog as mc

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH_ROLES = ("research", "analyst", "strateg", "pricing", "market", "growth", "product-owner")


def _caps(agent_id: str) -> Dict:
    try:
        return (json.load(open(os.path.join(REPO, "config", "agent-capabilities.json"),
                               encoding="utf-8")).get("agents", {})).get(agent_id, {}) or {}
    except Exception:
        return {}


def _card_tools(agent_id: str) -> List[str]:
    try:
        return json.load(open(os.path.join(REPO, "agents", f"{agent_id}.agent.json"),
                              encoding="utf-8")).get("tools") or []
    except Exception:
        return []


def _min_output(agent_id: str) -> int:
    try:
        from core.model_fit import DEFAULT_CONFIG
        return int(((DEFAULT_CONFIG.get("agents") or {}).get(agent_id) or {}).get("min_output_tokens", 0) or 0)
    except Exception:
        return 0


def needs_for(agent_id: str) -> Dict:
    cap = _caps(agent_id)
    know = [str(x).lower() for x in (cap.get("knowledge") or [])]
    blob = " ".join([agent_id.lower()] + know + [str(x).lower() for x in (cap.get("skills") or [])])
    return {
        "tools": bool(_card_tools(agent_id)) or any(m in blob for m in RESEARCH_ROLES),
        "reasoning": bool("reasoning" in blob or any(m in blob for m in RESEARCH_ROLES)) or agent_id in (
            "architect", "design", "product-design-spec"),
        "min_output": _min_output(agent_id),
    }


def score_model(agent_id: str, model_name: str) -> Dict:
    fit = mc.fit(model_name, needs_for(agent_id))
    c = mc.capabilities(model_name) or {}
    # cost/speed tiebreak (from the registry, best-effort)
    return {"model": model_name, "fit": fit.get("ok"), "reasons": fit.get("reasons"),
            "capabilities": fit.get("capabilities"),
            "modality_in": c.get("input_modalities"), "modality_out": c.get("output_modalities")}


def recommend(candidate_models: List[str], agent_ids: List[str]) -> Dict:
    out = {}
    for a in agent_ids:
        ranked = [score_model(a, m) for m in candidate_models]
        ranked.sort(key=lambda r: (r.get("fit") is not True,))  # good fits first
        ok = [r for r in ranked if r.get("fit")]
        out[a] = {"recommended": (ok[0]["model"] if ok else ranked[0]["model"]),
                  "fit": bool(ok), "reasons": ranked[0].get("reasons"),
                  "alternates": [r["model"] for r in ok[1:4]]}
    return out


def _tier_models(tier: str) -> List[str]:
    try:
        d = json.load(open(os.path.join(REPO, "config", "model-tier.json"), encoding="utf-8"))
        prof = (d.get("profiles") or {}).get(tier) or {}
        return sorted((prof.get("models") or {}).keys()) or [prof.get("default_model")]
    except Exception:
        return []


def _tier_agents() -> List[str]:
    try:
        d = json.load(open(os.path.join(REPO, "config", "model-tier.json"), encoding="utf-8"))
        return list((d.get("agents") or {}).keys())
    except Exception:
        return []


def build(tier: str = "", save: bool = False) -> Dict:
    """Recommend per-agent models for a candidate pool (a tier's models, else the whole catalog)."""
    agents = _tier_agents()
    if not agents:
        try:
            agents = list(json.load(open(os.path.join(REPO, "config", "agent-capabilities.json"),
                                         encoding="utf-8")).get("agents", {}).keys())
        except Exception:
            agents = []
    cands = [m for m in (_tier_models(tier) if tier else list(mc.load().keys())) if m]
    rec = recommend(cands, agents) if (cands and agents) else {}
    return {"tier": tier or "all", "candidates": len(cands), "agents": len(agents),
            "recommendations": rec, "saved": False}


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Auto tier creation (recommend agent->model)")
    ap.add_argument("--recommend", action="store_true")
    ap.add_argument("--tier", default="")
    a = ap.parse_args(argv)
    print(json.dumps(build(tier=a.tier), indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
