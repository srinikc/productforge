"""Model Capability Gate (PRE-run).

Validates every agent's assigned model against that agent's capability needs
(tools / reasoning / structured / min_output / min_context), using the live
capability catalog (core/model_catalog). Produces:
  * a per-agent verdict: OK | UNKNOWN | INCOMPATIBLE (+ reasons)
  * a RECOMMENDED substitute model that fits (never auto-applied)
  * a report: products/<project>/model-gate.json

Complements model_fit (which probes liveness); this gate is capability-based and
works offline from the refreshed catalog. Config: config/agent-requirements.json -> "capabilities".
"""
import json
import os
from datetime import datetime
from typing import Dict, List

FILENAME = "model-gate.json"


def _cfg() -> Dict:
    try:
        from core.paths import ROOT
        p = os.path.join(str(ROOT), "config", "agent-requirements.json")
    except Exception:
        p = os.path.join("config", "agent-requirements.json")
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def needs_for(agent_id: str) -> Dict:
    c = (_cfg().get("capabilities") or {})
    n = dict(c.get("default") or {})
    n.update(c.get(agent_id) or {})
    # BI-0221/BI-0222: the per-agent capability vector drives the gate needs.
    try:
        from core import agent_capabilities as _ac
        v = _ac.vector(agent_id)
        for k in ("needs_reasoning", "needs_structured", "needs_tools", "needs_vision",
                  "min_output", "min_context"):
            if k in v:
                n[k] = v[k]
    except Exception:
        pass
    return n


def _fit_needs(needs: Dict) -> Dict:
    return {
        "tools": bool(needs.get("needs_tools")),
        "reasoning": bool(needs.get("needs_reasoning")),
        "structured_outputs": bool(needs.get("needs_structured")),
        "min_output": int(needs.get("min_output", 0) or 0),
        "min_context": int(needs.get("min_context", 0) or 0),
    }


def evaluate(profile: Dict) -> Dict:
    """tier profile dict -> gate report (no side effects)."""
    from core import model_catalog
    agents = (profile.get("agents") or {})
    default = profile.get("default_model") or ""
    pool: List[str] = []
    for a, cfg in agents.items():
        m = (cfg or {}).get("model")
        if m and m not in pool:
            pool.append(m)
    if default and default not in pool:
        pool.append(default)

    entries, blocked = [], []
    for agent, cfg in sorted(agents.items()):
        model = ((cfg or {}).get("model") or default or "")
        needs = needs_for(agent)
        fn = _fit_needs(needs)
        res = model_catalog.fit(model, fn) if model else {"ok": None, "reasons": ["no model assigned"]}
        status = "OK" if res.get("ok") else ("UNKNOWN" if res.get("ok") is None else "INCOMPATIBLE")
        # Policy eligibility (BI-PF-0278): restricted/over-budget/unmet-quality => POLICY_BLOCKED.
        pol = {"ok": True, "policy_found": False, "reasons": [], "fallback": [], "independent_review": False}
        try:
            from core import model_policy
            task = str((cfg or {}).get("task") or "")
            crit = bool((cfg or {}).get("critical")) or bool(needs.get("needs_reasoning"))
            pol = model_policy.eligible(model, task, critical=crit) if model else pol
        except Exception:
            pass
        if not pol.get("ok"):
            status = "POLICY_BLOCKED"
        rec = ""
        if status != "OK":
            # prefer the policy's declared fallback, then any capability-fitting pool model
            for cand in list(pol.get("fallback") or []) + pool:
                if cand == model:
                    continue
                if model_catalog.fit(cand, fn).get("ok"):
                    rec = cand
                    break
        reasons = list(res.get("reasons", [])) + list(pol.get("reasons") or [])
        entries.append({"agent": agent, "model": model, "status": status,
                        "reasons": reasons, "recommended": rec,
                        "independent_review": bool(pol.get("independent_review", False)),
                        "policy_found": bool(pol.get("policy_found", False)),
                        "needs": {k: needs.get(k) for k in ("needs_tools", "needs_reasoning",
                                                            "min_output", "min_context")}})
        if status in ("INCOMPATIBLE", "POLICY_BLOCKED"):
            blocked.append(agent)

    # PF-017: make UNKNOWN explicit, and flag capability-critical agents (tools /
    # reasoning) whose fit is UNKNOWN for confirmation instead of silent pass.
    _unknown = [e["agent"] for e in entries if e["status"] == "UNKNOWN"]
    _confirm = [e["agent"] for e in entries if e["status"] == "UNKNOWN"
                and any(e["needs"].get(k) for k in ("needs_tools", "needs_reasoning"))]

    # BI-PF-0246: fail closed on unknown capability for capability-critical agents unless
    # explicitly overridden (MODEL_GATE_REJECT_UNKNOWN=0).
    _reject = _confirm if os.getenv("MODEL_GATE_REJECT_UNKNOWN", "1").strip().lower() not in (
        "0", "false", "no", "off") else []
    blocked_all = sorted(set(blocked) | set(_reject))

    summary = {
        "total": len(entries),
        "ok": sum(1 for e in entries if e["status"] == "OK"),
        "unknown": sum(1 for e in entries if e["status"] == "UNKNOWN"),
        "incompatible": len(blocked),
        "policy_blocked": sum(1 for e in entries if e["status"] == "POLICY_BLOCKED"),
        "blocked_agents": blocked_all,
        "unknown_agents": _unknown,
        "needs_confirmation": _confirm,
        "rejected_unknown": _reject,
        "catalog_last_refreshed": model_catalog.last_refreshed(),
    }
    return {"tier": profile.get("default_tier", ""),
            "generated_at": datetime.now().isoformat(),
            "entries": entries, "summary": summary}


def report_path(project_dir: str) -> str:
    return os.path.join(project_dir, FILENAME)


def save_report(project_dir: str, report: Dict) -> None:
    tmp = report_path(project_dir) + ".tmp"
    try:
        os.makedirs(os.path.dirname(report_path(project_dir)), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        os.replace(tmp, report_path(project_dir))
    except Exception:
        pass


def load_report(project_dir: str) -> Dict:
    try:
        with open(report_path(project_dir), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def run(executor) -> Dict:
    """Evaluate the executor's active tier; save the report. Returns the report."""
    try:
        prof = executor.model_router.active_profile() or executor.model_router.load_tier_config()
    except Exception as e:
        return {"error": str(e)}
    rep = evaluate(prof or {})
    try:
        if getattr(executor, "project_dir", ""):
            save_report(executor.project_dir, rep)
    except Exception:
        pass
    return rep


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Model capability gate")
    ap.add_argument("--project", default="")
    ap.add_argument("--products", default="products")
    a = ap.parse_args()
    if a.project:
        print(json.dumps(load_report(os.path.join(a.products, a.project)), indent=2, ensure_ascii=False))
    else:
        print("use via pipeline preflight or --project <name>")
