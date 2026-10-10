"""Gate (BI-PF-1250): every NEW open item must belong to an epic (baseline-aware).

Epics are containers (exempt). Items that were already open when the rule was introduced are grandfathered
(``_BASELINE``). Any NEW open non-epic item with no ``epic``/``parent`` FAILS. The ``Unscoped`` holding epic
counts as an epic (automated creators attach to it). Scope: ``product_forge`` (generated-product backlogs are
already Feature->Epic structured; transient scratch scopes are excluded).

Run from product-forge/. Exit 0 = ok, 1 = new unparented item(s).
"""
import os
import sys

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from core import backlog  # noqa: E402

# grandfathered open items without an epic at introduction time (BI-PF-1250)
_BASELINE = {
    "BI-0185", "BI-0195", "BI-0206", "BI-0208", "BI-0209", "BI-0218", "BI-0220", "BI-0225",
    "BI-PF-0331", "BI-PF-0332", "BI-PF-0408", "BI-PF-1223", "BI-PF-1225", "BI-PF-1236",
    "BI-PF-1237", "BI-PF-1240", "BI-PF-1241",
}


def main() -> int:
    warns = backlog.epic_coverage_warnings("product_forge", None)
    new = [w for w in warns if str(w.get("item")) not in _BASELINE]
    if new:
        print(f"backlog-epic: FAIL - {len(new)} NEW open item(s) with no epic:")
        for w in new[:25]:
            print(f"   - {w['ref']}: {str(w.get('title') or '')[:90]}")
        print("   attach each to an epic, or to the 'Unscoped' holding epic; see AGENTS.md "
              "(every item needs an epic)")
        return 1
    print(f"backlog-epic: OK (0 new unparented items; {len(warns)} grandfathered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
