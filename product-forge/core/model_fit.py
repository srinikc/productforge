"""Model capability fit — preflight reconcile of tier models with agent requirements.

Single concern: before a run, probe every model the SELECTED TIER uses with a tiny
task, check each against the requirements of the agents that use it, and report
OK / AT_RISK / INCOMPATIBLE with a recommended action. The recommendation is
applied by default if the human does not answer in time.

This closes the class of failures where a model returns empty/reasoning-only
content (BI-0075) or is unsuited to an agent (e.g. no artifact output).

Owner store (single writer = this module):
  ``products/<project>/model-fit.json``  — kind=derived, scope=project

Design notes:
- The probe is injected as ``probe_fn(model_name, provider, api_endpoint) -> dict``
  so this module has no LLM dependency and is testable offline.
- No import-time side effects.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

PANEL_FILENAME = "model-fit.json"

# Per-agent requirements. `artifact_output` = the agent must produce real content
# (not reasoning-only); `min_chars` = minimal acceptable content length.
DEFAULT_REQUIREMENT: Dict[str, Any] = {
    "artifact_output": True,
    "no_reasoning_only": True,
    "min_output_tokens": 2000,
    "min_chars": 200,
}

AGENT_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "ideation": {"min_output_tokens": 4000, "min_chars": 800},
    "discovery": {"min_output_tokens": 8000, "min_chars": 1500},
    "design": {"min_output_tokens": 16000, "min_chars": 3000},
    "architect": {"min_output_tokens": 10000, "min_chars": 3000},
    "product-design-spec": {"min_output_tokens": 8000, "min_chars": 1500},
    "ux-ia": {"min_output_tokens": 8000, "min_chars": 1200},
    "implement": {"min_output_tokens": 16000, "min_chars": 1200},
    "validate": {"min_output_tokens": 12000, "min_chars": 800},
    "code-review": {"min_output_tokens": 8000, "min_chars": 800},
    "security": {"min_output_tokens": 8000, "min_chars": 800},
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "probe": True,
    # Generous enough for reasoning-style models to finish thinking AND emit the
    # final content (a tiny budget yields reasoning-only / empty content).
    "probe_max_tokens": 700,
    "answer_timeout_seconds": 300,
    "apply_recommendation_by_default": True,
}

STATUS_OK = "OK"
STATUS_AT_RISK = "AT_RISK"
STATUS_INCOMPATIBLE = "INCOMPATIBLE"


def _rj(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _wj(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def requirement_for(agent_id: str) -> Dict[str, Any]:
    req = dict(DEFAULT_REQUIREMENT)
    req.update(AGENT_REQUIREMENTS.get(agent_id, {}))
    return req


def tier_specs(tier_cfg: Dict) -> Dict[str, Dict[str, Any]]:
    """From a resolved tier config -> {model_name: {provider, api_endpoint, agents[]}}."""
    agents = (tier_cfg or {}).get("agents") or {}
    models_catalog = (tier_cfg or {}).get("models") or {}
    default_provider = (tier_cfg or {}).get("provider", "")
    default_endpoint = (tier_cfg or {}).get("api_endpoint", "")

    specs: Dict[str, Dict[str, Any]] = {}
    for agent_id, acfg in agents.items():
        model = (acfg or {}).get("model") if isinstance(acfg, dict) else None
        if not model:
            continue
        cat = models_catalog.get(model) or {}
        spec = specs.setdefault(model, {
            "model": model,
            "provider": cat.get("provider", default_provider),
            "api_endpoint": cat.get("api_endpoint", default_endpoint),
            "agents": [],
        })
        spec["agents"].append(agent_id)
    return specs


def probe_one(probe_fn: Callable, spec: Dict[str, Any], max_tokens: int = 64) -> Dict[str, Any]:
    """Run the injected probe for one model. Never raises."""
    if probe_fn is None:
        return {"ok": None, "skipped": True}
    try:
        res = probe_fn(spec["model"], spec.get("provider", ""), spec.get("api_endpoint", ""),
                       max_tokens) or {}
        return res
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _status_for(agent_id: str, probe: Dict[str, Any]) -> Dict[str, Any]:
    """Given a probe result, decide status + reason for one agent's requirements."""
    req = requirement_for(agent_id)

    if probe.get("skipped"):
        return {"status": "UNKNOWN", "reason": "probe skipped (offline)"}
    if not probe.get("ok", False):
        return {"status": STATUS_INCOMPATIBLE,
                "reason": f"probe failed: {probe.get('error', 'no response')}"}

    content_len = int(probe.get("content_len", 0) or 0)
    reasoning_only = bool(probe.get("reasoning_only", False))

    if content_len == 0:
        return {"status": STATUS_INCOMPATIBLE,
                "reason": ("empty content"
                           + (" (reasoning-only output)" if reasoning_only else ""))}
    if reasoning_only and req.get("no_reasoning_only", True):
        return {"status": STATUS_AT_RISK, "reason": "model returns reasoning as output"}
    # The probe expects a short fixed sentence; only an implausibly short reply
    # (near-empty) is a risk. Do NOT compare against agent min_chars here.
    if content_len < 8:
        return {"status": STATUS_AT_RISK, "reason": f"near-empty output ({content_len} chars)"}
    return {"status": STATUS_OK, "reason": "content produced"}


def evaluate(specs: Dict[str, Dict[str, Any]], probes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Build the per-agent compatibility report with a recommended action."""
    entries: List[Dict[str, Any]] = []
    # Rank candidate models within the tier for substitution (OK first, content length).
    def _score(model: str) -> tuple:
        p = probes.get(model, {})
        return (1 if p.get("ok") else 0, int(p.get("content_len", 0) or 0),
                0 if p.get("reasoning_only") else 1)

    ranked = sorted(specs.keys(), key=_score, reverse=True)

    for model, spec in specs.items():
        probe = probes.get(model, {})
        for agent_id in spec.get("agents", []):
            verdict = _status_for(agent_id, probe)
            action = {"kind": "keep", "model": model}
            if verdict["status"] != STATUS_OK and ranked:
                best = ranked[0]
                if best != model and probes.get(best, {}).get("ok"):
                    action = {"kind": "substitute", "model": best}
                else:
                    action = {"kind": "review", "model": model}
            entries.append({
                "agent": agent_id,
                "model": model,
                "provider": spec.get("provider", ""),
                "status": verdict["status"],
                "reason": verdict["reason"],
                "recommended_action": action,
            })

    bad = [e for e in entries if e["status"] == STATUS_INCOMPATIBLE]
    risk = [e for e in entries if e["status"] == STATUS_AT_RISK]
    return {
        "generated_at": datetime.now().isoformat(),
        "entries": entries,
        "summary": {
            "agents": len(entries),
            "ok": len(entries) - len(bad) - len(risk),
            "at_risk": len(risk),
            "incompatible": len(bad),
            "healthy": not bad and not risk,
        },
    }


def apply_state(report: Dict[str, Any], answer: Optional[str] = None) -> Dict[str, Any]:
    """Record the human decision; default = apply the recommendation (auto-continue)."""
    applied: Dict[str, Dict[str, Any]] = {}
    for e in report.get("entries", []):
        if e["status"] == STATUS_OK:
            continue
        act = e.get("recommended_action") or {}
        # answer == "keep" -> keep the model; anything else ("", None, "apply") -> apply rec.
        if (answer or "").strip().lower() == "keep":
            applied[e["agent"]] = {"model": e["model"], "source": "human-keep"}
        elif act.get("kind") == "substitute":
            applied[e["agent"]] = {"model": act["model"], "source": "recommended"}
        else:
            applied[e["agent"]] = {"model": e["model"], "source": "review-kept"}
    report["applied"] = applied
    report["decision"] = "keep" if (answer or "").strip().lower() == "keep" else "apply-recommendation"
    report["decided_at"] = datetime.now().isoformat()
    return report


def report_path(project_dir: str) -> str:
    return os.path.join(project_dir, PANEL_FILENAME)


def save_report(project_dir: str, report: Dict) -> str:
    p = report_path(project_dir)
    _wj(p, report)
    return p


def load_report(project_dir: str) -> Optional[Dict]:
    d = _rj(report_path(project_dir), None)
    return d if isinstance(d, dict) else None


def run(tier_cfg: Dict, probe_fn: Optional[Callable], config: Optional[Dict] = None) -> Dict:
    """Full preflight: probe every model in the tier and produce the report."""
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    specs = tier_specs(tier_cfg)
    probes: Dict[str, Dict[str, Any]] = {}
    if cfg.get("probe", True):
        for model, spec in specs.items():
            probes[model] = probe_one(probe_fn, spec, int(cfg.get("probe_max_tokens", 64)))
    report = evaluate(specs, probes)
    report["probes"] = probes
    report["config"] = {"probe": cfg.get("probe", True)}

    # Catalog enrichment: attach REAL per-model capabilities (context, max_output, tools,
    # reasoning, structured_outputs, modality) + a reasoned per-agent fit (core/model_catalog).
    try:
        import glob as _glob
        import json as _json
        import os as _os
        from core import model_catalog as _mc
        _repo = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        agent_tools = {}
        for f in _glob.glob(_os.path.join(_repo, "agents", "*.agent.json")):
            try:
                d = _json.load(open(f, encoding="utf-8"))
                aid = d.get("id") or _os.path.basename(f).replace(".agent.json", "")
                agent_tools[aid] = bool(d.get("tools"))
            except Exception:
                pass
        needs_cfg = cfg.get("agents") or {}
        for e in report.get("entries", []):
            m = e.get("model")
            a = e.get("agent")
            c = _mc.capabilities(m) or {}
            e["capabilities"] = {k: c.get(k) for k in
                                 ("context_window", "max_output", "tools", "reasoning",
                                  "structured_outputs", "input_modalities", "provider")}
            req = needs_cfg.get(a) or {}
            needs = {"tools": agent_tools.get(a, False),
                     "min_output": req.get("min_output_tokens"),
                     "min_context": req.get("min_context_tokens")}
            fit = _mc.fit(m, needs)
            e["catalog_fit"] = fit.get("ok")
            e["catalog_reasons"] = fit.get("reasons")
    except Exception:
        pass
    return report
