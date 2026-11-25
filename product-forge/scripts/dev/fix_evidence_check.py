"""Validate fix evidence before a delta re-review."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402

ATTR = ROOT / "config" / "review-attribution.json"
REQUIRED = ("finding_sig", "origin_class", "regression_test", "controls_rerun", "result", "evidence")


def problems(item: dict) -> list[str]:
    classes = {str(x) for x in json.loads(ATTR.read_text(encoding="utf-8-sig")).get("classes", [])}
    fixes = item.get("fix_evidence") or []
    if not fixes:
        return ["fix_evidence missing"]
    bad = []
    for i, f in enumerate(fixes, 1):
        if not isinstance(f, dict):
            bad.append(f"fix_evidence[{i}] must be an object")
            continue
        for key in REQUIRED:
            if not f.get(key):
                bad.append(f"fix_evidence[{i}].{key} missing")
        if str(f.get("origin_class") or "") not in classes:
            bad.append(f"fix_evidence[{i}] invalid origin_class")
        if f.get("controls_rerun") and not isinstance(f.get("controls_rerun"), list):
            bad.append(f"fix_evidence[{i}].controls_rerun must be a list")
        if str(f.get("result") or "").upper() != "PASS":
            bad.append(f"fix_evidence[{i}] result is not PASS")
        ev = str(f.get("evidence") or "")
        if ev and not (ROOT / ev).exists():
            bad.append(f"fix_evidence[{i}] evidence not found: {ev}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fix evidence check")
    ap.add_argument("--item", required=True)
    a = ap.parse_args(argv)
    it = backlog.get_epic("product_forge", None, a.item) or {}
    if not it:
        print(f"fix-evidence: FAIL - item not found: {a.item}")
        return 2
    bad = problems(it)
    if bad:
        print("fix-evidence: FAIL")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("fix-evidence: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
