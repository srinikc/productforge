"""
Budget Planner & Model-Tier Proposer

Given a project budget envelope (soft/hard cost or tokens + tolerance), this
module proposes a per-agent model tier that fits the budget *without* dropping
any agent below its capability floor, and explains every choice.

Design principles (from cost research):
  - Criticality-aware: high-value roles (architecture, security, synthesis)
    keep stronger models; routine roles can be down-routed.
  - Capability floor: never downgrade below a per-criticality quality floor.
  - Explainable: every selection carries a rationale.
  - Never silently force: if the budget cannot be met within floors, report
    infeasible and let the human decide.
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
from typing import Dict, List, Optional, Any


# Role criticality: how costly a wrong answer is / how hard it is to verify.
CRITICALITY = {
    "architect": "critical",
    "security": "critical",
    "orchestrator": "critical",
    "design": "critical",
    "implement": "high",
    "implement-api": "high",
    "implement-db": "high",
    "implement-logic": "high",
    "implement-ui": "high",
    "ideation": "high",
    "code-review": "high",
    "devops": "medium",
    "validate": "medium",
    "discovery": "medium",
    "product-design-spec": "medium",
    "ux-ia": "medium",
    "design_critic": "medium",
    "visual_qa": "medium",
    "document": "medium",
    "package": "low",
}

# Minimum quality_score per criticality (the capability floor).
QUALITY_FLOOR = {
    "critical": 0.80,
    "high": 0.75,
    "medium": 0.70,
    "low": 0.0,
}

DEFAULT_CRITICALITY = "medium"

ROOT = str(_PF_ROOT)


def _read_json(path: str) -> Optional[Any]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _find_tier_config(project_dir: str, products_dir: str) -> Dict:
    for p in [
        os.path.join(project_dir, "model-tier.json"),
        os.path.join(str(_PF_ROOT), "config", "model-tier.json"),
        os.path.join(products_dir, "model-tier.json"),
    ]:
        data = _read_json(p)
        if data:
            return data
    return {}


def _blended(profile) -> float:
    return (profile.cost_per_1k_input or 0.0) + (profile.cost_per_1k_output or 0.0)


def _agent_expected_tokens(agent_id: str) -> Dict[str, int]:
    """Plan-level expected tokens per agent (upper bound from the contract)."""
    try:
        from core.context_manager import get_contract
        c = get_contract(agent_id)
        return {"input": c.get("max_input_tokens", 8000), "output": c.get("max_output_tokens", 4000)}
    except Exception:
        return {"input": 8000, "output": 4000}


def propose_tier(project: str, products_dir: str = "products") -> Dict:
    """Propose a per-agent model tier that fits the project budget."""
    from core.model_registry import ModelCapabilityRegistry

    project_dir = os.path.join(products_dir, project)
    project_cfg = _read_json(os.path.join(project_dir, "project.json")) or {}
    tier = _find_tier_config(project_dir, products_dir)
    registry = ModelCapabilityRegistry()
    models = {m.name: m for m in registry.list_models() if getattr(m, "enabled", True)}

    # Candidate pool: opencode-go models (cheapest capable per floor).
    go_models = [m for m in models.values() if getattr(m, "provider", "") == "opencode-go"]
    if not go_models:
        go_models = list(models.values())

    budget = project_cfg.get("budget", {}) if isinstance(project_cfg.get("budget"), dict) else {}
    currency = budget.get("currency", "USD")
    # Variance/tolerance the user can enter; defaults to 10% if not provided.
    # Accepted locations: budget.variance_percent, budget.tolerance_percent,
    # or top-level project field budget_variance_percent.
    tolerance = (
        budget.get("variance_percent")
        or budget.get("tolerance_percent")
        or project_cfg.get("budget_variance_percent")
        or 10
    )
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError):
        tolerance = 10.0
    soft_cost = budget.get("soft_cost")
    hard_cost = budget.get("hard_cost")
    soft_tokens = budget.get("soft_tokens")
    hard_tokens = budget.get("hard_tokens")

    # Which agents are in play (from pipeline definition ideal_flow; fall back to CRITICALITY keys)
    pipeline_def = _read_json(os.path.join(ROOT, "pipeline-definition.json")) or {}
    agent_ids = set()
    for sid, s in (pipeline_def.get("stages", {}) or {}).items():
        for a in s.get("ideal_flow", []) or []:
            agent_ids.add(a)
    if not agent_ids:
        agent_ids = set(CRITICALITY.keys())

    agent_tier_cfg = tier.get("agents", {})
    stage_tier_cfg = tier.get("stages", {})
    default_tier_model = None
    if tier.get("stages"):
        # pick any explicit stage model as the baseline representative
        default_tier_model = next(iter(tier["stages"].values())).get("model")

    per_agent = []
    projected_total = 0.0
    baseline_total = 0.0
    infeasible = []
    projected_tokens = 0

    for agent_id in sorted(agent_ids):
        crit = CRITICALITY.get(agent_id, DEFAULT_CRITICALITY)
        floor = QUALITY_FLOOR.get(crit, 0.70)
        expected = _agent_expected_tokens(agent_id)
        exp_tokens = expected["input"] + expected["output"]
        projected_tokens += exp_tokens

        current_model = agent_tier_cfg.get(agent_id, {}).get("model") or default_tier_model
        cur_profile = models.get(current_model)

        # Baseline cost (current tier)
        if cur_profile:
            baseline_total += (expected["input"] / 1000 * cur_profile.cost_per_1k_input +
                               expected["output"] / 1000 * cur_profile.cost_per_1k_output)

        # Candidates meeting the floor, cheapest first
        capable = [m for m in go_models if (m.quality_score or 0) >= floor]
        capable.sort(key=lambda m: _blended(m))

        if not capable:
            infeasible.append(agent_id)
            chosen = cur_profile
            rationale = (f"NO candidate meets quality floor {floor} for criticality "
                         f"'{crit}' — keeping {current_model}; human decision required.")
        else:
            cheapest = capable[0]
            # Keep the current model if it already meets floor and is among the
            # cheapest capable options; otherwise down-route to the cheapest capable.
            if cur_profile and (cur_profile.quality_score or 0) >= floor and _blended(cur_profile) <= _blended(cheapest) * 1.5:
                chosen = cur_profile
                rationale = (f"kept {current_model}: criticality '{crit}', quality "
                             f"{cur_profile.quality_score} >= floor {floor}.")
            else:
                chosen = cheapest
                if cur_profile and current_model != chosen.name:
                    direction = "up-routed" if _blended(chosen) > _blended(cur_profile) else "down-routed"
                    rationale = (f"{direction} {current_model} -> {chosen.name}: criticality "
                                 f"'{crit}', quality {chosen.quality_score} >= floor {floor}, "
                                 f"select cheapest capable model.")
                else:
                    rationale = (f"selected {chosen.name}: cheapest model meeting floor {floor} "
                                 f"for criticality '{crit}'.")

        if chosen:
            cost = (expected["input"] / 1000 * chosen.cost_per_1k_input +
                    expected["output"] / 1000 * chosen.cost_per_1k_output)
            projected_total += cost
            per_agent.append({
                "agent": agent_id,
                "criticality": crit,
                "quality_floor": floor,
                "current_model": current_model,
                "proposed_model": chosen.name,
                "proposed_quality": chosen.quality_score,
                "projected_cost": round(cost, 6),
                "rationale": rationale,
                "floor_respected": (chosen.quality_score or 0) >= floor,
            })
        else:
            per_agent.append({
                "agent": agent_id,
                "criticality": crit,
                "quality_floor": floor,
                "current_model": current_model,
                "proposed_model": None,
                "projected_cost": None,
                "rationale": rationale,
                "floor_respected": False,
            })

    fits_soft = (soft_cost is None) or (projected_total <= soft_cost)
    within_tolerance = (soft_cost is None) or (projected_total <= soft_cost * (1 + tolerance / 100.0))
    exceeds_hard = (hard_cost is not None) and (projected_total > hard_cost)
    tokens_ok = True
    if soft_tokens is not None and projected_tokens > soft_tokens:
        tokens_ok = False
    feasible = fits_soft and tokens_ok and not infeasible

    warnings = []
    if infeasible:
        warnings.append(f"Budget cannot be met within capability floors for: {infeasible}")
    if not fits_soft and not infeasible:
        warnings.append("Projected cost exceeds soft budget even at the capability floor; "
                        "consider trimming optional stages or raising budget.")
    if exceeds_hard:
        warnings.append("Projected cost exceeds the HARD budget; run should not proceed without approval.")

    return {
        "project": project,
        "currency": currency,
        "budget": budget,
        "variance_percent": tolerance,
        "baseline_total_cost": round(baseline_total, 6),
        "projected_total_cost": round(projected_total, 6),
        "projected_total_tokens": projected_tokens,
        "fits_soft": fits_soft,
        "within_tolerance": within_tolerance,
        "exceeds_hard": exceeds_hard,
        "feasible": feasible,
        "per_agent": per_agent,
        "warnings": warnings,
    }


def apply_proposal(project: str, products_dir: str = "products", approve: bool = False) -> Dict:
    """Write a runtime model-tier for the project from the current proposal.

    Requires explicit approval (approve=True) because it changes quality/cost.
    """
    if not approve:
        return {"error": "approval required", "hint": "pass approve=true to apply"}
    proposal = propose_tier(project, products_dir)
    project_dir = os.path.join(products_dir, project)
    os.makedirs(project_dir, exist_ok=True)
    out = os.path.join(project_dir, "model-tier.json")

    existing = _read_json(out) or _read_json(
        os.path.join(str(_PF_ROOT),
                     "config", "model-tier.json")) or {}

    agents_cfg = {}
    for row in proposal["per_agent"]:
        if row.get("proposed_model"):
            agents_cfg[row["agent"]] = {
                "model": row["proposed_model"],
                "provider": "opencode-go",
                "rationale": row["rationale"],
                "criticality": row["criticality"],
            }

    runtime = {
        "default_tier": existing.get("default_tier", "opencode-go-cheap"),
        "api_endpoint": existing.get("api_endpoint", "https://opencode.ai/zen/go/v1/chat/completions"),
        "agents": agents_cfg,
        "budget": proposal["budget"],
        "variance_percent": proposal.get("variance_percent", 10),
        "projected_total_cost": proposal["projected_total_cost"],
        "generated_by": "budget_planner.apply_proposal",
    }
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(runtime, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"error": str(e)}

    return {"status": "applied", "path": out, "agents": len(agents_cfg),
            "projected_total_cost": proposal["projected_total_cost"]}
