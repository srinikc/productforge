"""ENG-6 gate: the Common Validation Engine runs profiles by composing existing validators.

Deterministic (no store writes to shared scopes): a scratch project dir is created. Exercises: profile
registry, target resolution on a git repo, BLOCKED on a non-repo, and a full FEATURE_PR run on a scratch repo
(result must be PASS/FAIL/BLOCKED, fail-closed). Run: ``python scripts/dev/validation_engine_check.py``.
"""
import contextlib
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


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _force_rmtree(p):
    p = str(p)
    if not os.path.exists(p):
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            with contextlib.suppress(Exception):
                os.chmod(os.path.join(root, name), 0o700)
    shutil.rmtree(p, ignore_errors=True)


def _git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)


def main() -> int:
    from core import validation_engine as ve

    profs = ve.profiles().get("profiles") or {}
    _check({"FEATURE_PR", "INTEGRATION", "DOGFOOD", "RELEASE"} <= set(profs), "all 4 profiles present")
    _check(ve.profile("feature_pr")["name"] == "FEATURE_PR", "profile lookup case-insensitive")

    scratch = os.path.join(_PRODUCTS, "_test_validation_engine")
    _force_rmtree(scratch)
    nonrepo = tempfile.mkdtemp(prefix="pf-val-norepo-")
    try:
        # non-repo -> BLOCKED (fail-closed)
        res = ve.run("_test_validation_engine", nonrepo, profile_name="FEATURE_PR", scope="project")
        _check(res.get("result") == "BLOCKED", f"non-repo -> BLOCKED (got {res.get('result')})")

        # git repo -> resolves target and returns a defined result
        os.makedirs(scratch, exist_ok=True)
        _git(scratch, "init", "-q")
        _git(scratch, "config", "user.email", "t@local")
        _git(scratch, "config", "user.name", "t")
        with open(os.path.join(scratch, "README.md"), "w", encoding="utf-8") as f:
            f.write("x\n")
        _git(scratch, "add", "-A")
        _git(scratch, "commit", "-q", "-m", "init")
        res = ve.run("_test_validation_engine", scratch, profile_name="FEATURE_PR", scope="project")
        _check(res.get("result") in ("PASS", "FAIL", "BLOCKED"), "run result is a defined verdict")
        _check((res.get("target_resolved") or {}).get("ok"), "target resolved on a repo")
        _check("checks" in res, "per-check results present")
    finally:
        _force_rmtree(nonrepo)
        _force_rmtree(scratch)

    if FAILS:
        print("validation-engine: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("validation-engine: OK (profiles, target resolution, fail-closed result)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
