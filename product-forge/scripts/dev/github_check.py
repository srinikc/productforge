"""ENG-5 gate: PR orchestration + evidence + guards (no network required).

Exercises, in isolated temp repos: adapter availability + degradation, run-bound evidence assembly, PR record
roundtrip, and the guards (refuse PR from a protected branch; refuse a non-repo). Run:
``python scripts/dev/github_check.py`` (wired into precheck). Exit 1 on any failure.
"""
import os
import shutil
import subprocess
import sys
import tempfile

try:
    from core.paths import PRODUCTS_DIR as _PRODUCTS
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _PRODUCTS = os.path.join(_ROOT, "products")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []
_REQUIRED = ("run_id", "task_id", "commit_sha", "base_sha", "tests", "validation",
             "security", "issues", "rcca", "backlog", "artifacts")


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _force_rmtree(p):
    p = str(p)
    if not os.path.exists(p):
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o700)
            except Exception:
                pass
    shutil.rmtree(p, ignore_errors=True)


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def main() -> int:
    from core import github

    _check(isinstance(github.available().get("gh"), bool), "available() reports gh availability")
    _check(bool(github.POLICY), "POLICY (never-list) present")

    scratch = os.path.join(_PRODUCTS, "_test_github")
    _force_rmtree(scratch)
    tmp = tempfile.mkdtemp(prefix="pf-github-")
    try:
        _git(tmp, "init", "-q")
        _git(tmp, "config", "user.email", "pf@local")
        _git(tmp, "config", "user.name", "Product Forge")
        with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as f:
            f.write("init\n")
        _git(tmp, "add", "-A")
        _git(tmp, "commit", "-q", "-m", "init")
        _git(tmp, "checkout", "-q", "-b", "feature/tc-pf-0001")

        ev = github.build_evidence("_test_github", tmp, run_id="run-x", task_id="TC-PF-0001")
        missing = [k for k in _REQUIRED if k not in ev]
        _check(not missing, f"evidence missing keys: {missing}")

        ci = github.ci_status(tmp, "")
        _check("available" in ci, "ci_status reports adapter availability")

        res = github.create_pr("_test_github", tmp, title="t", head="feature/tc-pf-0001",
                               task_id="TC-PF-0001", run_id="run-x", scope="project")
        _check(res.get("ok"), f"create_pr ok: {res.get('error')}")
        if res.get("ok"):
            _check(github.list_prs("project", "_test_github"), "PR record stored")
            n = (res.get("pr") or {}).get("number")
            if n:
                _check(github.get_pr("project", "_test_github", n) is not None, "get_pr by number")
            _check(bool((res.get("pr") or {}).get("evidence_hash")), "evidence hash recorded")

        refused = github.create_pr("_test_github", tmp, title="t", head="develop", scope="project")
        _check(refused.get("ok") is False, "guards: refuse PR from protected branch")

        empty = tempfile.mkdtemp(prefix="pf-norepo-")
        try:
            norepo = github.create_pr("_test_github", empty, title="t", scope="project")
            _check(norepo.get("ok") is False, "guards: refuse non-repo")
        finally:
            _force_rmtree(empty)
    finally:
        _force_rmtree(tmp)
        _force_rmtree(scratch)

    if FAILS:
        print("github: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("github: OK (adapter, evidence, PR record, guards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
