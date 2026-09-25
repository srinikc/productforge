"""
QIR — Quality Index Report (project-level).

One number (0-100, band, trend) + a profile of ISO/IEC 25010:2023 characteristics
(9) plus a QA Governance extension. Weighted sum with a hard cap when any
characteristic is red/blocking.

Persists: test-framework/results/<project>/{qir.json,qir-history.json}
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
_WEIGHTS = os.path.join(_REPO, "config", "qa-weights.json")


def _load_weights() -> Dict:
    try:
        with open(_WEIGHTS, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


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


def _signals(project: str, project_dir: str) -> Dict[str, Any]:
    sig: Dict[str, Any] = {}
    # coverage
    try:
        from core.nfr_coverage import compute_nfr_coverage
        cov = compute_nfr_coverage(project_dir)
        fr_total = cov.get("fr_total", 0)
        sig["fr_ratio"] = (cov.get("fr_covered", 0) / fr_total) if fr_total else None
        nfr_total = cov.get("total", 0)
        sig["nfr_ratio"] = (cov.get("covered", 0) / nfr_total) if nfr_total else None
    except Exception:
        pass
    # cycle pass rate (latest)
    cycles = _cycles(project)
    rate = None
    if cycles:
        c = cycles[-1]
        tot = sum(r.get("tests_run", 0) for r in c.get("test_runs", []))
        pas = sum(r.get("tests_passed", 0) for r in c.get("test_runs", []))
        rate = (pas / tot) if tot else None
    sig["pass_rate"] = rate
    sig["cycles"] = len(cycles)
    # defects
    try:
        from core.defect_loop import tracker
        t = tracker(project)
        defs = list(getattr(t, "defects", []) or [])
        sig["open_high"] = len([d for d in defs if str(getattr(d.status, "value", d.status)) in ("open", "in_progress")
                                and str(getattr(d.severity, "value", d.severity)) in ("critical", "high")])
        sig["open_total"] = len([d for d in defs if str(getattr(d.status, "value", d.status)) in ("open", "in_progress")])
        sig["rcca_ratio"] = (len([d for d in defs if getattr(d, "rcca_stage", None)]) / len(defs)) if defs else None
    except Exception:
        pass
    # spec review
    try:
        from core.spec_review import summary as sr
        sig["spec"] = sr(project_dir, project)
    except Exception:
        sig["spec"] = {}
    return sig


def _score(value: Optional[float], neutral: float) -> float:
    return neutral if value is None else max(0.0, min(1.0, float(value)))


def compute_qir(project: str, project_dir: str, tech_stack: Optional[Dict] = None,
                domain: Optional[str] = None) -> Dict[str, Any]:
    w = _load_weights()
    neutral = float(w.get("neutral_score", 0.78))
    from core.test_matrix import product_kind
    kind = product_kind(tech_stack or {})
    base = (w.get("base") or {}).get(kind) or (w.get("base") or {}).get("default") or {}
    weights = dict(base)
    if domain:
        for k, dv in ((w.get("domain_overlays") or {}).get(domain, {}) or {}).items():
            weights[k] = max(0, weights.get(k, 0) + dv)
    total_w = sum(weights.values()) or 1

    s = _signals(project, project_dir)
    spec = s.get("spec") or {}
    blocking = spec.get("blocking_open", 0)
    optional = spec.get("optional_open", 0)

    func = 0.5 * _score(s.get("fr_ratio"), neutral) + 0.5 * _score(s.get("pass_rate"), neutral)
    rel = _score(s.get("pass_rate"), neutral)
    sec = 1.0 - min(1.0, (s.get("open_high", 0) / 3.0)) if s.get("open_high") is not None else neutral
    scores = {
        "functional": func,
        "performance": neutral,
        "compatibility": neutral,
        "interaction": 1.0 - min(1.0, optional * 0.1) if spec else neutral,
        "reliability": rel,
        "security": max(neutral, sec) if s.get("open_high") is not None else neutral,
        "maintainability": 1.0 - min(1.0, blocking * 0.2),
        "flexibility": neutral,
        "safety": neutral,
        "governance": (1.0 - min(1.0, blocking * 0.25)) * 0.5 + _score(s.get("nfr_ratio"), neutral) * 0.5,
    }
    evidence = {
        "functional": f"fr_coverage={s.get('fr_ratio')} pass_rate={s.get('pass_rate')}",
        "reliability": f"pass_rate={s.get('pass_rate')}",
        "security": f"open_high_defects={s.get('open_high')}",
        "interaction": f"optional_spec_findings={optional}",
        "maintainability": f"blocking_spec_findings={blocking}",
        "governance": f"blocking={blocking} nfr_coverage={s.get('nfr_ratio')}",
    }

    number = 100.0 * sum(weights.get(k, 0) * scores.get(k, neutral) for k in weights) / total_w
    red = any(scores.get(k, 1.0) < 0.5 for k in weights) or blocking > 0
    if red:
        number = min(number, float((w.get("bands") or {}).get("cap_red", 59)))
    number = round(number, 1)
    bands = w.get("bands") or {}
    band = "green" if number >= bands.get("green", 90) else \
           ("yellow" if number >= bands.get("yellow", 75) else "red")

    profile = [{"characteristic": k, "weight": weights.get(k, 0),
                "score": round(scores.get(k, neutral), 3),
                "evidence": evidence.get(k, "")} for k in weights]

    out = {"project": project, "product_kind": kind, "domain": domain or "",
           "number": number, "band": band, "profile": profile,
           "blocking_spec_findings": blocking, "created_at": datetime.now().isoformat()}
    out["trend"] = _trend(project, number)
    _persist(project, out)
    return out


def _trend(project: str, number: float) -> Dict[str, Any]:
    path = os.path.join(_TF, "results", project, "qir-history.json")
    hist = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            hist = json.load(f) or []
    except Exception:
        hist = []
    prev = hist[-1]["number"] if hist else None
    delta = round(number - prev, 1) if prev is not None else 0.0
    return {"previous": prev, "delta": delta,
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat")}


def _persist(project: str, out: Dict):
    d = os.path.join(_TF, "results", project)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "qir.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    hist_path = os.path.join(d, "qir-history.json")
    try:
        with open(hist_path, "r", encoding="utf-8") as f:
            hist = json.load(f) or []
    except Exception:
        hist = []
    hist.append({"number": out["number"], "band": out["band"], "created_at": out["created_at"]})
    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump(hist[-50:], f, indent=2)


def load(project: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(_TF, "results", project, "qir.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
