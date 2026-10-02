"""ENG-10 gate: the release gate is fail-closed and never falsely green.

A repo with no build/BOM/RELEASE-validation/deployment/merge-gate evidence must be BLOCKED (can_release False),
and every checklist item must be present. Records release evidence to a scratch project scope (cleaned).
Run: ``python scripts/dev/release_check.py``.
"""
import contextlib
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
_REQUIRED = {"release_validation", "build", "packaging_bom", "deployment", "merge_gate"}


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
    from core import release

    # 1) fail-closed on an empty candidate
    tmp = tempfile.mkdtemp(prefix="pf-eng10-")
    try:
        g = release.gate("project", os.path.basename(tmp))
        _check(set(g.get("items") or {}), "checklist has items")
        _check(_REQUIRED.issubset(set(g.get("items") or {})), "required items present")
        _check(g.get("can_release") is False, "empty candidate cannot release")
        _check(g.get("decision") == "blocked", "empty candidate decision blocked")
        _check(bool(g.get("unmet")), "unmet items reported")

        # 2) an unmet required item flips readiness to blocked
        r = release.readiness("project", os.path.basename(tmp))
        _check(r.get("can_release") is False, "readiness blocked")

        # 3) evidence round-trips without duplicating a store (read the file directly: the
        #    scratch project's evidence lands in its own project dir, not the product-forge log)
        import json as _json
        ev_path = release.record_evidence(g)
        with open(ev_path, encoding="utf-8") as f:
            rows = [_json.loads(ln) for ln in f if ln.strip()]
        _check(rows and rows[-1].get("decision") == "blocked", "evidence records the decision")

        # 4) statuses are a closed set (no accidental 'pass' default)
        allowed = {"pass", "fail", "unknown", "skip"}
        for k, v in (g.get("items") or {}).items():
            _check(v.get("status") in allowed, f"item {k} status in {allowed}")
    finally:
        _force_rmtree(tmp)

    if FAILS:
        print("release: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("release: OK (fail-closed gate, checklist items, evidence)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
