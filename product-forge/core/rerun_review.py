"""Rerun review (GENERAL - any restart / stage re-run / agent re-run).

Single concern: on ANY rerun (restart, --from-stage, --only-stage, --agent, dashboard
"re-run"), produce ONE review package that:
  1. SHOWS what already exists (brief + inputs + artifacts for the affected scope),
  2. RECOMMENDS what should change (tailoring plan, recommended packs, model-fit,
     stale artifacts to regenerate),
  3. ASKS the operator to continue / accept / reject.
Used by BOTH the CLI and the dashboard (API-first) so behaviour is identical.

Owner store: products/<project>/rerun-review.json (last review) - derived.
"""
from __future__ import annotations
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

import json, os
from datetime import datetime
from typing import Any, Dict, List, Optional

REPO = str(_PF_ROOT)


def _load(path: str, default):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _artifacts_present(project_dir: str, stages: Optional[List[str]] = None) -> Dict[str, int]:
    out: Dict[str, int] = {}
    from core import stage_paths as _sp
    base = _sp.artifacts_root(project_dir)
    if not os.path.isdir(base):
        return out
    for d in sorted(os.listdir(base)):
        sid = _sp._sid_from_dirname(d) or d
        if stages and sid not in stages:
            continue
        p = os.path.join(base, d)
        if os.path.isdir(p):
            out[d] = len([f for f in os.listdir(p) if f.endswith(".md")])
    return out


def build(project_dir: str, project: str, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assemble the review package for a rerun. scope: {from_stage, only_stages, agents}."""
    scope = scope or {}
    project_dir = project_dir or os.path.join("products", project)
    cfg = _load(os.path.join(project_dir, "project.json"), {})
    brief = (cfg.get("idea") or cfg.get("description") or "").strip()

    review: Dict[str, Any] = {
        "project": project, "generated_at": datetime.now().isoformat(),
        "scope": scope, "existing": {}, "recommends": [], "questions": [],
    }
    # 1) SHOW what exists
    review["existing"] = {
        "brief": brief,
        "has_state": os.path.exists(os.path.join(project_dir, "pipeline-state.json")),
        "artifacts": _artifacts_present(project_dir, scope.get("only_stages")),
    }
    # 2) RECOMMEND changes (each guarded; all best-effort)
    recs: List[Dict[str, str]] = []
    try:
        from core import pipeline_tailoring as pt
        pd = _load(os.path.join(REPO, "pipeline-definition.json"), {})
        plan = pt.recommend(pd, project_dir)
        recs.append({"kind": "tailoring",
                     "detail": f"enable {plan.get('enable') or '[]'}; skip {plan.get('disable') or '[]'}"})
    except Exception:
        pass
    try:
        from core.integration_advisor import recommend as _irec, choices_recommended, _LABEL
        ir = _irec(project_dir, project)
        on = [_LABEL.get(n, n) for n, v in choices_recommended(ir).items() if v]
        recs.append({"kind": "packs", "detail": "; ".join(on) or "none"})
    except Exception:
        pass
    try:
        from core import model_fit
        rep = model_fit.load_report(project_dir)
        if rep:
            recs.append({"kind": "model-fit",
                         "detail": f"{sum(1 for e in rep.get('entries', []) if e.get('status') == 'at-risk')} at-risk"})
    except Exception:
        pass
    recs.append({"kind": "stale-artifacts",
                 "detail": "prior outputs for the rerun scope are cleared so they regenerate"})
    review["recommends"] = recs

    # 3) ASK - what the operator must decide
    review["questions"] = [
        {"id": "rerun-confirm",
         "text": "Proceed with the rerun? Existing inputs above will be reused; recommendations applied unless rejected.",
         "options": ["continue", "accept-recommendations", "reject"]},
    ]
    # persist (derived)
    try:
        with open(os.path.join(project_dir, "rerun-review.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(review, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return review


def present(review: Dict[str, Any]) -> str:
    """Render the review as a clear, log-friendly block (same text in CLI and API)."""
    L: List[str] = []
    L.append("=" * 72)
    L.append(f"RERUN REVIEW - {review.get('project')}")
    L.append("=" * 72)
    ex = review.get("existing", {})
    brief = (ex.get("brief") or "").strip()
    if brief:
        L.append("Existing brief:")
        L.append("  " + brief.replace("\n", "\n  "))
    else:
        L.append("Existing brief: (none)")
    arts = ex.get("artifacts") or {}
    if arts:
        L.append("Existing artifacts: " + ", ".join(f"{k}({v})" for k, v in arts.items()))
    L.append("")
    L.append("Recommendations:")
    for r in review.get("recommends", []):
        L.append(f"  - {r.get('kind')}: {r.get('detail')}")
    L.append("")
    L.append("Action: continue (reuse inputs + apply recommendations) | "
             "accept-recommendations | reject")
    L.append("=" * 72)
    return "\n".join(L)


def decide(project_dir: str, decision: str, note: str = "") -> Dict[str, Any]:
    """Record the operator's rerun decision (continue | accept-recommendations | reject)."""
    p = os.path.join(project_dir, "rerun-review.json")
    d = _load(p, {"project": os.path.basename(project_dir.rstrip('/\\')), "recommends": []})
    d["decision"] = {"value": decision, "note": note, "at": datetime.now().isoformat()}
    try:
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return d


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Rerun review (general)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--decision", default="", choices=["", "continue", "accept-recommendations", "reject"])
    a = ap.parse_args()
    pd = os.path.join("products", a.project)
    if a.decision:
        print(json.dumps(decide(pd, a.decision), indent=2))
    else:
        rv = build(pd, a.project)
        print(present(rv))
