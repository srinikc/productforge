"""Compute and validate a conservative BIIS tier from item risk surface."""
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
import design_contract_check as dcc  # noqa: E402

CFG = ROOT / "config" / "biis-tiers.json"


def enforced(item: dict) -> bool:
    cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
    if str(item.get("id") or "") in (cfg.get("enforce_items") or []):
        return True
    created = str(item.get("created_at") or "")[:10]
    start = str(cfg.get("enforce_from") or "")
    return bool(created and start and created >= start)


def _surface(item: dict) -> str:
    parts = list(item.get("affected_files") or []) + list(item.get("affected_components") or [])
    parts += list(item.get("in_scope") or [])
    parts += [str(item.get("title") or ""), str(item.get("objective") or "")]
    return " ".join(parts).lower()


def computed_tier(item: dict) -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
    s = _surface(item)
    if any(p in s for p in (cfg.get("tier3_patterns") or [])):
        return 3
    if any(p in s for p in (cfg.get("tier2_patterns") or [])):
        return 2
    return 1


def problems(item: dict) -> list[str]:
    if not enforced(item):
        return []
    cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
    want = computed_tier(item)
    got = item.get("tier")
    try:
        got = int(got or 0)
    except Exception:
        got = 0
    bad = []
    if got not in (1, 2, 3):
        bad.append("item.tier missing/invalid")
    elif got < want:
        bad.append(f"item tier {got} is below computed tier {want}")
    if not item.get("tier_reasons"):
        bad.append("item.tier_reasons missing")
    if not (cfg.get("tiers") or {}).get(str(want)):
        bad.append(f"unknown computed tier {want}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BIIS tier check")
    ap.add_argument("--item", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    it = backlog.get_epic("product_forge", None, a.item) or {}
    if not it:
        print(f"biis-tier: FAIL - item not found: {a.item}")
        return 2
    want = computed_tier(it)
    if a.apply:
        backlog.update("product_forge", None, a.item, tier=want,
                       tier_reasons=[f"computed from affected surface: tier {want}"])
        print(f"biis-tier: applied tier {want}")
        return 0
    bad = problems(it)
    if bad:
        print("biis-tier: FAIL")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("biis-tier: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
