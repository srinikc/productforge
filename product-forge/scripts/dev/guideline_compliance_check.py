"""Validate guideline coverage/review scope for an item, including evidence references."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402
import design_contract_check as dcc  # noqa: E402


def problems(item_id: str, item: dict | None = None) -> list[str]:
    if item is None:
        item = backlog.get_epic("product_forge", None, item_id)
    if not item:
        return [f"item not found: {item_id}"]
    return [p for p in dcc.problems(item_id, item)
            if "guideline" in p.lower() or "review_scope" in p.lower()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Guideline compliance check")
    ap.add_argument("--item", required=True)
    a = ap.parse_args(argv)
    bad = problems(a.item)
    if bad:
        print(f"guideline-compliance: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("guideline-compliance: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
