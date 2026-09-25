"""Close-on-verify loop — auto-close a backlog + intake item once a run is VERIFIED.

Trigger: :func:`job_manager.finish` (every run ends there). Evidence is gathered from
existing stores (no new truth): tests, compliance, defects, Go/No-Go, traceability.
One decision function, scope-aware (config/verification-policy.json).

On verified:
  backlog BI-####  -> implemented -> verifying -> closed  (links: run_id, reports)
  intake  IN-####  -> closed                              (attaches final + QA report links)
On NOT verified:
  backlog -> blocked (+ optional fix/defect) ; intake stays open ; notify.

Never closes a run that did not produce evidence. `force_close()` allows an audited
manual override.
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

import glob
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

REPO = str(_PF_ROOT)
_POLICY = os.path.join(REPO, "config", "verification-policy.json")

_DEFAULT_POLICY = {
    "scopes": {
        "build": {"require": ["artifact_exists", "tests_passed", "compliance_passed",
                              "no_blocking_defects", "go_no_go"]},
        "entire": {"require": ["artifact_exists", "tests_passed", "compliance_passed",
                               "no_blocking_defects", "go_no_go"]},
        "prototype": {"require": ["artifact_exists"]},
        "research": {"require": ["artifact_exists"]},
        "explore": {"require": ["artifact_exists"]},
    },
    "reports": {"final": "final-report.json", "execution": "pipeline-execution-report.json",
                "qa": "qa-manifest.json", "quality": "quality-metrics.json",
                "traceability": "traceability.html", "compliance_glob": "compliance/*-latest.json",
                "tests_glob": "../test-framework/reports/*/index.html"},
}


def policy() -> Dict:
    p = json.loads(json.dumps(_DEFAULT_POLICY))
    try:
        with open(_POLICY, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        for k in ("scopes", "reports"):
            if isinstance(data.get(k), dict):
                p[k].update(data[k])
    except Exception:
        pass
    return p


def _rj(p: str, d):
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return d


# ── evidence collectors (best-effort; each returns bool) ─────────────────────

def _artifact_exists(project_dir: str) -> bool:
    from core import stage_paths as sp
    for _sid, d in sp.iter_stages(project_dir):
        for fn in os.listdir(d):
            if fn.endswith("-output.md") or fn.endswith(".md"):
                return True
    return False


def _tests_passed(project_dir: str) -> bool:
    qa = _rj(os.path.join(project_dir, "qa-manifest.json"), {}) or {}
    for k in ("passed", "tests_passed", "all_passed"):
        if k in qa:
            return bool(qa.get(k))
    qm = _rj(os.path.join(project_dir, "quality-metrics.json"), {}) or {}
    if qm.get("tests_failed") is not None:
        return int(qm.get("tests_failed") or 0) == 0 and int(qm.get("tests_total") or 0) > 0
    return False


def _compliance_passed(project_dir: str) -> bool:
    files = glob.glob(os.path.join(project_dir, "compliance", "*-latest.json"))
    for f in files:
        d = _rj(f, {}) or {}
        st = str(d.get("status") or d.get("result") or "").lower()
        if st in ("pass", "passed", "ok"):
            return True
    return False


def _no_blocking_defects(project_dir: str) -> bool:
    idir = os.path.join(project_dir, "issues")
    if not os.path.isdir(idir):
        return True
    for fn in os.listdir(idir):
        d = _rj(os.path.join(idir, fn), None)
        items = d if isinstance(d, list) else (d or {}).get("issues") or []
        for it in items:
            sev = str((it or {}).get("severity") or "").lower()
            st = str((it or {}).get("status") or "open").lower()
            if sev in ("critical", "high", "blocker") and st not in ("closed", "resolved", "done"):
                return False
    return True


def _go_no_go(project_dir: str) -> bool:
    for p in (os.path.join(project_dir, "approvals", "10a"),
              os.path.join(project_dir, "approvals", "10")):
        if os.path.isdir(p):
            for fn in os.listdir(p):
                d = _rj(os.path.join(p, fn), {}) or {}
                if str(d.get("status") or "").lower() == "approved":
                    return True
    return False


_EVIDENCE = {
    "artifact_exists": _artifact_exists,
    "tests_passed": _tests_passed,
    "compliance_passed": _compliance_passed,
    "no_blocking_defects": _no_blocking_defects,
    "go_no_go": _go_no_go,
}


def collect_reports(project_dir: str) -> Dict[str, str]:
    """Absolute paths of the final + QA + related reports (for the intake item)."""
    pol = policy()["reports"]
    out: Dict[str, str] = {}
    proj = os.path.basename(project_dir)
    for key in ("final", "execution", "qa", "quality"):
        p = os.path.join(project_dir, pol.get(key, ""))
        if pol.get(key) and os.path.exists(p):
            out[key] = p
    tr = os.path.join(project_dir, pol.get("traceability", ""))
    if os.path.exists(tr):
        out["traceability"] = tr
    for f in glob.glob(os.path.join(project_dir, pol.get("compliance_glob", ""))):
        out["compliance"] = f
        break
    for f in glob.glob(os.path.join(project_dir, pol.get("tests_glob", ""))):
        if proj in f or "reports" in f:
            out["tests"] = f
            break
    return out


def verify_run(project_dir: str, scope: str = "") -> Dict:
    """Decide verified/not for a completed run (scope-aware). No side effects."""
    pol = policy()
    sc = (scope or "entire").lower()
    require = (pol["scopes"].get(sc) or pol["scopes"].get("entire") or {}).get("require") or []
    evidence: Dict[str, bool] = {}
    reasons: List[str] = []
    for req in require:
        fn = _EVIDENCE.get(req)
        ok = bool(fn and fn(project_dir))
        evidence[req] = ok
        if not ok:
            reasons.append(f"missing/failed: {req}")
    verified = all(evidence.values()) if require else False
    return {"verified": verified, "scope": sc, "require": require,
            "evidence": evidence, "reasons": reasons,
            "reports": collect_reports(project_dir)}


def _scope_for(project_dir: str, item_ids: List[str]) -> str:
    """The item's pipeline scope (from intake/backlog), default 'entire'."""
    from core import intake_channels as ic
    products = os.path.dirname(os.path.abspath(project_dir))
    for bid in item_ids:
        it = ic.find_by_backlog(products, bid)
        if it and it.get("scope"):
            return str(it["scope"])
    return "entire"


def verify_and_close(project_dir: str, run_id: str = "",
                     item_ids: Optional[List[str]] = None) -> Dict:
    """Verify a finished run and, if verified, close its backlog + intake items."""
    ids = [i.strip() for i in (item_ids or []) if str(i).strip()]
    scope = _scope_for(project_dir, ids)
    res = verify_run(project_dir, scope)
    res.update({"run_id": run_id, "item_ids": ids, "closed_backlog": [], "closed_intake": []})
    if not ids:
        res["note"] = "no backlog item linked; nothing to close"
        return res

    from core import backlog
    products = os.path.dirname(os.path.abspath(project_dir))
    proj = os.path.basename(project_dir)
    links = {"run_id": run_id, **{k: v for k, v in res["reports"].items()}}

    for bid in ids:
        try:
            # which scope owns this backlog item?
            in_proj = backlog.get_epic("project", proj, bid) is not None
            bscope, bproj = ("project", proj) if in_proj else ("product_forge", None)
            if res["verified"]:
                backlog.set_status(bscope, bproj, bid, "implemented",
                                   note=f"auto: verified by run {run_id}")
                backlog.set_status(bscope, bproj, bid, "closed",
                                   note=f"auto closed by run {run_id} (verified)")
                res["closed_backlog"].append(bid)
                try:
                    from core import intake_channels as ic
                    it = ic.find_by_backlog(products, bid)
                    if it:
                        ic.close_verified(products, it["id"], backlog_ref=bid,
                                          report_links=links)
                        res["closed_intake"].append(it["id"])
                except Exception:
                    pass
            else:
                try:
                    backlog.set_status(bscope, bproj, bid, "blocked",
                                       note=f"verify failed: {', '.join(res['reasons'])[:120]}")
                except Exception:
                    pass
        except Exception as e:
            res.setdefault("errors", []).append(f"{bid}: {e}")

    try:
        from core import log_router as _lr
        _lr.log_event(_lr.backend_log_path(), run_id=run_id, event="verify_close",
                      message=f"project={proj} verified={res['verified']} "
                              f"backlog={res['closed_backlog']} intake={res['closed_intake']}")
    except Exception:
        pass
    return res


def force_close(project_dir: str, item_ids: List[str], by: str = "operator",
                note: str = "") -> Dict:
    """Audited manual close when automation cannot decide."""
    from core import backlog, intake_channels as ic
    proj = os.path.basename(project_dir)
    products = os.path.dirname(os.path.abspath(project_dir))
    out = {"force_closed": [], "intake": []}
    for bid in item_ids:
        try:
            backlog.set_status("project", proj, bid, "closed",
                               note=f"force-closed by {by}: {note}")
            out["force_closed"].append(bid)
            it = ic.find_by_backlog(products, bid)
            if it:
                ic.close_verified(products, it["id"], backlog_ref=bid,
                                  report_links={"forced_by": by, "note": note})
                out["intake"].append(it["id"])
        except Exception as e:
            out.setdefault("errors", []).append(str(e))
    return out
