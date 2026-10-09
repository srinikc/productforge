"""BI-PF-0458 gate: DOGFOOD Phase 1 (API auto-dogfood).

Asserts ``core.dogfood_run``: ``start`` seeds the project (idea + auto + tier) and enqueues via ``run_entry``;
``status`` aggregates; ``assert_delivery`` is fail-closed. Also wires the module on the tooling path.
Run: ``python scripts/dev/dogfood_run_check.py``.
"""
import os
import shutil
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


def main() -> int:
    from core import dogfood_run, run_entry

    tmp = tempfile.mkdtemp(prefix="pf-dogfood-run-")
    try:
        orig = run_entry.enqueue
        run_entry.enqueue = lambda project, products_dir="products", tier="", **kw: {"run_id": "run-check-1"}
        try:
            res = dogfood_run.start("a tiny idea", "_test_dogfood_run", tier="kctier", products_dir=tmp)
        finally:
            run_entry.enqueue = orig
        _check(res.get("run_id") == "run-check-1", "start returns run_id")
        _check(res.get("tier") == "kctier", "tier propagated")

        st = dogfood_run.status("_test_dogfood_run", products_dir=tmp)
        _check(all(k in st for k in ("delivery", "events", "log_tail", "defects", "validation")),
               "status aggregates")

        empty = os.path.join(tmp, "empty")
        os.makedirs(empty, exist_ok=True)
        _check(dogfood_run.assert_delivery(empty).get("delivered") is False, "delivery fail-closed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        print("dogfood-run: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("dogfood-run: OK (start seed+enqueue, status aggregate, delivery fail-closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
