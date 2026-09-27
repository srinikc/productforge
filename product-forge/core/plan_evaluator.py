"""Post-discovery RUN PLAN evaluator.

Reads the ideation + discovery artifacts (what actually needs to be built) and, for
each optional-capability GROUP (config/plan-groups.json), recommends include/skip with
a plain-English reason + evidence. The user then confirms/extend via one HIL review.

This module is pure-ish (no store writes): it returns a plan dict. The persisted
products/<project>/run-plan.json is written by core/run_plan.py (single writer).

Also performs DEPENDENCY SAFETY: if skipping an optional stage would remove a declared
input of a non-skipped stage, it records a warning and (in strict mode) auto-includes it.
"""
import glob
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

DEFAULT_GROUPS_PATH_REL = ("config", "plan-groups.json")


def _root() -> str:
    try:
        from core.paths import ROOT
        return str(ROOT)
    except Exception:
        return "."


def _load_groups() -> List[Dict]:
    try:
        with open(os.path.join(_root(), *DEFAULT_GROUPS_PATH_REL), "r", encoding="utf-8-sig") as f:
            return (json.load(f) or {}).get("groups") or []
    except Exception:
        return []


def _stages() -> Dict:
    try:
        with open(os.path.join(_root(), "pipeline-definition.json"), "r", encoding="utf-8-sig") as f:
            return (json.load(f) or {}).get("stages") or {}
    except Exception:
        return {}


def _read(path: str, limit: int = 20000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()[:limit]
    except Exception:
        return ""


def discovery_ready(project_dir: str) -> bool:
    """True when a discovery (0a) output exists on disk."""
    try:
        for pat in ("artifacts/0a*/*-output.md", "artifacts/0a*/*.md",
                    "docs/agent-summaries/0a-*.md"):
            if glob.glob(os.path.join(project_dir, *pat.split("/"))):
                return True
    except Exception:
        pass
    return False


def gather_text(project_dir: str) -> Dict[str, str]:
    """Concatenate the requirement-bearing artifacts (idea + ideation + discovery)."""
    out = {"idea": "", "ideation": "", "discovery": ""}
    parts = []
    for p in (os.path.join(project_dir, "idea.md"), os.path.join(project_dir, "idea.txt")):
        if os.path.exists(p):
            out["idea"] = _read(p)
            break
    if not out["idea"]:
        try:
            with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
                out["idea"] = str((json.load(f) or {}).get("idea") or "")
        except Exception:
            pass
    for key, pat in (("ideation", "artifacts/0*/*ideation-output.md"),
                     ("discovery", "artifacts/0a*/*discovery-output.md")):
        for p in glob.glob(os.path.join(project_dir, *pat.split("/"))):
            out[key] += "\n" + _read(p)
    parts = [out["idea"], out["ideation"], out["discovery"]]
    out["all"] = "\n".join(parts)
    return out


def evaluate(project_dir: str) -> Dict:
    """Recommend include/skip per optional group from the requirement artifacts."""
    text = gather_text(project_dir)
    low = (text.get("all") or "").lower()
    dis_low = (text.get("discovery") or "").lower()
    id_low = (text.get("ideation") or "").lower()

    groups_out, skip_stages, include_stages, deps = [], [], [], []
    for g in _load_groups():
        hits = [s for s in (g.get("signals") or []) if s and s in low]
        hit_disc = [s for s in (g.get("signals") or []) if s in dis_low]
        hit_ide = [s for s in (g.get("signals") or []) if s in id_low]
        recommended = bool(hits) or bool(g.get("recommend_default"))
        if recommended:
            reason = ("Discovery/ideation mention: " + ", ".join(hits[:5])) if hits \
                else "recommended by default"
        else:
            reason = "no requirement signal found in discovery/ideation"
        evidence = (["discovery-output.md"] if hit_disc else []) + \
                   (["ideation-output.md"] if hit_ide else [])
        groups_out.append({
            "key": g.get("key"), "title": g.get("title"),
            "provides": g.get("provides"), "skip_impact": g.get("skip_impact"),
            "agents": g.get("agents") or [], "stages": g.get("stages") or [],
            "recommended": recommended, "reason": reason, "evidence": evidence or ["(default)"],
        })
        for sid in (g.get("stages") or []):
            if recommended:
                if sid not in include_stages:
                    include_stages.append(sid)
                if sid in skip_stages:
                    skip_stages.remove(sid)
            elif sid not in include_stages and sid not in skip_stages:
                skip_stages.append(sid)

    # Prerequisite closure: if an optional stage is included, include its optional
    # prerequisites too (e.g. 13a/13b need 13).
    stages = _stages()
    include_stages, skip_stages, prereq_notes = _close_prereqs(include_stages, skip_stages, stages)

    # Dependency safety: a skipped stage that is a declared input of a stage we WILL
    # run means the dependent loses its input.
    for sid in list(skip_stages):
        dependents = [d for d, sd in stages.items()
                      if sid in ((sd or {}).get("depends_on") or [])
                      and d not in skip_stages]
        if dependents:
            deps.append({"skipped": sid, "dependents": dependents})

    return {
        "kind": _classify(low),
        "groups": groups_out,
        "include_optional": include_stages,
        "skip_optional": skip_stages,
        "dependencies": deps,
        "warnings": prereq_notes,
        "generated_at": datetime.now().isoformat(),
    }


def _close_prereqs(include: List[str], skip: List[str], stages: Dict):
    inc, sk, notes = list(include), list(skip), []
    changed = True
    while changed:
        changed = False
        for sid in list(inc):
            for dep in ((stages.get(sid) or {}).get("depends_on") or []):
                if (stages.get(dep) or {}).get("optional") and dep in sk:
                    sk.remove(dep)
                    inc.append(dep)
                    notes.append(f"included optional prerequisite '{dep}' required by '{sid}'")
                    changed = True
    return inc, sk, notes


def _classify(low: str) -> str:
    for kind, kws in (("web_app", ("web app", "website", "dashboard", "portal")),
                      ("mobile_app", ("mobile app", "ios", "android")),
                      ("api", ("api", "microservice", "endpoint")),
                      ("cli", ("cli", "command line")),
                      ("library", ("library", "sdk")),
                      ("internal_tool", ("internal tool", "admin tool"))):
        if any(k in low for k in kws):
            return kind
    return "unknown"


def resolve(plan: Dict, strict: bool = False) -> Dict:
    """Finalize include/skip with dependency safety. strict => auto-include risky skips."""
    plan = dict(plan)
    resolved_skip = list(plan.get("skip_optional") or [])
    resolved_inc = list(plan.get("include_optional") or [])
    warnings = []
    for d in (plan.get("dependencies") or []):
        sid, deps = d.get("skipped"), d.get("dependents") or []
        msg = (f"skipping optional stage '{sid}' removes a declared input of "
               f"{deps}; those stages will run with reduced context")
        warnings.append(msg)
        if strict and sid in resolved_skip:
            resolved_skip.remove(sid)
            if sid not in resolved_inc:
                resolved_inc.append(sid)
            warnings.append(f"strict_deps: kept '{sid}' because {deps} depend on it")
    plan["skip_optional"] = resolved_skip
    plan["include_optional"] = resolved_inc
    plan["warnings"] = (plan.get("warnings") or []) + warnings
    return plan


def confirm(plan: Dict, project_dir: str, interactive_review=None) -> Dict:
    """Apply the user's selection (if any). `interactive_review(plan)->selection` returns
    the list of group keys to INCLUDE, or 'accept'/'all'/'none'."""
    plan = dict(plan)
    # persist a review file for the dashboard / offline editing
    try:
        with open(os.path.join(project_dir, "plan-review.json"), "w", encoding="utf-8") as f:
            json.dump({"generated_at": datetime.now().isoformat(), "groups": plan.get("groups", [])},
                      f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    if interactive_review is None:
        return plan
    try:
        sel = interactive_review(plan)
    except Exception:
        sel = None
    if sel in (None, "", "accept", "yes", "recommended"):
        return plan  # accept recommendations
    if str(sel).strip().lower() == "all":
        chosen = {g["key"] for g in plan.get("groups", [])}
    elif str(sel).strip().lower() == "none":
        chosen = set()
    else:
        chosen = {t.strip() for t in str(sel).split(",") if t.strip()}
    inc, skip = [], []
    for g in plan.get("groups", []):
        want = g["key"] in chosen
        g["chosen"] = want
        for sid in (g.get("stages") or []):
            if want:
                if sid not in inc:
                    inc.append(sid)
                if sid in skip:
                    skip.remove(sid)
            elif sid not in inc and sid not in skip:
                skip.append(sid)
    plan["include_optional"] = inc
    plan["skip_optional"] = skip
    return plan


def apply_to_dag(dag_executor, plan: Dict) -> List[str]:
    applied = []
    if not dag_executor:
        return applied
    for sid in (plan.get("skip_optional") or []):
        try:
            st = dag_executor.states.get(sid)
            if st is not None and st.status.value == "pending":
                dag_executor.mark_skipped(sid)
                applied.append(sid)
        except Exception:
            pass
    return applied


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Post-discovery run plan evaluator")
    ap.add_argument("--project", required=True)
    ap.add_argument("--products", default="products")
    a = ap.parse_args()
    pj = os.path.join(a.products, a.project)
    print(json.dumps(resolve(evaluate(pj)), indent=2, ensure_ascii=False))
