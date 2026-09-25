"""Pipeline tailoring (BI-0115): derive a per-project customized pipeline from the
common pipeline definition + a per-project `pipeline-plan.json`.

Rules (owner-approved):
  * Stage/agent IDS are STABLE KEYS and never change.
  * Customization changes only: (a) which OPTIONAL stages are enabled, (b) order
    (already derived from `depends_on`), (c) the DISPLAY numbering.
  * DISPLAY shows BOTH: a gap-free per-project sequence (S1.1, S1.2, S2.1...)
    AND the canonical phase/stage name + canonical S-id for traceability.
  * Optional stages are dropped unless the plan enables them (or a `needs` signal
    matches the idea). Required stages are always kept.

Owner store: products/<project>/pipeline-plan.json (single writer = this module).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

# Signals that turn an optional stage/phase ON from the idea/goal text.
DEFAULT_SIGNALS: Dict[str, List[str]] = {
    "0b": ["business", "product", "startup", "saas", "launch", "monetiz", "market", "customer", "revenue"],
    "0c": ["market", "competitor", "competition", "positioning", "saas", "launch", "go-to-market"],
    "0d": ["pricing", "revenue", "monetiz", "profit", "cost", "subscription", "freemium", "business model"],
    "0e": ["go-to-market", "gtm", "marketing", "launch", "onboard", "customer", "funnel"],
    "13": ["operate", "monitor", "sla", "maintenance", "production", "observability", "uptime"],
    "13a": ["support", "customer success", "onboard", "retention", "churn"],
    "13b": ["growth", "engage", "social", "community", "retention", "referral", "feedback"],
}


def _load(path: str) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def _idea_text(project_dir: str) -> str:
    from core import stage_paths as _sp
    rels = ["docs/idea-refined.md", "docs/product-plan.md",
            os.path.join(_sp.find_stage_dir(project_dir, "0"), "ideation-output.md"),
            os.path.join(_sp.find_stage_dir(project_dir, "0a"), "discovery-output.md")]
    for rel in rels:
        p = rel if os.path.isabs(rel) else os.path.join(project_dir, rel)
        if os.path.exists(p):
            try:
                return open(p, encoding="utf-8", errors="ignore").read().lower()
            except Exception:
                continue
    return ""


def recommend(pipeline_def: Dict, project_dir: str) -> Dict[str, Any]:
    """Recommend the enabled optional stages from the idea/goal (no AI call; signal-based).

    Returns {"enable": [...], "disable": [...], "reasons": {...}}.
    """
    stages = (pipeline_def or {}).get("stages", {}) or {}
    idea = _idea_text(project_dir)
    enable, disable, reasons = [], [], {}
    for sid, st in stages.items():
        if not st.get("optional"):
            continue
        sigs = DEFAULT_SIGNALS.get(sid, [])
        hit = [s for s in sigs if s in idea]
        if hit:
            enable.append(sid)
            reasons[sid] = f"matched idea signals: {', '.join(hit[:4])}"
        else:
            disable.append(sid)
            reasons[sid] = "no matching idea signals (optional)"
    return {"enable": sorted(enable), "disable": sorted(disable), "reasons": reasons}


def build_plan(pipeline_def: Dict, project_dir: str, enabled: Optional[List[str]] = None,
               disabled: Optional[List[str]] = None, actor: str = "pipeline") -> Dict[str, Any]:
    """Build (and write) a per-project pipeline-plan.json."""
    rec = recommend(pipeline_def, project_dir)
    stages = (pipeline_def or {}).get("stages", {}) or {}
    optional = [s for s, st in stages.items() if st.get("optional")]
    chosen = set(enabled if enabled is not None else rec["enable"])
    chosen -= set(disabled or [])
    # never disable a required stage
    plan = {
        "_doc": "Per-project customized pipeline (BI-0115). Ids are stable; only the enabled set + display numbering are project-specific. Owner: core/pipeline_tailoring.py.",
        "project": os.path.basename(project_dir.rstrip("/\\")),
        "generated_at": datetime.now().isoformat(),
        "generated_by": actor,
        "optional_stages": optional,
        "enabled_optional": sorted(chosen),
        "disabled_optional": sorted(s for s in optional if s not in chosen),
        "recommendation": rec,
    }
    plan["display"] = derive_display(stages, chosen)
    return plan


def derive_display(stages: Dict[str, Any], enabled_optional: set) -> Dict[str, Dict[str, str]]:
    """Gap-free per-project display ids + canonical ids for traceability."""
    out: Dict[str, Dict[str, str]] = {}
    phase_seen: Dict[str, int] = {}
    counters: Dict[str, int] = {}

    def _enabled(sid: str, st: Dict) -> bool:
        return (not st.get("optional")) or (sid in enabled_optional)

    for sid, st in stages.items():
        if not _enabled(sid, st):
            continue
        phase = st.get("phase") or "Unphased"
        if phase not in phase_seen:
            phase_seen[phase] = len(phase_seen) + 1
        pno = phase_seen[phase]
        counters.setdefault(phase, 0)
        counters[phase] += 1
        seq = f"S{pno}.{counters[phase]}"
        out[sid] = {
            "display_seq": seq,               # gap-free per-project
            "canonical_id": st.get("display_id") or "",   # canonical S-id
            "name": st.get("name") or sid,
            "phase": phase,
            "canonical": st.get("display_id") or sid,
        }
    return out


def apply_plan(pipeline_def: Dict, plan: Dict) -> Dict:
    """Return a COPY of pipeline_def with disabled optional stages removed (and downstream deps cleaned)."""
    import copy
    pd = copy.deepcopy(pipeline_def)
    stages = pd.get("stages", {}) or {}
    drop = set(plan.get("disabled_optional") or [])
    for sid in list(stages.keys()):
        if sid in drop:
            stages.pop(sid, None)
    # clean dangling depends_on references
    for sid, st in stages.items():
        deps = [d for d in (st.get("depends_on") or []) if d in stages]
        st["depends_on"] = deps
    pd["_tailored"] = {"enabled_optional": plan.get("enabled_optional"),
                       "disabled_optional": sorted(drop)}
    return pd


def plan_path(project_dir: str) -> str:
    return os.path.join(project_dir, "pipeline-plan.json")


def load_plan(project_dir: str) -> Optional[Dict]:
    return _load(plan_path(project_dir))


def save_plan(project_dir: str, plan: Dict) -> str:
    p = plan_path(project_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return p


def load_or_recommend(pipeline_def: Dict, project_dir: str) -> Dict:
    return load_plan(project_dir) or build_plan(pipeline_def, project_dir)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Pipeline tailoring (BI-0115)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--pipeline", default="pipeline-definition.json")
    ap.add_argument("--recommend", action="store_true")
    ap.add_argument("--build", action="store_true", help="write pipeline-plan.json")
    ap.add_argument("--enable", default="", help="comma list of optional stage ids to enable")
    ap.add_argument("--disable", default="", help="comma list of optional stage ids to disable")
    a = ap.parse_args()
    pd = _load(a.pipeline) or {}
    pdir = os.path.join("products", a.project)
    if a.recommend or not a.build:
        print(json.dumps(recommend(pd, pdir), indent=2))
    if a.build:
        en = [s.strip() for s in a.enable.split(",") if s.strip()] or None
        di = [s.strip() for s in a.disable.split(",") if s.strip()] or None
        plan = build_plan(pd, pdir, enabled=en, disabled=di, actor="owner")
        print("wrote", save_plan(pdir, plan))
