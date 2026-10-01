"""ENG-4 gate: the worker runtime executes a task in an isolated worktree and normalizes the result.

Exercises, in an isolated temp repo: provider registry/availability, a successful command-provider run
(files changed + commit + PR_READY), a noop run (NEEDS_REVIEW), and a failing command (FAILED).
Run: ``python scripts/dev/worker_check.py`` (wired into precheck). Exit 1 on any failure.
"""
import os
import shutil
import subprocess
import sys
import tempfile

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _task(tid="TC-PF-0001"):
    return {"task_id": tid, "title": "add made.txt", "objective": "create made.txt",
            "status": "ready", "acceptance_criteria": ["made.txt exists"],
            "affected_components": ["cli"], "test_requirements": ["unit"], "branch_policy": {}}


def main() -> int:
    from core import worker

    names = {p["name"] for p in worker.available_providers()}
    _check({"noop", "human", "command", "opencode"} <= names, "provider registry complete")
    _check(any(p["name"] == "opencode" for p in worker.available_providers()), "opencode adapter present")

    tmp = tempfile.mkdtemp(prefix="pf-worker-")
    try:
        subprocess.run(["git", "init", "-q"], cwd=tmp, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "pf@local"], cwd=tmp, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Product Forge"], cwd=tmp, capture_output=True, text=True)
        with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as f:
            f.write("init\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp, capture_output=True, text=True)

        good = [sys.executable, "-c", "open('made.txt','w').write('hi')"]
        r = worker.run_task(_task(), tmp, provider="command", command=good, commit=True)
        _check(r.status == "PR_READY", f"command run PR_READY (got {r.status}: {r.error})")
        _check(bool(r.final_commit), "final commit recorded")
        _check("made.txt" in r.files_changed, f"files_changed includes made.txt ({r.files_changed})")
        _check(r.branch.startswith("feature/"), f"feature branch ({r.branch})")
        _check("ASSIGNED" in r.lifecycle and "WORKING" in r.lifecycle, "lifecycle traversed")
        _check(worker.contract_status_for(r.to_dict()) == "review", "result maps to contract status")

        r2 = worker.run_task(_task("TC-PF-0002"), tmp, provider="noop")
        _check(r2.status == "NEEDS_REVIEW", f"noop -> NEEDS_REVIEW (got {r2.status})")

        bad = [sys.executable, "-c", "import sys; sys.exit(3)"]
        r3 = worker.run_task(_task("TC-PF-0003"), tmp, provider="command", command=bad)
        _check(r3.status == "FAILED", f"failing command -> FAILED (got {r3.status})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        print("worker: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("worker: OK (providers, isolated run, PR_READY/NEEDS_REVIEW/FAILED, normalized result)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
