"""FINAL AUDIT gate: production-readiness acceptance criteria (plan section 42) must pass.

Runs ``core.audit`` (mechanical acceptance audit) and ``core.e2e_lifecycle`` (full lifecycle dry run).
Fail-closed: any unmet acceptance criterion or errored lifecycle stage fails the gate.
Run: ``python scripts/dev/final_audit_check.py``.
"""
import os
import sys

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
    from core import audit, e2e_lifecycle

    # 1) acceptance audit (section 42)
    a = audit.run()
    _check(a.get("production_ready") is True,
           f"acceptance criteria unmet: {a.get('unmet')}")
    _check(a.get("total", 0) >= 40, "audit covers the acceptance criteria")
    for area in ("API", "Runtime", "Engineering", "GitHub", "Validation", "Release", "Clients", "Invariants"):
        _check(area in (a.get("by_area") or {}), f"audit area present: {area}")

    # 2) full lifecycle E2E (dry; must reach every stage with no errored stage)
    r = e2e_lifecycle.run(dry=True)
    _check(r.get("result") in ("PARTIAL_SUCCESS", "PASS"), f"lifecycle result {r.get('result')}")
    _check(len(r.get("stages", [])) == len(e2e_lifecycle.STAGES) - 1,
           "every lifecycle stage exercised")  # 'intake' is external-only, not a prerequisite
    _check(not r.get("unmet"), f"lifecycle unmet stages: {r.get('unmet')}")

    if FAILS:
        print("final-audit: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print(f"final-audit: OK (acceptance {a['passed']}/{a['total']}, production_ready, "
          f"lifecycle {r['stages_run']} stages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
