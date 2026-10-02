"""ENG-8 gate: merge enforcement is fail-closed.

A scratch project with no pr_gate/validation evidence must NOT be mergeable; the gate reports both checks.
Run: ``python scripts/dev/merge_gate_check.py`` (wired into precheck).
"""
import os
import shutil
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


def main() -> int:
    from core import merge_gate

    scratch = tempfile.mkdtemp(prefix="pf-mergegate-")
    try:
        res = merge_gate.evaluate("_test_merge_gate", scratch, scope="project")
        _check("pr_gate" in res.get("checks", {}), "pr_gate check present")
        _check("validation" in res.get("checks", {}), "validation check present")
        _check(res.get("can_merge") is False, "no evidence -> merge blocked (fail-closed)")
        _check(bool(res.get("unmet")), "unmet list reported")
        _check(isinstance(merge_gate.queue("product_forge"), list), "queue returns a list")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if FAILS:
        print("merge-gate: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("merge-gate: OK (fail-closed; pr_gate + validation required)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
