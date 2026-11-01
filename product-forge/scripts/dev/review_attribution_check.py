"""Require origin_class for findings from follow-up reviews."""
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
import review_ledger  # noqa: E402

CFG = ROOT / "config" / "review-attribution.json"


def problems(item: dict) -> list[str]:
    cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
    count = len(review_ledger.entries(item, "diff"))
    if count <= int(cfg.get("require_after_review_count") or 1):
        return []
    classes = {str(x) for x in (cfg.get("classes") or [])}
    bad = []
    for sig, d in ((item.get("review_dispositions") or {}).get("diff") or {}).items():
        if str((d or {}).get("status") or "").upper() == "PENDING":
            continue
        origin = str((d or {}).get("origin_class") or "")
        if origin not in classes:
            bad.append(f"{sig}: missing/invalid origin_class")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Review attribution check")
    ap.add_argument("--item", required=True)
    a = ap.parse_args(argv)
    it = backlog.get_epic("product_forge", None, a.item) or {}
    if not it:
        print(f"review-attribution: FAIL - item not found: {a.item}")
        return 2
    bad = problems(it)
    if bad:
        print(f"review-attribution: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("review-attribution: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
