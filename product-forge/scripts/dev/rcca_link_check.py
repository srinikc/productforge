"""Require an RCCA link when an item is marked as a bug/incident correction."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402


def problems(item: dict) -> list[str]:
    kind = str(item.get("type") or "").lower()
    if kind not in ("bug", "incident", "defect") and not item.get("rcca_required"):
        return []
    links = item.get("links") or {}
    if not (item.get("rcca") or links.get("rcca") or links.get("rcca_ref")):
        return ["RCCA link missing for bug/incident item"]
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="RCCA link check")
    ap.add_argument("--item", required=True)
    a = ap.parse_args(argv)
    it = backlog.get_epic("product_forge", None, a.item) or {}
    if not it:
        print(f"rcca-link: FAIL - item not found: {a.item}")
        return 2
    bad = problems(it)
    if bad:
        print("rcca-link: FAIL")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("rcca-link: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
