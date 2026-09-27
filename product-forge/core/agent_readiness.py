"""Agent readiness checklist (PRE-execution).

Distinct from compliance (which is POST-execution). Before an agent runs we verify
it actually has what it needs: required upstream inputs, a usable context, an
assigned model, and a resolvable provider key. Must-have failures BLOCK the agent
(and emit an event + issue + notification); warnings are surfaced but do not block.

Store: products/<project>/readiness.json (kind=derived, scope=project).
Owner: this module (single writer). Config: config/agent-requirements.json -> "readiness".
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

FILENAME = "readiness.json"

_DEFAULT = {
    "required_inputs": [],       # substrings that MUST appear in the collected context keys
    "min_context_chars": 0,      # below this = warn (thin context)
    "require_model": True,       # no model assigned = fail
    "require_provider_key": True,  # provider key missing = warn (fallbacks may still work)
}


def _cfg_path() -> str:
    try:
        from core.paths import ROOT
        return os.path.join(str(ROOT), "config", "agent-requirements.json")
    except Exception:
        return os.path.join("config", "agent-requirements.json")


def _load_cfg() -> Dict:
    try:
        with open(_cfg_path(), "r", encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def spec(agent_id: str, stage_id: str = "") -> Dict:
    """Merge default <- agent <- agent@stage (most specific wins)."""
    r = (_load_cfg().get("readiness") or {})
    out = dict(_DEFAULT)
    out.update(r.get("default") or {})
    out.update(r.get(agent_id) or {})
    if stage_id:
        out.update(r.get(f"{agent_id}@{stage_id}") or {})
    return out


def _dag_required(stage_id: str) -> List[str]:
    """Required upstream inputs = the stage's NON-optional declared dependencies.
    (Robust: never hand-code a dependency the DAG doesn't declare.)"""
    if not stage_id:
        return []
    try:
        from core.paths import ROOT
        with open(os.path.join(str(ROOT), "pipeline-definition.json"), "r",
                  encoding="utf-8-sig") as f:
            stages = (json.load(f) or {}).get("stages") or {}
        deps = (stages.get(stage_id) or {}).get("depends_on") or []
        return [d for d in deps if not (stages.get(d) or {}).get("optional")]
    except Exception:
        return []


def evaluate(agent_id: str, *, stage_id: str = "", available_keys: Optional[List[str]] = None,
             context_chars: int = 0, model: str = "", provider: str = "") -> Dict:
    """Return {ok, checks:[{name,status,detail}], missing, ...}. status: ok|warn|fail."""
    s = spec(agent_id, stage_id)
    keys = [str(k) for k in (available_keys or [])]
    checks: List[Dict[str, Any]] = []

    required = [str(x) for x in (s.get("required_inputs") or []) if str(x).strip()]
    if not required:
        required = _dag_required(stage_id)
    missing = [m for m in required if not any(m in k for k in keys)]
    checks.append({
        "name": "required_inputs",
        "status": "fail" if missing else "ok",
        "detail": ("missing required inputs: " + ", ".join(missing)) if missing
                  else f"all required inputs present ({len(required)})",
        "required": required, "available": keys[:40],
    })

    min_chars = int(s.get("min_context_chars", 0) or 0)
    thin = bool(min_chars and context_chars < min_chars)
    checks.append({
        "name": "context_size",
        "status": "warn" if thin else "ok",
        "detail": (f"thin context: {context_chars} chars < {min_chars}") if thin
                  else f"context {context_chars} chars",
    })

    if s.get("require_model", True):
        checks.append({
            "name": "model_assigned",
            "status": "ok" if (model or "").strip() else "fail",
            "detail": f"model={model or '(none)'}",
        })

    if s.get("require_provider_key", True) and provider:
        try:
            from core import credentials
            has = credentials.has(provider)
        except Exception:
            has = True  # cannot verify -> do not block
        checks.append({
            "name": "provider_key",
            "status": "ok" if has else "warn",
            "detail": f"provider={provider} key={'present' if has else 'MISSING'}",
        })

    ok = not any(c["status"] == "fail" for c in checks)
    return {"ok": ok, "checks": checks, "missing": missing,
            "context_chars": context_chars, "model": model, "provider": provider}


def report_path(project_dir: str) -> str:
    return os.path.join(project_dir, FILENAME)


def record(project_dir: str, *, run_id: str = "", stage: str = "", agent: str = "",
           verdict: Dict) -> None:
    """Upsert one agent's readiness verdict into readiness.json (atomic)."""
    path = report_path(project_dir)
    data = load_report(project_dir) or {"project": os.path.basename(project_dir.rstrip("/\\")),
                                        "agents": []}
    entry = {
        "stage": stage, "agent": agent, "run_id": run_id,
        "ok": bool(verdict.get("ok")),
        "model": verdict.get("model", ""), "provider": verdict.get("provider", ""),
        "context_chars": verdict.get("context_chars", 0),
        "checks": verdict.get("checks", []),
        "at": datetime.now().isoformat(),
    }
    agents = [a for a in (data.get("agents") or [])
              if not (a.get("stage") == stage and a.get("agent") == agent)]
    agents.append(entry)
    data["agents"] = agents
    data["run_id"] = run_id
    data["updated_at"] = datetime.now().isoformat()
    tmp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def load_report(project_dir: str) -> Optional[Dict]:
    try:
        with open(report_path(project_dir), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def summary(project_dir: str) -> Dict:
    """Counts for dashboards/alarms."""
    rep = load_report(project_dir) or {}
    agents = rep.get("agents") or []
    return {
        "total": len(agents),
        "ready": sum(1 for a in agents if a.get("ok")),
        "blocked": sum(1 for a in agents if not a.get("ok")),
        "blocked_agents": [f"{a.get('stage')}:{a.get('agent')}" for a in agents if not a.get("ok")],
        "updated_at": rep.get("updated_at", ""),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Agent readiness checklist (pre-execution)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--products", default="products")
    a = ap.parse_args()
    pj = os.path.join(a.products, a.project)
    print(json.dumps({"summary": summary(pj), "report": load_report(pj)}, indent=2, ensure_ascii=False))
