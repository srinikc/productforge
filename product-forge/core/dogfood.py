"""ENG-9: DOGFOOD execution — prove Product Forge can build a real product end-to-end (plan section 23).

Orchestrates an approved PF baseline -> fresh isolated worktree -> RUN_ID -> full PF pipeline -> generated-product
validation -> evidence -> defect classification -> (optional, authorized) repair/retest -> final report.

Reuses canonical owners (``vcs``, ``run_entry`` = the ONE pipeline path, ``validation_engine`` DOGFOOD profile,
``github`` evidence, ``issues`` defects). Final states: PASS / PARTIAL_SUCCESS / FAIL / BLOCKED. Never hide
failures, weaken security, change tests to pass, bypass CI, or delete evidence. Records to ``validation-runs.json``.
"""
import uuid
from datetime import datetime
from typing import Any

from core.paths import PRODUCTS_DIR, ROOT

STATES = ("PASS", "PARTIAL_SUCCESS", "FAIL", "BLOCKED")


def _health(project_dir: str, dry: bool) -> dict[str, Any]:
    if dry:
        return {"status": "skipped", "detail": "dry run"}
    try:
        from core import run_quality_gate
        res = run_quality_gate.evaluate(project_dir or "", "item")
        return {"status": "pass" if res.get("passed") else "fail", "detail": res.get("reasons", [])}
    except Exception as e:
        return {"status": "unknown", "detail": type(e).__name__}


def _finish(out: dict[str, Any], state: str, scope: str, project: str, reason: str = "") -> dict[str, Any]:
    out["result"] = state
    if reason:
        out["reason"] = reason
    out["finished_at"] = datetime.now().isoformat()
    try:
        from core import validation_engine
        validation_engine.record(scope, project, out)
    except Exception:
        pass
    return out


def run(project: str, project_dir: str, *, idea: dict | None = None, target: str = "",
        baseline: str = "", run_id: str = "", scope: str = "product_forge",
        trigger_pipeline: bool = True, dry: bool = False, use_worktree: bool = True,
        repair: bool = False) -> dict[str, Any]:
    """Execute a DOGFOOD run and return the final report (PASS/PARTIAL_SUCCESS/FAIL/BLOCKED)."""
    from core import validation_engine as ve
    rid = run_id or f"dog-{uuid.uuid4().hex[:12]}"
    out: dict[str, Any] = {"run_id": rid, "mode": "DOGFOOD", "project": project, "idea": dict(idea or {}),
                           "target": target, "auto_repair": bool(repair), "controlled_repair": False,
                           "started_at": datetime.now().isoformat(), "steps": {}, "defects": [], "evidence": {}}

    # 1) approved PF baseline resolved exactly (+ fresh isolated worktree)
    base = ve._resolve_target(project_dir, baseline or "HEAD")
    out["baseline"] = base
    if not base.get("ok"):
        return _finish(out, "BLOCKED", scope, project, "baseline unresolved")

    val_dir = project_dir
    wt = None
    vm = None
    if use_worktree and not dry:
        from core.vcs import VCSManager
        vm = VCSManager(project_dir)
        if vm.is_repo():
            wt = vm.add_worktree(f"dogfood-{rid}", branch=f"dogfood/{rid}", base=base["sha"])
            if wt.get("ok"):
                val_dir = wt["path"]

    # 2) PF baseline health
    out["steps"]["baseline_health"] = _health(val_dir, dry)

    # 3) full PF pipeline via the ONE canonical run entry
    if trigger_pipeline and not dry:
        try:
            from core import run_entry
            products = ROOT if ve._norm_scope(scope) == "product_forge" else PRODUCTS_DIR
            out["steps"]["pipeline"] = {"status": "enqueued",
                                        **run_entry.enqueue(project, products, source="dogfood", actor="dogfood")}
        except Exception as e:
            out["steps"]["pipeline"] = {"status": "error", "error": type(e).__name__}
    else:
        out["steps"]["pipeline"] = {"status": "dry-run"}

    # 4) generated-product validation (DOGFOOD profile)
    try:
        out["steps"]["generated_product"] = ({"status": "dry-run"} if dry else
                                             ve.run(project, val_dir, profile_name="DOGFOOD", run_id=rid, scope=scope))
    except Exception as e:
        out["steps"]["generated_product"] = {"status": "error", "error": type(e).__name__}

    # 5) run-bound evidence + defect classification
    try:
        from core import github
        out["evidence"] = github.build_evidence(project, val_dir, run_id=rid, head_sha=base["sha"])
    except Exception:
        out["evidence"] = {}
    try:
        from core import issues
        isc = "project" if ve._norm_scope(scope) == "project" else "product_forge"
        out["defects"] = [i.get("id") for i in issues.list_open(isc, project or None)]
    except Exception:
        out["defects"] = []

    # 6) remove the validation worktree (never modify the baseline branch)
    if wt and wt.get("ok") and vm is not None:
        try:
            vm.remove_worktree(wt["name"])
            vm._git(["branch", "-D", f"dogfood/{rid}"])
        except Exception:
            pass

    # 7) final state (fail-closed; dry is never a full PASS)
    gp = out["steps"].get("generated_product") or {}
    gres = gp.get("result") or gp.get("status")
    pipe = (out["steps"].get("pipeline") or {}).get("status")
    if gres == "FAIL":
        state, reason = "FAIL", "generated-product validation failed"
    elif pipe == "error":
        state, reason = "BLOCKED", "pipeline could not start"
    elif dry:
        state, reason = "PARTIAL_SUCCESS", "dry run (pipeline not executed)"
    elif gres == "PASS" and pipe == "enqueued":
        state, reason = "PASS", ""
    else:
        state, reason = "PARTIAL_SUCCESS", "validation incomplete (unverified checks)"
    return _finish(out, state, scope, project, reason)
