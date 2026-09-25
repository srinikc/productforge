"""
Defect -> fix -> RCCA loop.

Bridges the test-framework's DefectTracker / RCCAAnalyzer into the pipeline so that:
  * open defects are handed to the fix agent (defect_brief), and
  * each defect yields root-cause + prevention recommendations (RCCA) fed back to
    earlier stages/agents.
Also exposes TestGenerator for stack-agnostic test scaffolds (FR/NFR tagged).

All framework imports are lazy + guarded: if the test framework is absent this
degrades to no-ops instead of failing the pipeline.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_TF = _REPO / "test-framework"


def _load(name: str, rel: str):
    from core.test_framework_integration import _load as _l
    return _l(name, rel)


def _defects_dir(project: str) -> str:
    return str(_TF / "defects" / project)


def tracker(project: str):
    return _load("defect_tracker", "core/defect_tracker.py").DefectTracker(project)


def open_defects(project: str) -> List[Dict[str, Any]]:
    """Open defects ordered by severity (for the fix agent)."""
    try:
        out: List[Dict[str, Any]] = []
        for d in tracker(project).get_defects_for_fix_agent():
            out.append({
                "defect_id": d.defect_id,
                "title": d.title,
                "description": (d.description or "")[:800],
                "severity": getattr(d.severity, "value", str(d.severity)),
                "test_id": d.test_id,
                "test_name": d.test_name,
                "stack_trace": (d.stack_trace or "")[:1200],
            })
        return out
    except Exception as e:
        print(f"[DefectLoop] open_defects: {e}")
        return []


def analyze(project: str, defect: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run RCCA for one defect and persist root cause/prevention onto the defect."""
    try:
        analyzer = _load("rcca", "core/rcca.py").RCCAAnalyzer(_defects_dir(project))
        report = analyzer.analyze_defect(defect["defect_id"], defect)
        recs = list(getattr(report, "recommendations", []) or [])
        stage = getattr(getattr(report, "overall_stage", None), "value", None)
        try:
            tracker(project).update_defect(
                defect["defect_id"],
                root_cause=recs[0] if recs else "unspecified",
                rcca_stage=stage,
                rcca_recommendation="\n".join(recs) if recs else None,
            )
        except Exception:
            pass
        return {"defect_id": defect["defect_id"], "stage": stage,
                "confidence": getattr(report, "overall_confidence", None),
                "recommendations": recs}
    except Exception as e:
        print(f"[DefectLoop] analyze: {e}")
        return None


def analyze_open(project: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in open_defects(project):
        r = analyze(project, d)
        if r:
            out.append(r)
    return out


def defect_brief(project: str, project_dir: str = "") -> str:
    """Markdown brief for the fix agent: open defects + RCCA prevention."""
    if not project:
        return ""
    defects = open_defects(project)
    if not defects:
        return ""
    lines = ["## OPEN DEFECTS (fix these, then re-validate)", ""]
    for d in defects:
        lines.append(f"### [{d['severity'].upper()}] {d['defect_id']}: {d['title']}")
        lines.append(f"- test: {d['test_name'] or d['test_id']}")
        if d["description"]:
            lines.append(f"- detail: {d['description']}")
        if d["stack_trace"]:
            lines.append("```")
            lines.append(d["stack_trace"])
            lines.append("```")
        lines.append("")
    rcca = analyze_open(project)
    if rcca:
        lines.append("## ROOT-CAUSE / PREVENTION (avoid recurring defects)")
        for r in rcca:
            lines.append(f"- {r['defect_id']} (stage={r.get('stage')}): "
                         + "; ".join(r.get("recommendations", [])[:3]))
    return "\n".join(lines)


def resolve(project: str, defect_ids: List[str], fixed_by: str, fix_description: str,
            fix_files: Optional[List[str]] = None) -> int:
    """Mark defects as FIXED after a fix (verification happens separately)."""
    n = 0
    try:
        t = tracker(project)
        for did in defect_ids or []:
            if t.resolve_defect(did, fixed_by=fixed_by, fix_description=fix_description,
                                resolution_notes=fix_description, fix_files=fix_files or []):
                n += 1
    except Exception as e:
        print(f"[DefectLoop] resolve: {e}")
    return n


def reconcile(project: str, passed_tests: Optional[List[Any]] = None, all_passed: bool = False,
              fixed_by: str = "fix", note: str = "Auto-verified: test passes after fix") -> Dict[str, int]:
    """Close open defects whose tests now pass (loop back-half).

    `passed_tests` may be framework test objects or dicts with test_id/name.
    `all_passed` forces closure of every open defect (used when a suite passes
    but per-test identities are unavailable).
    """
    keys = set()
    for t in passed_tests or []:
        if isinstance(t, dict):
            keys.add(str(t.get("test_id") or ""))
            keys.add(str(t.get("name") or ""))
            keys.add(str(t.get("test_name") or ""))
        else:
            keys.add(str(getattr(t, "test_id", "") or ""))
            keys.add(str(getattr(t, "name", "") or ""))
            keys.add(str(getattr(t, "test_name", "") or ""))
    keys.discard("")

    verified = 0
    closed = 0
    try:
        t = tracker(project)
        for d in list(t.get_open_defects()):
            dkeys = {str(d.test_id or ""), str(d.test_name or "")} - {""}
            if not (all_passed or (keys & dkeys)):
                continue
            try:
                t.resolve_defect(d.defect_id, fixed_by=fixed_by,
                                 fix_description=note, resolution_notes=note)
                t.verify_defect(d.defect_id, verification_notes=note)
                t.close_defect(d.defect_id)
                verified += 1
                closed += 1
            except Exception as e:
                print(f"[DefectLoop] reconcile {d.defect_id}: {e}")
    except Exception as e:
        print(f"[DefectLoop] reconcile: {e}")
    return {"verified": verified, "closed": closed}


# ---- Test generation (stack-agnostic scaffolds, FR/NFR tagged) ----

def generate_tests(project_dir: str, features: List[Dict], categories: Optional[Dict] = None,
                   output_dir: Optional[str] = None) -> Dict[str, Any]:
    """Generate test scaffolds via the framework TestGenerator (guarded).

    Feature ids are sanitized to valid Python identifiers, and TODO bodies are
    converted to ``pytest.skip`` so scaffolds never report false passes.
    """
    import re

    def _safe(s: Any) -> str:
        return re.sub(r"[^0-9A-Za-z_]", "_", str(s or "feat")) or "feat"

    try:
        gen = _load("test_generator", "core/test_generator.py").TestGenerator()
        safe_features = [{"id": _safe(f.get("id")), "name": f.get("name", "")}
                         for f in (features or [])]
        cfg = {"features": safe_features, "test_categories": categories or {"unit": True}}
        tests: Dict[str, List[str]] = {}
        if hasattr(gen, "generate_all_tests"):
            tests = gen.generate_all_tests(cfg) or {}
        # Template-based scaffolds for every requested category × feature.
        cats = [c for c, on in (categories or {"unit": True}).items() if on]
        for f in safe_features:
            for cat in cats:
                try:
                    blobs = gen.generate_from_templates(f, cat)
                except Exception:
                    blobs = []
                if blobs:
                    tests.setdefault(f"{f['id']}_{cat}", []).extend(blobs)

        out = output_dir or os.path.join(project_dir, "tests", "generated")
        os.makedirs(out, exist_ok=True)
        written = 0
        for name, blobs in (tests or {}).items():
            for i, blob in enumerate(blobs or []):
                if "TODO" in blob:
                    blob = re.sub(r"(\n\s*)pass\b",
                                  r'\1pytest.skip("scaffold: implement this test")', blob)
                    if "import pytest" not in blob:
                        blob = "import pytest\n\n" + blob
                path = os.path.join(out, f"test_{_safe(name)}_{i}.py")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(blob)
                written += 1
        return {"generated": written, "path": out}
    except Exception as e:
        print(f"[DefectLoop] generate_tests: {e}")
        return {"generated": 0, "error": str(e)}


# ── U2/B3: route stage issue reports into the single problem store ──────────
_SEV = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW"}


def route_stage_issues(project: str, kind: str, issues: List[Any]) -> Dict[str, Any]:
    """Fold `issues/<stage>-<agent>-issues.json` entries into the DefectTracker and
    link each as a `bug` backlog item (B3). Deduped by title within open defects.

    `issues` may be a list of dicts or strings; unknown shapes are summarized.
    Returns {"routed": n, "skipped": n, "defect_ids": [...]}.
    """
    routed, skipped, ids = 0, 0, []
    if not issues:
        return {"routed": 0, "skipped": 0, "defect_ids": []}
    try:
        tr = tracker(project)                       # test-framework DefectTracker
        existing = {d.title.strip().lower() for d in tr.get_open_defects()}
        sev_mod = _load("defect_tracker", "core/defect_tracker.py")
        feature_id = ""
        for raw in issues:
            if isinstance(raw, str):
                data = {"title": raw[:120], "description": raw}
            else:
                data = raw if isinstance(raw, dict) else {"title": str(raw)}
            title = str(data.get("title") or data.get("issue") or data.get("message")
                        or data.get("name") or f"{kind} issue").strip()[:160]
            if title.lower() in existing:
                skipped += 1
                continue
            desc = str(data.get("description") or data.get("detail") or data.get("message") or title)
            sev_key = str(data.get("severity") or data.get("level") or data.get("priority")
                          or "medium").strip().lower()
            sev = getattr(sev_mod.Severity, _SEV.get(sev_key, "MEDIUM"))
            try:
                defect = tr.log_defect(title=title, description=desc, severity=sev,
                                       test_id=str(data.get("test_id") or kind),
                                       test_name=title, suite_name=kind)
            except TypeError:
                defect = tr.log_defect(title, desc, sev)
            did = getattr(defect, "defect_id", "") or (defect or {}).get("defect_id", "")
            feature_id = feature_id or (data.get("feature_id") or
                                        ((data.get("affected_features") or [""])[0]))
            if did:
                ids.append(did)
                try:
                    from core.backlog_link import link_defect
                    link_defect(project, feature_id, did, title=title, severity=sev_key)
                except Exception:
                    pass
            existing.add(title.lower())
            routed += 1
    except Exception as e:
        print(f"[DefectLoop] route_stage_issues: {e}")
    return {"routed": routed, "skipped": skipped, "defect_ids": ids}
