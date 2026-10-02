"""ENG-7 gate: FEATURE_PR validates an exact commit in a FRESH worktree without modifying the dev branch.

Builds a temp repo (base + a feature commit), runs ``validation_engine.feature_pr`` and asserts: a defined
verdict, changed-file detection, worktree isolation (developer branch HEAD unchanged), and worktree cleanup.
Run: ``python scripts/dev/feature_pr_check.py`` (wired into precheck).
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

    scratch = os.path.join(_PRODUCTS, "_test_feature_pr")
    wtroot = os.path.join(_PRODUCTS, "_test_feature_pr-worktrees")
    for p in (wtroot, scratch):
        _force_rmtree(p)

    tmp = tempfile.mkdtemp(prefix="pf-eng7-")
    try:
        _git(tmp, "init", "-q")
        _git(tmp, "config", "user.email", "t@local")
        _git(tmp, "config", "user.name", "t")
        with open(os.path.join(tmp, "base.txt"), "w", encoding="utf-8") as f:
            f.write("base\n")
        _git(tmp, "add", "-A")
        _git(tmp, "commit", "-q", "-m", "base")
        _git(tmp, "checkout", "-q", "-b", "feature/x")
        with open(os.path.join(tmp, "changed.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        _git(tmp, "add", "-A")
        _git(tmp, "commit", "-q", "-m", "change")
        head_before = _git(tmp, "rev-parse", "HEAD").stdout.strip()

        res = ve.feature_pr("_test_feature_pr", tmp, target="HEAD", scope="project")
        _check(res.get("result") in ("PASS", "FAIL", "BLOCKED"), "defined verdict")
        _check("changed.py" in (res.get("changed_files") or []), "detects changed file")
        _check((res.get("impact") or {}).get("changed_count", 0) >= 1, "impact analysis")
        _check("github_evidence" in (res.get("checks") or {}), "github evidence assembled")
        head_after = _git(tmp, "rev-parse", "HEAD").stdout.strip()
        _check(head_before == head_after, "developer branch HEAD unchanged")
        # validation worktree cleaned up (no residue under the product's worktree root)
        _check(not os.path.isdir(wtroot), "validation worktree removed")
    finally:
        _force_rmtree(tmp)
        _force_rmtree(wtroot)
        _force_rmtree(scratch)

    if FAILS:
        print("feature-pr: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("feature-pr: OK (exact SHA, changed-file/impact, worktree isolation, evidence, cleanup)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
