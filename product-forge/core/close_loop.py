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

import contextlib
import glob
import json
import os
from datetime import datetime

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


def policy() -> dict:
    p = json.loads(json.dumps(_DEFAULT_POLICY))
    try:
        with open(_POLICY, encoding="utf-8-sig") as f:
            data = json.load(f)
        for k in ("scopes", "reports"):
            if isinstance(data.get(k), dict):
                p[k].update(data[k])
    except Exception:
        pass
    return p


def _rj(p: str, d):
    try:
        with open(p, encoding="utf-8-sig") as f:
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


def _compliance_passed(project_dir: str, run_id: str = "") -> bool:
    """Run-bound (PF-031): when a run id is known, only a report from THAT run counts."""
    files = glob.glob(os.path.join(project_dir, "compliance", "*-latest.json"))
    for f in files:
        d = _rj(f, {}) or {}
        st = str(d.get("status") or d.get("result") or "").lower()
        if st not in ("pass", "passed", "ok"):
            continue
        if run_id:
            if str(d.get("run_id") or "") == str(run_id):
                return True
            continue  # stale/other-run report -> not evidence for this run
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


def collect_reports(project_dir: str) -> dict[str, str]:
    """Absolute paths of the final + QA + related reports (for the intake item)."""
    pol = policy()["reports"]
    out: dict[str, str] = {}
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


def verify_run(project_dir: str, scope: str = "", run_id: str = "") -> dict:
    """Decide verified/not for a completed run (scope-aware). No side effects."""
    pol = policy()
    sc = (scope or "entire").lower()
    require = (pol["scopes"].get(sc) or pol["scopes"].get("entire") or {}).get("require") or []
    evidence: dict[str, bool] = {}
    reasons: list[str] = []
    for req in require:
        fn = _EVIDENCE.get(req)
        if req == "compliance_passed":
            ok = bool(fn and fn(project_dir, run_id=run_id))
        else:
            ok = bool(fn and fn(project_dir))
        evidence[req] = ok
        if not ok:
            reasons.append(f"missing/failed: {req}")
    verified = all(evidence.values()) if require else False
    return {"verified": verified, "scope": sc, "require": require,
            "evidence": evidence, "reasons": reasons,
            "reports": collect_reports(project_dir)}


def _scope_for(project_dir: str, item_ids: list[str]) -> str:
    """The item's pipeline scope (from intake/backlog), default 'entire'."""
    from core import intake_channels as ic
    products = os.path.dirname(os.path.abspath(project_dir))
    for bid in item_ids:
        it = ic.find_by_backlog(products, bid)
        if it and it.get("scope"):
            return str(it["scope"])
    return "entire"


def _finalize(project_dir: str, scope: str, project, item_id: str, run_id: str, proj: str) -> dict:
    """PFSSOT-P8A.1 (BI-PF-0381): write delivery provenance + run-bound evidence onto the item.

    Reuses ``backlog.set_delivery`` (writes ``links.delivery``) + ``github.build_evidence`` + git for the
    branch/commits/merge SHA. One writer per store; no new store.
    """
    import subprocess

    from core import backlog, github
    branch = commits = merge_sha = ""
    try:
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir,
                                capture_output=True, text=True).stdout.strip()
        merge_sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=project_dir,
                                   capture_output=True, text=True).stdout.strip()
        commits = [c for c in subprocess.run(["git", "log", "--format=%h", "-5"], cwd=project_dir,
                                             capture_output=True, text=True).stdout.split() if c]
    except Exception:
        pass
    ev = {}
    try:
        ev = github.build_evidence(proj, project_dir, run_id=run_id, head_sha=merge_sha,
                                   backlog_ref=item_id)
    except Exception:
        ev = {}
    # write under links.delivery (canonical) + links.evidence (run-bound)
    backlog.set_delivery(scope, project, item_id, branch=branch, merge_sha=merge_sha,
                         commits=commits, note=f"auto-finalized by run {run_id}")
    with contextlib.suppress(Exception):
        backlog.link(scope, project, item_id, evidence={
            "run_id": run_id, "commit_sha": merge_sha,
            "pr": (ev or {}).get("pr") or "", "checks": list((ev or {}).get("checks") or []),
            "at": datetime.now().isoformat()})
    return {"item": item_id, "branch": branch, "merge_sha": merge_sha, "commits": commits}


def verify_and_close(project_dir: str, run_id: str = "",
                     item_ids: list[str] | None = None) -> dict:
    """Verify a finished run and, if verified, close its backlog + intake items."""
    ids = [i.strip() for i in (item_ids or []) if str(i).strip()]
    scope = _scope_for(project_dir, ids)
    res = verify_run(project_dir, scope, run_id)
    # F0-3 / PF-006: when this run has a provenance manifest, verification must be
    # satisfied by a RUN-BOUND artifact (hash still matches) - not just any markdown.
    try:
        from core import run_manifest as _rm
        if run_id and _rm.has(project_dir, run_id):
            if not _rm.verify_any_artifact(project_dir, run_id):
                res["evidence"]["artifact_exists"] = False
                res["reasons"].append("artifact_exists: no run-bound artifact (missing/hash mismatch/stale)")
            res["verified"] = all(res["evidence"].values()) if res["evidence"] else False
    except Exception:
        pass
    res.update({"run_id": run_id, "item_ids": ids, "closed_backlog": [], "closed_intake": []})
    if not ids:
        res["note"] = "no backlog item linked; nothing to close"
        return res

    from core import backlog
    products = os.path.dirname(os.path.abspath(project_dir))
    proj = os.path.basename(project_dir)
    links = {"run_id": run_id, **dict(res["reports"])}

    # PIDL-4 (BI-PF-0379): cross-worker synthesis gate when a run closes multiple items. Advisory by
    # default; in enforce mode a conflicting synthesis holds the close (PIDL_GATE_MODE).
    synth_hold = False
    if len(ids) > 1:
        try:
            from core import pidl as _pidl_syn
            _syn = _pidl_syn.synthesize(scope, None, results=[
                {"item_id": b, "ok": bool(res["verified"]),
                 "status": "pr_ready" if res["verified"] else "held"} for b in ids])
            res["pidl_synthesis"] = _syn.get("synthesis")
            res["pidl_synthesis_action"] = (_syn.get("decision") or {}).get("action")
            synth_hold = (_pidl_syn.gate_mode() == "enforce"
                          and (_syn.get("decision") or {}).get("action") == "CORRECT")
        except Exception:
            pass

    for bid in ids:
        try:
            # which scope owns this backlog item?
            in_proj = backlog.get_epic("project", proj, bid) is not None
            bscope, bproj = ("project", proj) if in_proj else ("product_forge", None)
            # PIDL-3 (BI-PF-0378): worker-result decision gate (advisory by default; enforce via
            # PIDL_GATE_MODE). Invoked by orchestration here at the result boundary - never by the worker.
            pidl_action, pidl_hold = "AUTO_PROCEED", False
            try:
                from core import pidl as _pidl
                _pd = _pidl.gate(bscope, bproj, item_id=bid, run_id=run_id,
                                 result={"ok": bool(res["verified"]),
                                         "status": "pr_ready" if res["verified"] else "failed"})
                pidl_action = str((_pd.get("decision") or {}).get("action") or "AUTO_PROCEED")
                with contextlib.suppress(Exception):
                    backlog.update(bscope, bproj, bid, links={"pidl": {
                        "action": pidl_action, "risk": _pd.get("risk"),
                        "profile_version": _pd.get("pidl_profile_version"),
                        "gate_mode": _pd.get("gate_mode"), "run_id": run_id}})
                res.setdefault("pidl", {})[bid] = pidl_action
                pidl_hold = _pidl.gate_mode() == "enforce" and pidl_action != "AUTO_PROCEED"
            except Exception:
                pass
            if res["verified"] and not pidl_hold and not synth_hold:
                backlog.set_status(bscope, bproj, bid, "implemented",
                                   note=f"auto: verified by run {run_id}")
                backlog.set_status(bscope, bproj, bid, "closed",
                                   note=f"auto closed by run {run_id} (verified)")
                # PFSSOT-P8A.1 (BI-PF-0381): auto write-back delivery + evidence provenance.
                try:
                    _finalize(project_dir, bscope, bproj, bid, run_id, proj)
                except Exception as _e:
                    res.setdefault("finalize_errors", []).append(f"{bid}: {type(_e).__name__}")
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
            elif res["verified"] and (pidl_hold or synth_hold):
                _why = pidl_action if pidl_hold else f"synthesis:{res.get('pidl_synthesis_action')}"
                with contextlib.suppress(Exception):
                    backlog.set_status(bscope, bproj, bid, "blocked",
                                       note=f"pidl gate ({_why}); review/approval required")
                res.setdefault("pidl_held", []).append(bid)
            else:
                with contextlib.suppress(Exception):
                    backlog.set_status(bscope, bproj, bid, "blocked",
                                       note=f"verify failed: {', '.join(res['reasons'])[:120]}")
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


def force_close(project_dir: str, item_ids: list[str], by: str = "operator",
                note: str = "") -> dict:
    """Audited manual close when automation cannot decide."""
    from core import backlog
    from core import intake_channels as ic
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
