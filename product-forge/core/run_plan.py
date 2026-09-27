"""Idea-based dynamic RUN PLAN.

Classifies the product from the idea/brief and decides which of the pipeline's
OPTIONAL stages to include (0b-0e business, 13/13a/13b operate). Optional stages are
declared in pipeline-definition.json; non-optional stages are always included.

Recommended + overridable: the plan is written to products/<project>/run-plan.json.
By default (mode=auto) the skip set is applied; set project.json
`"run_plan": {"mode": "recommend"}` to only recommend, or provide `include`/`exclude`
lists to force stages. Skipped stages do not block dependents (DAG treats skipped as
satisfied).
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, List

FILENAME = "run-plan.json"

BUSINESS_STAGES = ["0b", "0c", "0d", "0e"]
OPERATE_STAGES = ["13", "13a", "13b"]

_NONCOMMERCIAL = ("internal tool", "internal app", "cli", "command line", "library",
                  "sdk", "plugin", "script", "automation", "devtool", "developer tool",
                  "data pipeline", "etl", "batch job", "utility")
_COMMERCE = ("business", "market", "competitor", "competition", "pricing", "revenue",
             "monetiz", "monetis", "customer", "launch", "go-to-market", "gtm", "growth",
             "unit economics", "saas", "subscription", "freemium", "b2b", "b2c", "startup")
_OPS = ("production", "deploy", "monitor", "observab", "sla", "support", "scale",
        "retention", "engagement", "uptime", "incident")
_KIND = {
    "web_app": ("web app", "website", "web application", "dashboard", "portal", "spa"),
    "mobile_app": ("mobile app", "ios", "android", "react native", "flutter"),
    "api": ("api", "rest", "graphql", "microservice", "backend service", "endpoint"),
    "saas": ("saas", "subscription", "multi-tenant", "b2b product"),
    "cli": ("cli", "command line", "terminal"),
    "library": ("library", "sdk", "package", "framework", "plugin"),
    "data_pipeline": ("etl", "data pipeline", "batch job", "ingest"),
    "content": ("blog", "content site", "newsletter", "media"),
    "internal_tool": ("internal tool", "internal app", "admin tool", "devtool"),
}


def _pipeline_path() -> str:
    try:
        from core.paths import ROOT
        return os.path.join(str(ROOT), "pipeline-definition.json")
    except Exception:
        return "pipeline-definition.json"


def _stages() -> Dict:
    try:
        with open(_pipeline_path(), "r", encoding="utf-8-sig") as f:
            return (json.load(f) or {}).get("stages") or {}
    except Exception:
        return {}


def classify(idea: str) -> str:
    t = (idea or "").lower()
    for kind, kws in _KIND.items():
        if any(k in t for k in kws):
            return kind
    return "unknown"


def decide(idea: str) -> Dict:
    t = (idea or "").lower()
    stages = _stages()
    optional = [sid for sid, s in stages.items() if (s or {}).get("optional")]
    noncomm = any(k in t for k in _NONCOMMERCIAL)
    commerce = any(k in t for k in _COMMERCE)
    ops = any(k in t for k in _OPS)
    kind = classify(idea)

    include_business = (not noncomm) or commerce
    include_operate = (ops or commerce) and kind not in ("cli", "library", "data_pipeline",
                                                         "internal_tool")

    include, skip, why = [], [], []
    for sid in BUSINESS_STAGES:
        (include if include_business else skip).append(sid)
    why.append(f"{'include' if include_business else 'skip'} business stages "
               f"(commerce={commerce}, noncommercial={noncomm})")
    for sid in OPERATE_STAGES:
        (include if include_operate else skip).append(sid)
    why.append(f"{'include' if include_operate else 'skip'} operate stages (ops={ops})")

    # Only touch stages that are actually optional in the DAG.
    include = [s for s in include if s in optional]
    skip = [s for s in skip if s in optional]
    return {"kind": kind, "include_optional": include, "skip_optional": skip,
            "rationale": why, "optional_stages": optional}


def _overrides(project_dir: str) -> Dict:
    try:
        with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
            return ((json.load(f) or {}).get("run_plan") or {})
    except Exception:
        return {}


def generate(project_dir: str, project: str = "") -> Dict:
    idea = ""
    for p in (os.path.join(project_dir, "idea.md"), os.path.join(project_dir, "idea.txt")):
        try:
            if os.path.exists(p):
                idea = open(p, encoding="utf-8", errors="ignore").read()[:6000]
                break
        except Exception:
            pass
    if not idea:
        try:
            with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
                idea = str((json.load(f) or {}).get("idea") or "")
        except Exception:
            idea = ""
    plan = decide(idea)
    ov = _overrides(project_dir)
    mode = str(ov.get("mode") or os.getenv("PIPELINE_RUN_PLAN", "auto")).lower()
    if ov.get("include"):
        plan["include_optional"] = sorted(set(plan["include_optional"]) | set(ov["include"]))
        plan["skip_optional"] = [s for s in plan["skip_optional"] if s not in ov["include"]]
    if ov.get("exclude"):
        plan["skip_optional"] = sorted(set(plan["skip_optional"]) | set(ov["exclude"]))
        plan["include_optional"] = [s for s in plan["include_optional"] if s not in ov["exclude"]]
    plan.update({"project": project or os.path.basename(project_dir.rstrip("/\\")),
                 "mode": mode, "generated_at": datetime.now().isoformat()})
    save(project_dir, plan)
    return plan


def save(project_dir: str, plan: Dict) -> None:
    path = os.path.join(project_dir, FILENAME)
    tmp = path + ".tmp"
    try:
        os.makedirs(project_dir, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def load(project_dir: str) -> Dict:
    try:
        with open(os.path.join(project_dir, FILENAME), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _mode(project_dir: str) -> str:
    try:
        with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
            m = ((json.load(f) or {}).get("run_plan") or {}).get("mode")
    except Exception:
        m = None
    return str(m or os.getenv("PIPELINE_RUN_PLAN", "auto")).lower()


def _strict(project_dir: str) -> bool:
    try:
        with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
            s = ((json.load(f) or {}).get("run_plan") or {}).get("strict_deps")
        if s is not None:
            return bool(s)
    except Exception:
        pass
    return str(os.getenv("PIPELINE_RUN_PLAN_STRICT", "0")).lower() in ("1", "true", "yes")


def _interactive_review(plan: Dict):
    """One consolidated HIL question: which optional groups to include."""
    try:
        from core import interactive
        if not interactive.enabled():
            return None
        keys = [g["key"] for g in plan.get("groups", [])]
        lines = ["Include which optional capability groups? Reply with comma-separated keys,",
                 "or 'accept' (recommended), 'all', or 'none'."]
        for g in plan.get("groups", []):
            rec = "INCLUDE" if g.get("recommended") else "skip"
            lines.append(f"  [{g['key']}] {g['title']} - recommended: {rec} ({g.get('reason')})")
            lines.append(f"      get: {g.get('provides')}")
            lines.append(f"      if skipped: {g.get('skip_impact')}")
        ans = interactive.ask("\n".join(lines), default="accept",
                              options=keys + ["accept", "all", "none"], kind="plan",
                              timeout=float(os.getenv("PLAN_REVIEW_TIMEOUT", "300")))
        return ans or "accept"
    except Exception:
        return None


def ensure_plan(project_dir: str, project: str = "", force: bool = False,
                interactive_review=None) -> Dict:
    """Return the confirmed run plan. Defers (returns {}) until discovery exists,
    unless force=True. Never re-plans a confirmed plan (resume-safe)."""
    existing = load(project_dir)
    if existing and existing.get("confirmed"):
        return existing
    from core import plan_evaluator as _pe
    if not force and not _pe.discovery_ready(project_dir):
        return existing or {}
    plan = _pe.evaluate(project_dir)
    review = interactive_review if interactive_review is not None else _interactive_review
    plan = _pe.confirm(plan, project_dir, interactive_review=review)
    plan = _pe.resolve(plan, strict=_strict(project_dir))
    plan.update({"project": project or os.path.basename(project_dir.rstrip("/\\")),
                 "mode": _mode(project_dir), "confirmed": True})
    save(project_dir, plan)
    return plan


def apply_to_dag(dag_executor, plan: Dict) -> List[str]:
    """Mark the plan's skipped optional stages as SKIPPED (never blocks dependents)."""
    applied = []
    if not dag_executor:
        return applied
    for sid in (plan.get("skip_optional") or []):
        try:
            st = dag_executor.states.get(sid)
            if st is not None and getattr(st, "status", None) is not None \
                    and st.status.value == "pending":
                dag_executor.mark_skipped(sid)
                applied.append(sid)
        except Exception:
            pass
    return applied


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Idea-based run plan")
    ap.add_argument("--project", default="")
    ap.add_argument("--products", default="products")
    a = ap.parse_args()
    pj = os.path.join(a.products, a.project) if a.project else "."
    print(json.dumps(ensure_plan(pj, a.project), indent=2, ensure_ascii=False))
