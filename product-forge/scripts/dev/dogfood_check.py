"""ENG-9 gate: DOGFOOD runs (dry) fail-closed and produce a final state.

Dry run on a temp repo must yield a defined state (never a false PASS), record baseline + steps; a non-repo must
be BLOCKED. Records to a scratch project scope (cleaned). Run: ``python scripts/dev/dogfood_check.py``.
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


def main() -> int:
    from core import dogfood

    proj = "_test_dogfood"
    store = os.path.join(_PRODUCTS, proj)
    _force_rmtree(store)
    tmp = tempfile.mkdtemp(prefix="pf-eng9-")
    nonrepo = tempfile.mkdtemp(prefix="pf-eng9-norepo-")
    try:
        _check(set(dogfood.STATES) == {"PASS", "PARTIAL_SUCCESS", "FAIL", "BLOCKED"}, "state model")

        # non-repo -> BLOCKED (fail-closed)
        bad = dogfood.run(proj, nonrepo, dry=True, scope="project")
        _check(bad.get("result") == "BLOCKED", f"non-repo -> BLOCKED (got {bad.get('result')})")

        # temp git repo -> dry run yields a defined non-PASS state, baseline ok, steps present
        subprocess.run(["git", "init", "-q"], cwd=tmp, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "t@local"], cwd=tmp, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, capture_output=True, text=True)
        with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as f:
            f.write("x\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp, capture_output=True, text=True)
        res = dogfood.run(proj, tmp, dry=True, scope="project")
        _check(res.get("result") in dogfood.STATES, "dry result is a defined state")
        _check(res.get("result") != "PASS", "dry run must not report PASS")
        _check((res.get("baseline") or {}).get("ok"), "baseline resolved")
        _check("steps" in res and res["steps"].get("pipeline", {}).get("status") == "dry-run", "dry pipeline step")
        _check(bool(res.get("run_id", "").startswith("dog-")), "run id minted")
    finally:
        _force_rmtree(tmp)
        _force_rmtree(nonrepo)
        _force_rmtree(store)

    if FAILS:
        print("dogfood: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("dogfood: OK (dry fail-closed states, baseline, steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
