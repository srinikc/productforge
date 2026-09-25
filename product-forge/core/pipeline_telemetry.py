"""
Pipeline Telemetry & Cost Reporting

Aggregates per-agent execution telemetry into agent -> stage -> phase -> pipeline
rollups, with soft-budget states, truncation flags, and alerts.

Reads (read-only, no execution):
  products/<project>/pipeline-execution-report.json
  products/<project>/agent-audit-log.json
  pipeline-definition.json
  config/model-tier.json (or project-tier)

This module is intentionally pure (no I/O side effects beyond reading and an
opt-in cost-history append) so it can be safely called from the dashboard API.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any


PHASE_MAP = {
    "0b": "1.5-Business", "0c": "1.5-Business", "0d": "1.5-Business", "0e": "1.5-Business",
    "13": "7-Operate", "13a": "7-Operate", "13b": "7-Operate",
    "0": "1-Ideation", "0a": "1-Ideation",
    "1": "2-Design", "1a": "2-Design", "1b": "2-Design", "1c": "2-Design",
    "2": "3-Architecture", "3": "3-Architecture",
    "4-0": "4-Implementation", "4a": "4-Implementation", "4a-vqa": "4-Implementation",
    "4b": "4-Implementation", "4b-vqa": "4-Implementation",
    "4c": "4-Implementation", "4c-vqa": "4-Implementation",
    "5": "5-Verification", "6": "5-Verification", "7": "5-Verification",
    "8": "6-Delivery", "9": "6-Delivery", "10": "6-Delivery",
    "11": "6-Delivery", "12": "6-Delivery",
}

WARN_PCT = 70.0
CRIT_PCT = 90.0
TRUNCATED_OUTPUT_CAP = 16000  # historical fallback when finish_reason absent


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
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "model-tier.json"),
        os.path.join(products_dir, "model-tier.json"),
    ]:
        data = _read_json(p)
        if data:
            return data
    return {}


def _ctx_window(registry, model: str) -> int:
    try:
        prof = registry.get_model(model)
        return prof.context_window if prof else 0
    except Exception:
        return 0


def _state(used: float, budget: float) -> str:
    if not budget or budget <= 0:
        return "n/a"
    pct = used / budget * 100.0
    if pct > 100.0:
        return "OVER"
    if pct >= CRIT_PCT:
        return "HIT"
    if pct >= WARN_PCT:
        return "warn"
    return "under"


def build_telemetry(project: str, products_dir: str = "products") -> Dict:
    """Build a full telemetry + cost rollup for a project's latest run."""
    from core.context_manager import get_contract
    from core.model_registry import ModelCapabilityRegistry

    project_dir = os.path.join(products_dir, project)
    report = _read_json(os.path.join(project_dir, "pipeline-execution-report.json")) or {}
    audit = _read_json(os.path.join(project_dir, "agent-audit-log.json")) or []
    project_cfg = _read_json(os.path.join(project_dir, "project.json")) or {}
    pipeline_def = _read_json("pipeline-definition.json") or {}
    tier = _find_tier_config(project_dir, products_dir)
    registry = ModelCapabilityRegistry()

    stages_def = pipeline_def.get("stages", {})
    stage_summary = report.get("stage_summary", {})

    # cache_hit / finish_reason / retries lookup from audit
    audit_index = {(e.get("stage_id"), e.get("agent_id")): e for e in audit if isinstance(e, dict)}
    timing_index = {}
    for t in (report.get("timings", {}) or {}).get("agents", []):
        timing_index[(t.get("stage_id"), t.get("agent_id"))] = t.get("duration_seconds", 0)

    # Budget spec (soft/hard/tolerance) from project.json
    budget_spec = project_cfg.get("budget", {}) if isinstance(project_cfg.get("budget"), dict) else {}
    soft_tokens = budget_spec.get("soft_tokens")
    hard_tokens = budget_spec.get("hard_tokens")
    soft_cost = budget_spec.get("soft_cost")
    hard_cost = budget_spec.get("hard_cost")
    tolerance = (
        budget_spec.get("variance_percent")
        or budget_spec.get("tolerance_percent")
        or project_cfg.get("budget_variance_percent")
        or 10
    )
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError):
        tolerance = 10.0

    agents_rows: List[Dict] = []
    tot_in = tot_out = tot_cached = tot_tokens = 0
    tot_cost = 0.0
    tot_time = 0.0
    app_hits = app_misses = truncated_count = 0
    tot_compaction = tot_continuations = 0

    for stage_id, sdata in stage_summary.items():
        stage_budget_usd = stages_def.get(stage_id, {}).get("budget_limit", 0.0)
        stage_cost = sdata.get("total_cost", 0.0)
        phase = PHASE_MAP.get(stage_id, "other")
        for a in sdata.get("agents", []):
            agent_id = a.get("agent_id", "")
            key = (stage_id, agent_id)
            au = audit_index.get(key, {})
            model = a.get("selected_model", "") or au.get("model", "")
            in_tok = a.get("input_tokens", 0)
            out_tok = a.get("output_tokens", 0)
            cached_tok = a.get("cached_tokens", 0)
            total_tok = a.get("total_tokens", 0)
            cost = a.get("cost", 0.0)
            t = timing_index.get(key, au.get("duration_seconds", 0))
            hit = bool(au.get("cache_hit", False))
            finish_reason = au.get("finish_reason", "")
            truncated = bool(au.get("truncated", False))
            if not finish_reason and out_tok >= TRUNCATED_OUTPUT_CAP:
                truncated = True
                finish_reason = "length(assumed)"
            retries = au.get("retries", 0)
            compaction_saved_chars = au.get("compaction_saved_chars", 0)
            continuations = au.get("continuations", 0)

            contract = get_contract(agent_id)
            c_in = contract.get("max_input_tokens", 0)
            c_out = contract.get("max_output_tokens", 0)
            c_budget = c_in + c_out

            if hit:
                app_hits += 1
            else:
                app_misses += 1
            if truncated:
                truncated_count += 1

            agents_rows.append({
                "phase": phase,
                "stage": stage_id,
                "agent": agent_id,
                "model": model,
                "context_window": _ctx_window(registry, model),
                "input_tokens": in_tok,
                "cached_input_tokens": cached_tok,
                "uncached_input_tokens": max(0, in_tok - cached_tok),
                "output_tokens": out_tok,
                "total_tokens": total_tok,
                "truncated": truncated,
                "finish_reason": finish_reason,
                "retries": retries,
                "compaction_saved_chars": compaction_saved_chars,
                "continuations": continuations,
                "cache_hit": hit,
                "cost": round(cost, 8),
                "time_seconds": round(t, 2),
                "contract_input_tokens": c_in,
                "contract_output_tokens": c_out,
                "contract_budget_tokens": c_budget,
                "budget_used_percent": round(total_tok / c_budget * 100.0, 1) if c_budget else 0.0,
                "budget_state": _state(total_tok, c_budget),
                "stage_budget_usd": stage_budget_usd,
                "cost_state": "OVER" if (stage_budget_usd and cost > stage_budget_usd) else "under",
            })
            tot_in += in_tok; tot_out += out_tok; tot_cached += cached_tok
            tot_tokens += total_tok; tot_cost += cost; tot_time += t
            tot_compaction += compaction_saved_chars
            tot_continuations += continuations

    # Stage rollups
    stages_rollup = {}
    for r in agents_rows:
        s = stages_rollup.setdefault(r["stage"], {
            "name": stages_def.get(r["stage"], {}).get("name", r["stage"]),
            "phase": r["phase"], "agents": 0, "input_tokens": 0, "output_tokens": 0,
            "cached_input_tokens": 0, "total_tokens": 0, "cost": 0.0, "time_seconds": 0.0,
            "truncated": 0,
        })
        s["agents"] += 1
        s["input_tokens"] += r["input_tokens"]
        s["output_tokens"] += r["output_tokens"]
        s["cached_input_tokens"] += r["cached_input_tokens"]
        s["total_tokens"] += r["total_tokens"]
        s["cost"] += r["cost"]
        s["time_seconds"] += r["time_seconds"]
        s["truncated"] += 1 if r["truncated"] else 0

    # Phase rollups
    phases_rollup = {}
    for r in agents_rows:
        p = phases_rollup.setdefault(r["phase"], {
            "agents": 0, "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0,
            "total_tokens": 0, "cost": 0.0, "time_seconds": 0.0, "truncated": 0,
        })
        p["agents"] += 1
        p["input_tokens"] += r["input_tokens"]
        p["output_tokens"] += r["output_tokens"]
        p["cached_input_tokens"] += r["cached_input_tokens"]
        p["total_tokens"] += r["total_tokens"]
        p["cost"] += r["cost"]
        p["time_seconds"] += r["time_seconds"]
        p["truncated"] += 1 if r["truncated"] else 0

    # Budget / alerts
    used_pct_tokens = (tot_tokens / soft_tokens * 100.0) if soft_tokens else None
    used_pct_cost = (tot_cost / soft_cost * 100.0) if soft_cost else None
    budget_status = "n/a"
    if soft_cost or soft_tokens:
        pct = max([x for x in [used_pct_tokens, used_pct_cost] if x is not None] or [0])
        if hard_cost and tot_cost >= hard_cost:
            budget_status = "hard_exceeded"
        elif hard_tokens and tot_tokens >= hard_tokens:
            budget_status = "hard_exceeded"
        elif pct > 100 + tolerance:
            budget_status = "over_tolerance"
        elif pct >= CRIT_PCT:
            budget_status = "critical"
        elif pct >= WARN_PCT:
            budget_status = "warning"
        else:
            budget_status = "ok"

    alerts: List[Dict] = []
    if used_pct_tokens is not None and used_pct_tokens >= WARN_PCT:
        alerts.append({"level": "warn" if used_pct_tokens < CRIT_PCT else "critical",
                       "scope": "pipeline", "metric": "tokens",
                       "message": f"Pipeline token usage {used_pct_tokens:.1f}% of soft budget"})
    if used_pct_cost is not None and used_pct_cost >= WARN_PCT:
        alerts.append({"level": "warn" if used_pct_cost < CRIT_PCT else "critical",
                       "scope": "pipeline", "metric": "cost",
                       "message": f"Pipeline cost usage {used_pct_cost:.1f}% of soft budget"})
    for r in agents_rows:
        if r["truncated"]:
            alerts.append({"level": "warning", "scope": f"{r['stage']}/{r['agent']}",
                           "metric": "output", "message": "Output truncated (finish_reason=length)"})
        if r["budget_state"] == "OVER":
            alerts.append({"level": "info", "scope": f"{r['stage']}/{r['agent']}",
                           "metric": "tokens",
                           "message": f"Agent used {r['budget_used_percent']}% of its contract token budget"})

    return {
        "project": project,
        "pipeline_id": report.get("pipeline_id", ""),
        "generated_at": datetime.now().isoformat(),
        "phase": report.get("phase", ""),
        "started_at": report.get("started_at", ""),
        "completed_at": report.get("completed_at", ""),
        "duration_seconds": report.get("total_duration_seconds", 0),
        "totals": {
            "agents": len(agents_rows),
            "input_tokens": tot_in,
            "cached_input_tokens": tot_cached,
            "uncached_input_tokens": max(0, tot_in - tot_cached),
            "output_tokens": tot_out,
            "total_tokens": tot_tokens,
            "cost": round(tot_cost, 8),
            "agent_time_seconds": round(tot_time, 2),
            "wall_clock_seconds": report.get("total_duration_seconds", 0),
            "app_cache_hits": app_hits,
            "app_cache_misses": app_misses,
            "truncated_count": truncated_count,
            "compaction_saved_chars": tot_compaction,
            "compaction_saved_tokens_est": tot_compaction // 4,
            "continuations": tot_continuations,
        },
        "budget": {
            "spec": budget_spec,
            "soft_tokens": soft_tokens,
            "hard_tokens": hard_tokens,
            "soft_cost": soft_cost,
            "hard_cost": hard_cost,
            "tolerance_percent": tolerance,
            "used_tokens": tot_tokens,
            "used_cost": round(tot_cost, 8),
            "used_percent_tokens": round(used_pct_tokens, 2) if used_pct_tokens is not None else None,
            "used_percent_cost": round(used_pct_cost, 2) if used_pct_cost is not None else None,
            "status": budget_status,
        },
        "alerts": alerts,
        "agents": agents_rows,
        "stages": stages_rollup,
        "phases": phases_rollup,
    }


# ─── Cross-project cost history ──────────────────────────────────────────

HISTORY_FILE = "pipeline_cost_history.json"


def append_cost_history(project: str, products_dir: str = "products") -> Dict:
    """Append this project's latest run summary into the unified budget store history."""
    tel = build_telemetry(project, products_dir)
    entry = {
        "project": project,
        "pipeline_id": tel.get("pipeline_id"),
        "date": tel.get("completed_at") or datetime.now().isoformat(),
        "models": sorted({a["model"] for a in tel["agents"] if a["model"]}),
        "total_input_tokens": tel["totals"]["input_tokens"],
        "total_output_tokens": tel["totals"]["output_tokens"],
        "total_cached_tokens": tel["totals"]["cached_input_tokens"],
        "total_tokens": tel["totals"]["total_tokens"],
        "total_cost": tel["totals"]["cost"],
        "duration_seconds": tel["totals"]["wall_clock_seconds"],
        "truncated_count": tel["totals"]["truncated_count"],
        "budget_status": tel["budget"]["status"],
        "used_percent_cost": tel["budget"]["used_percent_cost"],
    }
    try:
        from core import budget as _b
        _b.migrate_legacy(None, products_dir)
        hist = _b.read_section(None, "history", products_dir) or []
        hist = [h for h in hist if not (h.get("kind") == "run_cost_summary"
                                        and h.get("project") == project
                                        and h.get("pipeline_id") == entry["pipeline_id"])]
        hist.append({"kind": "run_cost_summary", **entry})
        data = _b.load(None, products_dir)
        data["history"] = hist[-5000:]
        _b.save(None, data, products_dir)
    except Exception:
        pass
    return entry


def read_cost_history(products_dir: str = "products") -> List[Dict]:
    try:
        from core import budget as _b
        _b.migrate_legacy(None, products_dir)
        hist = _b.read_section(None, "history", products_dir) or []
        return [h for h in hist if h.get("kind") == "run_cost_summary"]
    except Exception:
        return []
