"""
QA trend intelligence (evidence-based).

Analyzes history across cycles/defects/spec-findings and produces insights with
concrete evidence: issue clustering in an area/feature, aging/unresolved issues,
regressions, instability, RCCA clustering and risk signals.

Output: test-framework/results/<project>/insights.json
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

# aging SLA in days by severity
SLA_DAYS = {"critical": 1, "high": 3, "medium": 5, "low": 10}


def _defects(project: str) -> List[Dict]:
    p = os.path.join(_TF, "defects", project, "defects.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception:
        return []


def _cycles(project: str) -> List[Dict]:
    d = os.path.join(_TF, "results", "test-cycles")
    out = []
    if not os.path.isdir(d):
        return out
    for name in os.listdir(d):
        if not name.startswith(project + "_") or not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name), "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            pass
    out.sort(key=lambda c: c.get("started_at", ""))
    return out


def _age_days(created: str) -> float:
    try:
        dt = datetime.fromisoformat(str(created).replace("Z", ""))
        return (datetime.now() - dt).total_seconds() / 86400
    except Exception:
        return 0.0


def _sev(d: Dict) -> str:
    return str(d.get("severity", "medium")).lower()


def analyze(project: str, project_dir: Optional[str] = None) -> Dict[str, Any]:
    defects = _defects(project)
    cycles = _cycles(project)
    insights: List[Dict] = []
    n = 0

    def add(itype, severity, confidence, scope, evidence, action):
        nonlocal n
        n += 1
        insights.append({
            "id": f"INS-{n:03d}", "type": itype, "severity": severity,
            "confidence": confidence, "scope": scope, "evidence": evidence,
            "recommended_action": action,
            "build_range": [c.get("build_version", "") for c in cycles[-3:]],
            "created_at": datetime.now().isoformat(),
        })

    open_defects = [d for d in defects if str(d.get("status")) in ("open", "in_progress")]

    # 1. Issue clustering by area (suite/feature)
    by_area: Dict[str, List[Dict]] = {}
    for d in defects:
        area = d.get("suite_name") or d.get("test_name") or "unknown"
        by_area.setdefault(area, []).append(d)
    for area, items in by_area.items():
        if len(items) >= 3:
            sev = "high" if any(_sev(i) in ("critical", "high") for i in items) else "medium"
            add("issue_clustering", sev, 0.8, {"area": area},
                [{"defect_id": i.get("defect_id"), "severity": _sev(i), "status": i.get("status")}
                 for i in items],
                f"Recurring issues in '{area}' ({len(items)}); investigate root cause.")

    # 2. Aging / unresolved
    for d in open_defects:
        age = _age_days(d.get("created_at", ""))
        sla = SLA_DAYS.get(_sev(d), 5)
        if age > sla:
            add("aging_unresolved", "high" if _sev(d) in ("critical", "high") else "medium",
                0.9, {"defect_id": d.get("defect_id"), "area": d.get("suite_name")},
                [{"defect_id": d.get("defect_id"), "age_days": round(age, 1),
                  "sla_days": sla, "status": d.get("status")}],
                f"Defect {d.get('defect_id')} open {round(age,1)}d (> SLA {sla}d); escalate.")

    # 3. Regression / instability by phase across cycles
    by_phase: Dict[str, List[str]] = {}
    for c in cycles:
        by_phase.setdefault(str(c.get("phase")), []).append(str(c.get("status")))
    for phase, statuses in by_phase.items():
        if "failed" in statuses and "passed" in statuses:
            add("instability", "medium", 0.7, {"phase": phase},
                [{"phase": phase, "statuses": statuses[-8:]}],
                f"Phase {phase} intermittently fails; check flaky tests/order dependency.")
        if statuses and statuses[-1] == "failed" and "passed" in statuses[:-1]:
            add("regression", "high", 0.75, {"phase": phase},
                [{"phase": phase, "recent": statuses[-5:]}],
                f"Phase {phase} regressed (passed -> failed); bisect recent builds.")

    # 4. Trend of pass rate across cycles (declining)
    def _rate(c):
        tot = sum(r.get("tests_run", 0) for r in c.get("test_runs", []))
        pas = sum(r.get("tests_passed", 0) for r in c.get("test_runs", []))
        return (pas / tot) if tot else None
    rates = [(c.get("build_version", ""), _rate(c)) for c in cycles]
    rates = [(b, r) for b, r in rates if r is not None]
    if len(rates) >= 3 and rates[-1][1] < rates[0][1] - 0.1:
        add("coverage_erosion" if False else "quality_decline", "medium", 0.6,
            {"metric": "pass_rate"}, [{"build": b, "pass_rate": round(r, 3)} for b, r in rates[-5:]],
            "Pass rate declining across builds; review recent changes.")

    # 5. RCCA clustering
    cats: Dict[str, int] = {}
    for d in defects:
        rc = d.get("rcca_stage") or d.get("root_cause")
        if rc:
            cats[str(rc)] = cats.get(str(rc), 0) + 1
    for rc, count in cats.items():
        if count >= 3:
            add("root_cause_cluster", "medium", 0.65, {"root_cause": rc},
                [{"root_cause": rc, "count": count}],
                f"Recurring root cause '{rc}' ({count}); add prevention at source stage.")

    data = {"project": project, "generated_at": datetime.now().isoformat(),
            "insights": insights,
            "summary": {
                "total": len(insights),
                "high": len([i for i in insights if i["severity"] == "high"]),
                "medium": len([i for i in insights if i["severity"] == "medium"]),
                "low": len([i for i in insights if i["severity"] == "low"]),
            }}
    _persist(project, data)
    return data


def _persist(project: str, data: Dict):
    out = os.path.join(_TF, "results", project)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "insights.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # U3: this per-project file is derived evidence; import it into the canonical store.
    try:
        from core import insights as _ins
        _ins.import_file(path, project=project, source="qa_intelligence")
    except Exception:
        pass


def load(project: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(_TF, "results", project, "insights.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"insights": [], "summary": {"total": 0}}
