"""ENG-6: the Common Validation Engine — ONE engine with profiles (plan section 19/20).

This is a thin **orchestration/coordination** layer. It does NOT reimplement validation; it runs a *profile*
by delegating to the existing canonical owners:

  * target resolution        -> ``core.vcs`` (exact SHA / base / merge-base)
  * repo/build/tests          -> ``core.run_quality_gate`` + ``core.test_framework_integration`` + ``core.verification_runner``
  * policy / coverage         -> ``core.verification_policy``
  * quality verdict           -> ``core.qa_report`` + ``core.pr_gate``
  * run-bound decision        -> ``core.close_loop.verify_run``

Same engine; the profile changes target/scope/depth/trigger/repair/promotion. Evidence is run-bound; on any
doubt the result is BLOCKED (no false green). Results are recorded to the registered store
``validation-runs.json`` (single writer: this module).
"""
import contextlib
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any

from core.paths import PRODUCTS_DIR, ROOT

FILENAME = "validation-runs.json"
_PROFILE_PATH = os.path.join(ROOT, "config", "validation-profiles.json")
_RESULTS = ("PASS", "FAIL", "BLOCKED")


# ── store (single writer) ───────────────────────────────────────────────────
def _norm_scope(scope: str) -> str:
    return "product_forge" if str(scope) in ("portfolio", "product_forge") else "project"


def _dir(scope: str, project: str | None = None) -> str:
    if _norm_scope(scope) == "product_forge":
        return os.path.join(ROOT, "validation")
    return os.path.join(PRODUCTS_DIR, str(project or "_unknown"), "validation")


def path(scope: str, project: str | None = None) -> str:
    return os.path.join(_dir(scope, project), FILENAME)


def _lock(d: str) -> str:
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lp) > 300:
                    os.remove(lp)
                    continue
            except Exception:
                pass
            time.sleep(0.1)
    raise TimeoutError("could not acquire validation lock")


def _unlock(lp: str) -> None:
    with contextlib.suppress(Exception):
        os.remove(lp)


def _read(scope: str, project: str | None = None) -> dict[str, Any]:
    try:
        with open(path(scope, project), encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("runs"), list):
            return d
    except Exception:
        pass
    return {"runs": []}


def _write(scope: str, project: str | None, data: dict[str, Any]) -> None:
    p = path(scope, project)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def record(scope: str, project: str | None, run: dict[str, Any]) -> dict[str, Any]:
    d = _lock(_dir(scope, project))
    try:
        store = _read(scope, project)
        store["runs"].append(run)
        _write(scope, project, store)
        return run
    finally:
        _unlock(d)


def list_runs(scope: str, project: str | None = None, profile: str = "") -> list[dict[str, Any]]:
    rows = _read(scope, project).get("runs", [])
    if profile:
        rows = [r for r in rows if str(r.get("profile")) == profile]
    return list(rows)


# ── profiles ────────────────────────────────────────────────────────────────
def profiles() -> dict[str, Any]:
    try:
        with open(_PROFILE_PATH, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def profile(name: str) -> dict[str, Any] | None:
    n = str(name or "").upper()
    prof = (profiles().get("profiles") or {}).get(n)
    if prof is None:
        return None
    out = dict(prof)
    out["name"] = n
    return out


# ── target resolution (reuses core.vcs) ─────────────────────────────────────
def _resolve_target(project_dir: str, target: str, base: str = "") -> dict[str, Any]:
    from core.vcs import VCSManager
    v = VCSManager(project_dir)
    if not v.is_repo():
        return {"ok": False, "reason": "not a git repository"}
    sha = v.head_commit(target or "HEAD")
    base_ref = str(base or v.integration_branch or "")
    base_sha = v.head_commit(base_ref) if base_ref else ""
    merge_base = ""
    if base_sha:
        merge_base = v._git(["merge-base", sha, base_sha]).get("out", "")
    return {"ok": bool(sha), "sha": sha, "base": base_ref, "base_sha": base_sha,
            "merge_base": merge_base, "branch": v.current_branch()}


# ── delegate to the existing owners (no reimplementation) ───────────────────
def _check_quality_gate(project_dir: str, run_id: str = "") -> dict[str, Any]:
    from core import run_quality_gate
    latest = run_quality_gate.latest_run(project_dir, run_id) if run_id else None
    if not latest:
        latest = run_quality_gate.latest(project_dir)
    if not latest:
        return {"status": "unknown", "detail": "no quality-gate record"}
    return {"status": "pass" if latest.get("passed") else "fail",
            "detail": {"mode": latest.get("mode"), "reasons": latest.get("reasons", [])}}


def _check_tests(project_dir: str, project: str) -> dict[str, Any]:
    from core import qa_report
    rep = qa_report.load(project)
    if not rep:
        return {"status": "unknown", "detail": "no test cycle yet"}
    decision = str(rep.get("decision") or "")
    return {"status": "pass" if decision in ("GO", "GO-WITH-RISK") else "fail",
            "detail": {"decision": decision, "qir": rep.get("qir", {})}}


def _check_policy(project_dir: str) -> dict[str, Any]:
    from core import verification_policy
    s = verification_policy.summary(project_dir)
    return {"status": "pass" if s.get("internal", 0) else "unknown", "detail": s}


def _check_verification(project_dir: str) -> dict[str, Any]:
    from core import verification_runner
    res = verification_runner.run_verification(project_dir)
    if not res.get("ran"):
        return {"status": "skip", "detail": "no runnable project detected"}
    return {"status": "pass" if res.get("passed") else "fail", "detail": res}


def _check_pr_gate(project: str, project_dir: str) -> dict[str, Any]:
    from core import pr_gate
    ev = pr_gate.evaluate(project, project_dir)
    items = ev.get("items") or {}
    failed = sorted(k for k, v in items.items() if v.get("status") in ("fail", "unknown"))
    return {"status": "pass" if not failed else "fail",
            "detail": {"unmet": failed, "items": items}}


def _check_close_loop(project_dir: str, run_id: str) -> dict[str, Any]:
    from core import close_loop
    res = close_loop.verify_run(project_dir, run_id=run_id)
    return {"status": "pass" if res.get("verified") else "fail",
            "detail": {"verified": res.get("verified"), "reasons": res.get("reasons", [])}}


def _check_cross_contract(project: str, project_dir: str) -> dict[str, Any]:
    """BI-PF-0425: cross-component interface/contract consistency (reuses core.task_contract). Skip if none."""
    from core import task_contract
    try:
        tasks = task_contract.list_tasks("project", project)
    except Exception:
        tasks = []
    if not tasks:
        return {"status": "skip", "detail": "no task contracts to cross-check"}
    bad = []
    for t in tasks:
        v = task_contract.validate(t) if isinstance(t, dict) else {"ok": False, "errors": ["not an object"]}
        if not v.get("ok"):
            bad.append({"id": t.get("id"), "errors": v.get("errors", [])})
    return {"status": "fail" if bad else "pass",
            "detail": {"tasks": len(tasks), "invalid": bad[:5]}}


def _check_e2e(project: str, project_dir: str) -> dict[str, Any]:
    """BI-PF-0455: real end-to-end evidence - run the product's ``e2e`` category through the canonical test
    framework (``test_matrix`` plan + ``test_framework_integration`` runner). No dependence on a prior
    DOGFOOD PASS (a first run is never permanently BLOCKED) and no hardcoded scope. Skip when the product
    has no e2e suite; skip when no e2e runner is installed.
    """
    from core import test_framework_integration as tfi
    from core import test_matrix
    try:
        tech = tfi._tech_stack(project_dir)
        items = [it for it in test_matrix.plan(project_dir, ["e2e"], tech) if it.get("category") == "e2e"]
    except Exception as e:  # noqa: BLE001
        return {"status": "unknown", "detail": f"e2e plan error: {type(e).__name__}"}
    has_cfg = any(os.path.exists(os.path.join(project_dir, f))
                  for f in ("playwright.config.ts", "playwright.config.js", "playwright.config.mjs"))
    runnable = [it for it in items if it.get("exists") or has_cfg]
    if not runnable:
        return {"status": "skip", "detail": {"project": project, "note": "no e2e suite detected"}}
    results = [r for r in (tfi._run_plan_item(it, project_dir, tech) for it in runnable) if r is not None]
    checkable = [r for r in results if r.get("ok") is not None]
    if not checkable:
        return {"status": "skip", "detail": {"project": project, "results": results,
                                             "note": "e2e runner not installed"}}
    return {"status": "pass" if all(r.get("ok") for r in checkable) else "fail",
            "detail": {"project": project, "results": results}}


def _check_security(project: str, project_dir: str) -> dict[str, Any]:
    """BI-PF-0425: secret scan over the project tree (reuses the repo's secret patterns; no reimplementation)."""
    import importlib.util
    import os

    from core.paths import ROOT
    mod_path = os.path.join(str(ROOT), "scripts", "dev", "secret_scan.py")
    try:
        spec = importlib.util.spec_from_file_location("pf_secret_scan", mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        scan_text = mod.scan_text
    except Exception as e:  # noqa: BLE001
        return {"status": "unknown", "detail": f"secret-scan unavailable: {type(e).__name__}"}
    exts = (".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".env", ".ini", ".cfg", ".toml", ".txt")
    skip_dirs = {"node_modules", ".git", "__pycache__", "vendor", "dist", "build", ".venv"}
    hits, scanned = [], 0
    for dp, dn, fn in os.walk(project_dir):
        dn[:] = [x for x in dn if x not in skip_dirs]
        for f in fn:
            if scanned >= 800 or not f.lower().endswith(exts):
                continue
            p = os.path.join(dp, f)
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read()
            except Exception:
                continue
            scanned += 1
            found = scan_text(txt) or []
            for h in found:
                hits.append({"file": os.path.relpath(p, project_dir), "hit": str(h)[:80]})
    if hits:
        return {"status": "fail", "detail": {"count": len(hits), "secrets": hits[:10]}}
    return {"status": "pass", "detail": {"scanned_files": scanned}}


_CHECKERS = {
    "quality_gate": lambda p, d, r: _check_quality_gate(d, r),
    "tests": lambda p, d, r: _check_tests(d, p),
    "policy": lambda p, d, r: _check_policy(d),
    "verification": lambda p, d, r: _check_verification(d),
    "pr_gate": lambda p, d, r: _check_pr_gate(p, d),
    "cross_contract": lambda p, d, r: _check_cross_contract(p, d),
    "e2e": lambda p, d, r: _check_e2e(p, d),
    "security": lambda p, d, r: _check_security(p, d),
}


def _active_validations(v) -> int:
    """Count in-flight validation runs for the repo (worktrees on a ``validation/*`` branch). BI-PF-0420."""
    try:
        return sum(1 for w in v.list_worktrees()
                   if str(w.get("branch") or "").startswith("validation/"))
    except Exception:
        return 0


def run(project: str, project_dir: str, profile_name: str = "FEATURE_PR",
        target: str = "", base: str = "", run_id: str = "", scope: str = "project") -> dict[str, Any]:
    """Run a validation profile (composes existing validators). Returns a run-bound result."""
    prof = profile(profile_name)
    if prof is None:
        return {"ok": False, "error": f"unknown profile {profile_name!r}"}
    rid = run_id or f"val-{uuid.uuid4().hex[:12]}"
    started = datetime.now().isoformat()
    result: dict[str, Any] = {"run_id": rid, "profile": prof["name"], "project": project,
                              "target": prof["target"], "started_at": started}

    resolved = _resolve_target(project_dir, target, base)
    result["target_resolved"] = resolved
    if not resolved.get("ok"):
        result.update({"result": "BLOCKED", "reason": resolved.get("reason") or "target unresolved",
                       "checks": {}})
        result["finished_at"] = datetime.now().isoformat()
        record(scope, project, result)
        return result

    checks: dict[str, Any] = {}
    for name in prof["checks"]:
        if name == "target":
            continue
        fn = _CHECKERS.get(name)
        if fn is None:
            checks[name] = {"status": "unknown", "detail": "no checker (deferred to later ENG phase)"}
            continue
        try:
            checks[name] = fn(project, project_dir, rid)
        except Exception as e:
            checks[name] = {"status": "unknown", "detail": f"error: {type(e).__name__}"}

    # run-bound decision (canonical) as one more signal
    try:
        checks["close_loop"] = _check_close_loop(project_dir, rid)
    except Exception as e:
        checks["close_loop"] = {"status": "unknown", "detail": str(type(e).__name__)}

    statuses = [c.get("status") for c in checks.values()]
    if "fail" in statuses:
        verdict = "FAIL"
    elif all(s in ("pass", "skip") for s in statuses) and any(s == "pass" for s in statuses):
        verdict = "PASS"
    else:
        verdict = "BLOCKED"  # any unknown / no positive signal -> fail-closed

    result.update({"checks": checks, "result": verdict,
                   "promotion": prof.get("promotion") if verdict == "PASS" else "none",
                   "repair": bool(prof.get("repair")) and verdict != "PASS",
                   "finished_at": datetime.now().isoformat()})
    record(scope, project, result)
    return result


# ── ENG-7: FEATURE_PR execution (validate an exact PR/branch/commit) ────────
def _changed_files(project_dir: str, sha: str, merge_base: str) -> list[str]:
    from core.vcs import VCSManager
    v = VCSManager(project_dir)
    ref = f"{merge_base}..{sha}" if merge_base else f"{sha}~1..{sha}"
    out = v._git(["diff", "--name-only", ref]).get("out", "")
    return [x.strip() for x in out.splitlines() if x.strip()]


def _impact(changed: list[str]) -> dict[str, Any]:
    components = sorted({(f.split("/", 1)[0] if "/" in f else f) for f in changed})
    return {"changed_count": len(changed), "components": components}


def feature_pr(project: str, project_dir: str, target: str = "", base: str = "", run_id: str = "",
               scope: str = "project", use_worktree: bool = True,
               record_defects: bool = False) -> dict[str, Any]:
    """ENG-7: validate an exact PR/branch/commit before merge (plan section 21).

    Resolves exact SHA/base/merge-base, analyzes changed files + impact, runs the FEATURE_PR checks in a
    FRESH validation worktree (the developer branch is NEVER modified), assembles run-bound GitHub evidence and
    the PR merge decision, and returns PASS/FAIL/BLOCKED. ``auto_repair`` is always false.
    """
    from core.vcs import VCSManager
    rid = run_id or f"fpr-{uuid.uuid4().hex[:12]}"
    result: dict[str, Any] = {"run_id": rid, "profile": "FEATURE_PR", "project": project, "target": "pr",
                              "auto_repair": False, "started_at": datetime.now().isoformat()}
    resolved = _resolve_target(project_dir, target, base)
    result["target_resolved"] = resolved
    if not resolved.get("ok"):
        result.update({"result": "BLOCKED", "reason": resolved.get("reason") or "target unresolved", "checks": {}})
        result["finished_at"] = datetime.now().isoformat()
        record(scope, project, result)
        return result

    v = VCSManager(project_dir)
    # BI-PF-0420: bound concurrent validation runs per repo (no shared-checkout races)
    from core import capacity
    cap = capacity.can_validate(_active_validations(v))
    if not cap.get("ok"):
        result.update({"result": "BLOCKED", "reason": cap.get("reason") or "no validation slot",
                       "checks": {}})
        result["finished_at"] = datetime.now().isoformat()
        record(scope, project, result)
        return result
    changed = _changed_files(project_dir, resolved["sha"], resolved.get("merge_base") or "")
    result["changed_files"] = changed
    result["impact"] = _impact(changed)

    val_dir = project_dir
    wt = None
    if use_worktree and v.is_repo():
        wt = v.add_worktree(f"validate-{rid}", branch=f"validation/{rid}", base=resolved["sha"])
        if wt.get("ok"):
            val_dir = wt["path"]

    checks: dict[str, Any] = {}
    for name in [c for c in profile("FEATURE_PR")["checks"] if c != "target"] + ["close_loop"]:
        try:
            if name == "close_loop":
                checks[name] = _check_close_loop(val_dir, rid)
            else:
                fn = _CHECKERS.get(name)
                checks[name] = fn(project, val_dir, rid) if fn else \
                    {"status": "unknown", "detail": "no checker"}
        except Exception as e:
            checks[name] = {"status": "unknown", "detail": f"error: {type(e).__name__}"}

    try:
        from core import github
        checks["github_evidence"] = {"status": "pass", "detail": github.build_evidence(
            project, val_dir, run_id=rid, base_sha=resolved.get("base_sha", ""), head_sha=resolved["sha"])}
    except Exception as e:
        checks["github_evidence"] = {"status": "unknown", "detail": type(e).__name__}
    try:
        from core import pr_gate
        cm = pr_gate.can_merge(project, val_dir)
        checks["pr_merge"] = {"status": "pass" if cm.get("can_merge") else "fail",
                              "detail": {"can_merge": cm.get("can_merge"), "unmet": cm.get("unmet", [])}}
    except Exception as e:
        checks["pr_merge"] = {"status": "unknown", "detail": type(e).__name__}

    statuses = [c.get("status") for c in checks.values()]
    if "fail" in statuses:
        verdict = "FAIL"
    elif all(s in ("pass", "skip") for s in statuses) and any(s == "pass" for s in statuses):
        verdict = "PASS"
    else:
        verdict = "BLOCKED"
    result.update({"checks": checks, "result": verdict, "validator_worktree": (wt or {}).get("path", ""),
                   "finished_at": datetime.now().isoformat()})

    # never modify the developer branch: remove the validation worktree + its branch
    if wt and wt.get("ok"):
        try:
            v.remove_worktree(wt["name"])
            v._git(["branch", "-D", f"validation/{rid}"])
        except Exception:
            pass

    # optional defect -> Issue handoff (RCCA/backlog linkage is the issue owner's job)
    if record_defects and verdict == "FAIL":
        try:
            from core import issues
            iscope = "project" if _norm_scope(scope) == "project" else "product_forge"
            issues.raise_issue(iscope, project or None, f"FEATURE_PR validation failed ({rid})",
                               kind="bug", severity="high", source="validation",
                               evidence=[{"run_id": rid, "changed_files": changed,
                                          "failed": [k for k, c in checks.items() if c.get("status") == "fail"]}])
        except Exception:
            pass

    record(scope, project, result)
    return result
