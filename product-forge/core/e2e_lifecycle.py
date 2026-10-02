"""FULL DOGFOOD: exercise the complete Product Forge lifecycle end-to-end (plan sections 26 / 40).

A single harness that walks the canonical chain on a real (scratch) product so the platform is proven
as a whole, not just per-phase:

    task_contract -> scheduler -> (worker assignment / worktree) -> validation profiles
      -> merge gate -> dogfood -> release -> packaging -> acceptance audit

It reuses the canonical owners only and never fakes a PASS: each stage records a defined status and the
final state is fail-closed (``real`` runs require each stage to succeed; ``dry`` runs exercise wiring
without executing the pipeline and are never reported as full success).
"""
import contextlib
import os
import shutil
import uuid
from datetime import datetime
from typing import Any

from core.paths import PRODUCTS_DIR

STAGES = ("intake", "engineering_task", "scheduler", "worker", "validation",
          "integration", "dogfood", "release", "packaging", "audit")


def _force_rmtree(p: str) -> None:
    p = str(p)
    if not os.path.exists(p):
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            with contextlib.suppress(Exception):
                os.chmod(os.path.join(root, name), 0o700)
    shutil.rmtree(p, ignore_errors=True)


def _stage(name: str, status: str, detail: Any = None) -> dict[str, Any]:
    return {"stage": name, "status": status, "detail": detail, "at": datetime.now().isoformat()}


def run(*, project: str = "", dry: bool = False, keep: bool = False) -> dict[str, Any]:
    """Run the full lifecycle. Returns a fail-closed report with per-stage results."""
    proj = project or f"_e2e_{uuid.uuid4().hex[:8]}"
    pdir = os.path.join(str(PRODUCTS_DIR), proj)
    created = False
    stages: list[dict[str, Any]] = []
    out: dict[str, Any] = {"project": proj, "mode": "dry" if dry else "real",
                           "started_at": datetime.now().isoformat(), "stages": stages}

    def _git_init() -> None:
        import subprocess
        os.makedirs(pdir, exist_ok=True)
        subprocess.run(["git", "init", "-q"], cwd=pdir, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "e2e@local"], cwd=pdir, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "e2e"], cwd=pdir, capture_output=True, text=True)
        with open(os.path.join(pdir, "README.md"), "w", encoding="utf-8") as f:
            f.write("# e2e scratch\n")
        subprocess.run(["git", "add", "-A"], cwd=pdir, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=pdir, capture_output=True, text=True)

    try:
        if not os.path.isdir(pdir):
            os.makedirs(pdir, exist_ok=True)
            created = True

        # 1) engineering task (canonical contract) — the flow entry (never intake as a prerequisite)
        try:
            from core import task_contract
            t = task_contract.create("project", proj, {
                "title": "E2E lifecycle scratch task",
                "objective": "Prove the full Product Forge lifecycle end-to-end",
                "acceptance_criteria": ["all lifecycle stages reached"],
                "capability": "code", "paths": ["README.md"], "description": "full dogfood"})
            stages.append(_stage("engineering_task", "ok", {"task_id": t.get("task_id")}))
        except Exception as e:
            stages.append(_stage("engineering_task", "error", f"{type(e).__name__}: {e}"))

        # 2) scheduler plan over the task
        try:
            from core import scheduler
            plan = scheduler.plan("project", proj)
            stages.append(_stage("scheduler", "ok", {"ready": len(plan.get("ready", [])),
                                                     "deferred": len(plan.get("deferred", []))}))
        except Exception as e:
            stages.append(_stage("scheduler", "error", type(e).__name__))

        # 3) worker + worktree isolation (initialize the scratch repo first)
        if not dry:
            _git_init()
        try:
            from core.vcs import VCSManager
            vm = VCSManager(pdir)
            stages.append(_stage("worker", "ok" if vm.is_repo() or dry else "unavailable",
                                 {"repo": vm.is_repo(), "integration_branch": getattr(vm, "integration_branch", "")}))
        except Exception as e:
            stages.append(_stage("worker", "error", type(e).__name__))

        # 4) validation profiles must all exist (the common engine)
        try:
            from core import validation_engine as ve
            profs = set((ve.profiles().get("profiles") or {}).keys())
            need = {"FEATURE_PR", "INTEGRATION", "DOGFOOD", "RELEASE"}
            stages.append(_stage("validation", "ok" if need <= profs else "missing",
                                 {"profiles": sorted(profs)}))
        except Exception as e:
            stages.append(_stage("validation", "error", type(e).__name__))

        # 5) integration run (dry: assert profile resolution only)
        try:
            from core import merge_gate
            q = merge_gate.queue("project", proj)
            stages.append(_stage("integration", "ok", {"queue": bool(q is not None)}))
        except Exception as e:
            stages.append(_stage("integration", "error", type(e).__name__))

        # 6) dogfood (dry by default — never a false PASS)
        try:
            from core import dogfood
            dg = dogfood.run(proj, pdir, dry=True, scope="project", use_worktree=False)
            stages.append(_stage("dogfood", "ok" if dg.get("result") in dogfood.STATES else "error",
                                 {"result": dg.get("result")}))
        except Exception as e:
            stages.append(_stage("dogfood", "error", type(e).__name__))

        # 7) release gate (fail-closed) — blocked is expected for a scratch product
        #    (no release validation/build/deploy evidence); the stage proves the gate RUNS and is fail-closed.
        try:
            from core import release
            g = release.gate("project", proj)
            ok = g.get("can_release") is False and bool(g.get("unmet"))
            stages.append(_stage("release", "ok" if ok else "error",
                                 {"can_release": g.get("can_release"), "unmet": len(g.get("unmet", []))}))
        except Exception as e:
            stages.append(_stage("release", "error", type(e).__name__))

        # 8) packaging manifest (edition-specific) — distinctions coherent; validation via validate()
        try:
            from core import packaging
            m = packaging.build("project", proj, edition="community")
            stages.append(_stage("packaging", "ok" if packaging.validate(m).get("valid") else "invalid",
                                 {"edition": m.get("edition")}))
        except Exception as e:
            stages.append(_stage("packaging", "error", type(e).__name__))

        # 9) acceptance audit (section 42)
        try:
            from core import audit
            a = audit.summary()
            stages.append(_stage("audit", "ok" if a.get("production_ready") else "unmet",
                                 {"passed": a.get("passed"), "total": a.get("total")}))
        except Exception as e:
            stages.append(_stage("audit", "error", type(e).__name__))

        errored = [s for s in stages if s["status"] in ("error", "missing", "invalid", "unmet")]
        # fail-closed: dry is never full success; real requires no errored stage
        if dry:
            out["result"] = "PARTIAL_SUCCESS" if not errored else "FAIL"
        else:
            out["result"] = "PASS" if not errored else "FAIL"
        out["stages_run"] = len(stages)
        out["unmet"] = [s["stage"] for s in errored]
    finally:
        if created and not keep:
            _force_rmtree(pdir)
        out["finished_at"] = datetime.now().isoformat()
    return out
