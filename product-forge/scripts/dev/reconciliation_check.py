"""PF RECONCILIATION block advisory check (P4 — BI-PF-XXXX).

Checks whether engineering/designs/<item>.md exists and contains all five required
RECONCILIATION sections. Advisory-only: exits 0 (warn) so it never hard-blocks precheck
for legacy items. Only items in in_progress/implemented/verifying are checked.

Required sections:
  PRIOR DECISIONS / EXISTING PATH / ASSUMPTIONS / DIVERGENCES / OPEN QUESTIONS

Usage:
  python scripts/dev/reconciliation_check.py              # check all in-flight items
  python scripts/dev/reconciliation_check.py --item BI-PF-1234
  python scripts/dev/reconciliation_check.py --strict     # exit 1 on missing (CI-ready)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGNS_DIR = ROOT / "engineering" / "designs"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_SECTIONS = [
    "PRIOR DECISIONS",
    "EXISTING PATH",
    "ASSUMPTIONS",
    "DIVERGENCES",
    "OPEN QUESTIONS",
]

IN_FLIGHT_STATUSES = {"in_progress", "implemented", "verifying"}


def _get_in_flight_items() -> list[dict]:
    try:
        from core import backlog as _b
        items = _b.load_all("product_forge") or []
        return [i for i in items if i.get("status") in IN_FLIGHT_STATUSES]
    except Exception as e:
        print(f"  [warn] Could not load backlog: {e}", file=sys.stderr)
        return []


def _get_item(item_id: str) -> dict:
    try:
        from core import backlog as _b
        return _b.get_epic("product_forge", None, item_id) or {}
    except Exception:
        return {"external_id": item_id, "status": "unknown"}


def _check_item(item_id: str, strict: bool) -> tuple[bool, list[str]]:
    """Returns (ok, missing_sections)."""
    # Look for the design doc
    candidates = [
        DESIGNS_DIR / f"{item_id}.md",
        DESIGNS_DIR / f"{item_id.lower()}.md",
        DESIGNS_DIR / f"{item_id.upper()}.md",
    ]
    doc_path = None
    for c in candidates:
        if c.exists():
            doc_path = c
            break

    if doc_path is None:
        return False, ["[no design doc found]"]

    try:
        text = doc_path.read_text(encoding="utf-8", errors="replace").upper()
    except Exception as e:
        return False, [f"[cannot read {doc_path.name}: {e}]"]

    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    return len(missing) == 0, missing


def _print_result(item_id: str, ok: bool, missing: list[str], strict: bool) -> None:
    if ok:
        print(f"  [OK   ] {item_id}: RECONCILIATION block complete (all 5 sections present)")
    else:
        level = "[FAIL ]" if strict else "[WARN ]"
        print(f"  {level} {item_id}: RECONCILIATION block incomplete")
        for m in missing:
            print(f"           missing: {m}")
        if not strict:
            print(f"           hint: create engineering/designs/{item_id}.md with all 5 sections")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="PF RECONCILIATION block advisory check (P4)"
    )
    ap.add_argument("--item", default="", help="Check a specific item (default: all in-flight)")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 on missing RECONCILIATION (default: advisory/exit 0)")
    a = ap.parse_args(argv)

    print("reconciliation-check: verifying RECONCILIATION blocks for in-flight items\n")

    if a.item:
        items = [_get_item(a.item)]
        item_ids = [a.item]
    else:
        items = _get_in_flight_items()
        item_ids = [i.get("external_id") or i.get("id", "?") for i in items]

    if not item_ids:
        print("  No in-flight items to check.")
        return 0

    failures = []
    for item_id in item_ids:
        ok, missing = _check_item(item_id, a.strict)
        _print_result(item_id, ok, missing, a.strict)
        if not ok:
            failures.append(item_id)

    print()
    if failures:
        if a.strict:
            print(f"reconciliation-check: FAIL — {len(failures)} item(s) missing RECONCILIATION block")
            print("  Add engineering/designs/<item>.md with sections:")
            for s in REQUIRED_SECTIONS:
                print(f"    ## {s}")
            return 1
        else:
            print(f"reconciliation-check: ADVISORY — {len(failures)} item(s) missing RECONCILIATION block")
            print("  (non-blocking; use --strict to enforce)")
            return 0
    else:
        print(f"reconciliation-check: OK — all {len(item_ids)} item(s) have complete RECONCILIATION blocks")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
