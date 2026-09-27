"""Work estimate — predict an agent's call shape and time BEFORE it runs.

Combines a DETERMINISTIC base (strategy + #features + #sections + tool-loop cap) with
an observed overlay (call-ledger history per agent/model: call counts + ms/call).
Output: {llm_min, llm_typical, llm_max, tools_typical, ms_per_call, est_minutes, basis}.

Store: products/<project>/work-estimate.json (kind=derived, scope=project). API-readable.
Owner: this module.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

FILENAME = "work-estimate.json"
_TOOL_AGENTS = ("implement", "implement-api", "implement-db", "implement-logic",
                "implement-ui", "devops", "fix", "validate", "package")
_DEFAULT_MS = 30000


def _rj(path: str, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _root() -> str:
    try:
        from core.paths import ROOT
        return str(ROOT)
    except Exception:
        return "."


def _sections(agent_id: str) -> int:
    try:
        from core.agent_requirements import required_sections
        spec = required_sections(agent_id) or {}
        n = len((spec.get("essential") or {})) + len((spec.get("recommended") or {}))
        return n or 6
    except Exception:
        return 6


def _features(project_dir: str) -> Optional[int]:
    d = _rj(os.path.join(project_dir, "product-plan.json"), {})
    n = 0
    for mod in (d.get("modules") or []):
        n += len((mod or {}).get("features") or [])
    return n or None


def _strategy(agent_id: str) -> str:
    try:
        from core.agent_requirements import per_feature_agents, generation_strategy
        if agent_id in set(per_feature_agents()):
            return "per-feature"
    except Exception:
        pass
    if agent_id in _TOOL_AGENTS or agent_id.startswith("implement"):
        return "tool-loop"
    try:
        from core.agent_requirements import generation_strategy
        g = generation_strategy(agent_id)
        if g == "sectioned":
            return "sectioned"
    except Exception:
        pass
    return "single"


def _ledger_stats(project_dir: str) -> Dict:
    try:
        from core import call_ledger
        recs = call_ledger.read(project_dir)
    except Exception:
        recs = []
    llm_ms, by_agent, by_model = [], {}, {}
    for r in recs:
        a = str(r.get("agent", "") or "?")
        d = by_agent.setdefault(a, {"llm": 0, "tool": 0, "ms": 0})
        if r.get("kind") == "llm":
            ms = int(r.get("duration_ms", 0) or 0)
            d["llm"] += 1
            d["ms"] += ms
            if ms:
                llm_ms.append(ms)
                m = str(r.get("model", "") or "?")
                by_model.setdefault(m, []).append(ms)
        elif r.get("kind") == "tool":
            d["tool"] += 1
    default_ms = int(sum(llm_ms) / len(llm_ms)) if llm_ms else _DEFAULT_MS
    model_ms = {m: int(sum(v) / len(v)) for m, v in by_model.items() if v}
    return {"default_ms": default_ms, "by_agent": by_agent, "by_model": model_ms}


def estimate_agent(project_dir: str, agent_id: str, stage_id: str = "",
                   model: str = "") -> Dict:
    strat = _strategy(agent_id)
    sections = _sections(agent_id)
    feats = _features(project_dir) or 6
    stats = _ledger_stats(project_dir)
    ms = stats["by_model"].get(model) or stats["default_ms"] or _DEFAULT_MS

    if strat == "tool-loop":
        base_min, base_typ, base_max = 1, 3, 12
        tools_typ, tools_max = 2, 10
        basis = "tool-loop (llm iterations ~ tools)"
    elif strat == "per-feature":
        base_min, base_typ, base_max = sections, feats * sections, feats * sections * 2
        tools_typ = tools_max = 0
        basis = f"{feats} features x {sections} sections"
    elif strat == "sectioned":
        base_min, base_typ, base_max = 1, sections, sections * 3
        tools_typ = tools_max = 0
        basis = f"{sections} sections (sectioned)"
    else:
        base_min, base_typ, base_max = 1, 1, 3 + 6
        tools_typ = tools_max = 0
        basis = "single call"

    h = stats["by_agent"].get(agent_id) or {}
    if h.get("llm"):
        llm_typ = int(h["llm"])
        if strat == "tool-loop" and h.get("tool"):
            tools_typ = int(h["tool"])
        basis += f"; history {h['llm']} llm" + (f"/{h.get('tool', 0)} tools" if h.get("tool") else "")
    else:
        llm_typ = base_typ

    est_min = round((llm_typ * ms) / 60000.0, 1)
    return {
        "agent": agent_id, "stage": stage_id, "strategy": strat, "model": model or "",
        "sections": sections, "features": feats,
        "llm_min": base_min, "llm_typical": llm_typ, "llm_max": base_max,
        "tools_typical": tools_typ, "tools_max": tools_max,
        "ms_per_call": ms, "est_minutes": est_min,
        "basis": basis,
    }


def estimate_all(project_dir: str, tier: str = "") -> Dict:
    """Estimate every pipeline agent (unique), grouped by stage."""
    stages = _rj(os.path.join(_root(), "pipeline-definition.json"), {}).get("stages") or {}
    agents: List[Dict] = []
    seen = set()
    tot_calls, tot_tools, tot_min = 0, 0, 0.0
    for sid, sdef in stages.items():
        for a in ((sdef or {}).get("ideal_flow") or []):
            if a in seen:
                continue
            seen.add(a)
            e = estimate_agent(project_dir, a, sid)
            agents.append(e)
            tot_calls += e["llm_typical"]
            tot_tools += e["tools_typical"]
            tot_min += e["est_minutes"]
    data = {"tier": tier, "generated_at": datetime.now().isoformat(),
            "agents": agents,
            "totals": {"agents": len(agents), "llm_typical": tot_calls,
                       "tools_typical": tot_tools, "est_minutes": round(tot_min, 1)}}
    save(project_dir, data)
    return data


def path(project_dir: str) -> str:
    return os.path.join(project_dir, FILENAME)


def save(project_dir: str, data: Dict) -> None:
    tmp = path(project_dir) + ".tmp"
    try:
        os.makedirs(project_dir, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path(project_dir))
    except Exception:
        pass


def load(project_dir: str) -> Dict:
    return _rj(path(project_dir), {})


def summary(project_dir: str) -> Dict:
    d = load(project_dir)
    if not d:
        d = estimate_all(project_dir)
    return {"generated_at": d.get("generated_at", ""), "totals": d.get("totals", {}),
            "agents": [{"agent": a.get("agent"), "stage": a.get("stage"),
                        "strategy": a.get("strategy"), "llm_typical": a.get("llm_typical"),
                        "tools_typical": a.get("tools_typical"),
                        "est_minutes": a.get("est_minutes")} for a in (d.get("agents") or [])]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Per-agent work estimate")
    ap.add_argument("--project", required=True)
    ap.add_argument("--products", default="products")
    a = ap.parse_args()
    print(json.dumps(summary(os.path.join(a.products, a.project)), indent=2, ensure_ascii=False))
