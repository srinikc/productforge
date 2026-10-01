"""ENG-1 gate: the engineering task-contract schema is valid and exercised.

Checks ``core.task_contract`` directly (no store writes): incomplete contracts are rejected; a valid contract
passes; ``normalize`` fills every conceptual field (plan §13). Run: ``python scripts/dev/task_contract_check.py``
(wired into precheck). Exit 1 on any failure.
"""
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    from core import task_contract
    fails = []

    if task_contract.validate({"title": "x"})["ok"]:
        fails.append("incomplete contract wrongly accepted")
    good = {"title": "t", "objective": "o", "acceptance_criteria": ["a"]}
    res = task_contract.validate(good)
    if not res["ok"]:
        fails.append(f"valid contract rejected: {res['errors']}")

    norm = task_contract.normalize(good)
    missing = [f for f in task_contract.FIELDS if f not in norm]
    if missing:
        fails.append(f"normalize missing fields: {missing}")

    if fails:
        print("task-contract: FAIL")
        for f in fails:
            print("   -", f)
        return 1
    print(f"task-contract: OK ({len(task_contract.FIELDS)} contract fields)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
