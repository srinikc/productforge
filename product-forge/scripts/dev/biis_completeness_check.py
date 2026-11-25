"""BIIS completeness: same dimensions for every tier; N/A needs a rationale."""
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
import design_completeness_check as dcc  # noqa: E402

CFG = ROOT / "config" / "biis-tiers.json"


def enforced(item: dict) -> bool:
    cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
    if str(item.get("id") or "") in (cfg.get("enforce_items") or []):
        return True
    created = str(item.get("created_at") or "")[:10]
    start = str(cfg.get("enforce_from") or "")
    return bool(created and start and created >= start)


def problems(item: dict) -> list[str]:
    if not enforced(item):
        return []
    bad = dcc.problems(str(item.get("id") or ""), item)
    tier = item.get("tier")
    if tier not in (1, 2, 3):
        bad.append("item.tier missing/invalid")
    if not item.get("tier_reasons"):
        bad.append("item.tier_reasons missing")
    na = list(item.get("na_register") or [])
    for row in na:
        for key in ("dimension", "rationale", "owner"):
            if not row.get(key):
                bad.append(f"na_register missing {key}")
    # A dimension explicitly marked N/A must have an approved register row.
    pack = item.get("design_pack") or {}
    for dim in (json.loads(CFG.read_text(encoding="utf-8-sig")).get("universal_dimensions") or []):
        value = str(pack.get(dim, item.get(dim)) or "").strip().lower()
        if value in ("n/a", "na", "not applicable"):
            if not any(str(r.get("dimension")) == dim for r in na):
                bad.append(f"{dim} is N/A without na_register rationale")
    return sorted(set(bad))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BIIS completeness check")
    ap.add_argument("--item", required=True)
    a = ap.parse_args(argv)
    it = backlog.get_epic("product_forge", None, a.item) or {}
    if not it:
        print(f"biis-completeness: FAIL - item not found: {a.item}")
        return 2
    bad = problems(it)
    if bad:
        print(f"biis-completeness: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("biis-completeness: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
