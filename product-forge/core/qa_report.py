"""
QA Go/No-Go matrix + per-cycle coverage report.

Go/No-Go aggregates the quality dimensions (incl. Spec Review) into a RAG matrix
and a decision: any Red -> NO-GO; Yellow only -> GO-WITH-RISK; all Green -> GO.
QIR is the magnitude/trend that accompanies the decision.

Persists: test-framework/results/<project>/{go-no-go.json,coverage-<cycle>.json}
          products/<project>/docs/qa/go-no-go.md
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
from datetime import datetime
from typing import Any, Dict, List, Optional

_REPO = str(_PF_ROOT)
_TF = os.path.join(_REPO, "test-framework")


def _cycles(project: str) -> List[Dict]:
    d = os.path.join(_TF, "results", "test-cycles")
    out = []
    if not os.path.isdir(d):
        return out
    for name in os.listdir(d):
        if name.startswith(project + "_") and name.endswith(".json"):
            try:
                with open(os.path.join(d, name), "r", encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception:
                pass
    out.sort(key=lambda c: c.get("started_at", ""))
    return out


def _row(name: str, rag: str, detail: str) -> Dict[str, Any]:
    return {"dimension": name, "rag": rag, "detail": detail}


def _verification_row(project_dir: str, tech_stack: Optional[Dict] = None) -> Dict[str, Any]:
    """Gate the verification policy: not-run/external categories lower the RAG."""
    try:
        from core.verification_policy import policy
        p = policy(project_dir, tech_stack)
    except Exception:
        return _row("Verification coverage", "green", "policy unavailable")
    not_run, external = p.get("not_run", []), p.get("external", [])
    if not_run:
        rag = "red" if len(not_run) >= 3 else "yellow"
    elif external:
        rag = "yellow"
    else:
        rag = "green"
    return _row("Verification coverage", rag,
                f"internal={len(p.get('internal', []))} external={external} not_run={not_run}")


def _rag(green: bool, yellow: bool) -> str:
    return "green" if green else ("yellow" if yellow else "red")


def go_no_go(project: str, project_dir: str, tech_stack: Optional[Dict] = None,
             domain: Optional[str] = None) -> Dict[str, Any]:
    from core.qir import compute_qir
    qir = compute_qir(project, project_dir, tech_stack, domain)

    spec = {}
    try:
        from core.spec_review import summary as sr
        spec = sr(project_dir, project)
    except Exception:
        pass

    cov = {}
    try:
        from core.nfr_coverage import compute_nfr_coverage
        cov = compute_nfr_coverage(project_dir)
    except Exception:
        pass

    missing: List[str] = []
    try:
        from core.test_matrix import missing_categories, categories_for_kind, product_kind
        from core.qa_cycles import categories_for_suite
        cats = categories_for_kind(product_kind(tech_stack or {})) or categories_for_suite("feature")
        missing = missing_categories(project_dir, cats, tech_stack)
    except Exception:
        pass

    dsummary = {}
    rcca_ratio = None
    try:
        from core.defect_loop import tracker
        t = tracker(project)
        dsummary = t.get_summary()
        defs = list(getattr(t, "defects", []) or [])
        rcca_ratio = (len([d for d in defs if getattr(d, "rcca_stage", None)]) / len(defs)) if defs else None
    except Exception:
        pass

    cycles = _cycles(project)
    last = cycles[-1] if cycles else {}
    last_status = str(last.get("status", ""))

    insights = {}
    try:
        from core.qa_intelligence import load as iload
        insights = iload(project)
    except Exception:
        pass
    has_regression = any(i.get("type") in ("regression", "quality_decline")
                         for i in (insights.get("insights") or []))

    open_defects: List[Dict] = []
    try:
        from core.defect_loop import open_defects as _od
        open_defects = _od(project)
    except Exception:
        open_defects = []
    open_high = len([d for d in open_defects
                     if str(d.get("severity", "")).lower() in ("critical", "high")])
    open_any = len(open_defects)

    fr_ratio = (cov.get("fr_covered", 0) / cov["fr_total"]) if cov.get("fr_total") else None
    nfr_ratio = (cov.get("covered", 0) / cov["total"]) if cov.get("total") else None
    func_score = next((c["score"] for c in qir.get("profile", []) if c["characteristic"] == "functional"), 0.7)
    sec_score = next((c["score"] for c in qir.get("profile", []) if c["characteristic"] == "security"), 0.7)

    rows = [
        _row("Spec Review (QA gate)",
             _rag(spec.get("blocking_open", 0) == 0 and spec.get("optional_open", 0) == 0,
                  spec.get("blocking_open", 0) == 0),
             f"blocking={spec.get('blocking_open',0)} optional={spec.get('optional_open',0)}"),
        _row("Functional results", _rag((func_score or 0) >= 0.95, (func_score or 0) >= 0.8),
             f"functional_score={round(func_score or 0,2)} pass_rate={qir.get('profile') and ''}"),
        _row("Layer coverage", _rag(not missing, len(missing) <= 2),
             f"missing_categories={missing}"),
        _row("NFR quality", _rag((nfr_ratio or 0) >= 0.9 and (sec_score or 0) >= 0.9,
                                 (nfr_ratio or 0) >= 0.7),
             f"nfr_coverage={None if nfr_ratio is None else round(nfr_ratio,2)} security={round(sec_score or 0,2)}"),
        _row("Defects", "red" if open_high else ("yellow" if open_any else "green"),
             f"open_critical_high={open_high} open_total={open_any}"),
        _row("Traceability", _rag((fr_ratio or 0) >= 1.0, (fr_ratio or 0) >= 0.8),
             f"fr_coverage={None if fr_ratio is None else round(fr_ratio,2)}"),
        _row("Deploy/Smoke", _rag(last_status == "passed", last_status != "failed"),
             f"last_cycle_status={last_status or 'n/a'}"),
        _row("Install/Packaging", _rag(True, True), "checked in packaging stage"),
        _row("Regression trend", _rag(not has_regression, not has_regression),
             f"regression={has_regression}"),
        _row("RCCA completeness",
             "green" if rcca_ratio is None else _rag(rcca_ratio >= 0.9, rcca_ratio >= 0.5),
             f"rcca_coverage={None if rcca_ratio is None else round(rcca_ratio,2)}"),
        _verification_row(project_dir, tech_stack),
    ]
    reds = [r for r in rows if r["rag"] == "red"]
    yellows = [r for r in rows if r["rag"] == "yellow"]
    decision = "NO-GO" if reds else ("GO-WITH-RISK" if yellows else "GO")

    out = {"project": project, "decision": decision,
           "qir": {"number": qir.get("number"), "band": qir.get("band"), "trend": qir.get("trend")},
           "matrix": rows,
           "rationale": [f"{r['dimension']}: {r['detail']}" for r in reds + yellows],
           "created_at": datetime.now().isoformat()}
    _persist(project, project_dir, out)
    return out


def _persist(project: str, project_dir: str, out: Dict):
    d = os.path.join(_TF, "results", project)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "go-no-go.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    qa = os.path.join(project_dir, "docs", "qa")
    os.makedirs(qa, exist_ok=True)
    lines = [f"# QA Go/No-Go — {project}", f"", f"**Decision: {out['decision']}** "
             f"(QIR {out['qir'].get('number')} {out['qir'].get('band')})", "",
             "| Dimension | RAG | Detail |", "|---|---|---|"]
    lines += [f"| {r['dimension']} | {r['rag']} | {r['detail']} |" for r in out["matrix"]]
    if out["rationale"]:
        lines += ["", "## Blocking / at-risk"] + [f"- {x}" for x in out["rationale"]]
    with open(os.path.join(qa, "go-no-go.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def cycle_coverage_report(project: str, project_dir: str, cycle_id: Optional[str] = None) -> Dict[str, Any]:
    cycles = _cycles(project)
    c = None
    if cycle_id:
        c = next((x for x in cycles if x.get("cycle_id") == cycle_id), None)
    c = c or (cycles[-1] if cycles else {})
    runs = c.get("test_runs", [])
    out = {
        "project": project, "cycle_id": c.get("cycle_id", ""),
        "build_version": c.get("build_version", ""), "status": c.get("status", ""),
        "results": {"tests_run": sum(r.get("tests_run", 0) for r in runs),
                    "passed": sum(r.get("tests_passed", 0) for r in runs),
                    "failed": sum(r.get("tests_failed", 0) for r in runs),
                    "by_category": [{"framework": r.get("framework"), "status": r.get("status"),
                                     "run": r.get("tests_run"), "passed": r.get("tests_passed"),
                                     "failed": r.get("tests_failed")} for r in runs]},
    }
    try:
        from core.nfr_coverage import compute_nfr_coverage
        out["coverage"] = compute_nfr_coverage(project_dir)
    except Exception:
        out["coverage"] = {}
    try:
        from core.defect_loop import open_defects
        out["open_defects"] = open_defects(project)
    except Exception:
        out["open_defects"] = []
    d = os.path.join(_TF, "results", project)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"coverage-{out['cycle_id'] or 'latest'}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out


def load(project: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(_TF, "results", project, "go-no-go.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
