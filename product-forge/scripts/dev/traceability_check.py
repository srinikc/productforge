"""BI-PF-1169 (E8) gate: a project's requirements traceability matrix must be complete.

For a project with a ``traceability.json`` matrix (REQ<->feature), every row must be ``implemented`` and
``tested`` (fail-closed); nothing to check -> OK. Reads the owner store (core/traceability.py). No dashboard.
Run: ``python scripts/dev/traceability_check.py <project_dir>``.
"""
import argparse
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import traceability as _trace  # noqa: E402


def evaluate(project_dir: str) -> dict:
    data = _trace._rj(os.path.join(project_dir, "traceability.json"), None)
    if not isinstance(data, dict):
        return {"ok": True, "skipped": "no traceability.json", "unmet": []}
    matrix = data.get("matrix") or []
    unmet = []
    for r in matrix:
        if not r.get("implemented"):
            unmet.append({"requirement": r.get("requirement_id"), "feature": r.get("feature_id"),
                          "gap": "not implemented"})
        elif not r.get("tested"):
            unmet.append({"requirement": r.get("requirement_id"), "feature": r.get("feature_id"),
                          "gap": "not tested"})
    return {"ok": not unmet, "rows": len(matrix), "unmet": unmet}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir")
    a = ap.parse_args(argv)
    res = evaluate(a.project_dir)
    if res.get("skipped"):
        print(f"traceability: SKIP ({res['skipped']})")
        return 0
    if not res["ok"]:
        print(f"traceability: FAIL ({len(res['unmet'])} untraced row(s) of {res['rows']})")
        for u in res["unmet"][:20]:
            print(f"   - {u['requirement']} / {u['feature']}: {u['gap']}")
        return 1
    print(f"traceability: OK ({res['rows']} requirement rows traced)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
