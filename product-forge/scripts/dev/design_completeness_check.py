"""Fail a design that omits required engineering dimensions."""
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

CFG = ROOT / "config" / "design-completeness.json"


def _missing(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def problems(item_id: str, item: dict | None = None) -> list[str]:
    if item is None:
        item = backlog.get_epic("product_forge", None, item_id)
    if not item:
        return [f"item not found: {item_id}"]
    if not dcc.enforced(item, dcc._cfg()):
        return []
    cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
    pack = item.get("design_pack") or {}
    bad = []
    for dim in cfg.get("required_dimensions") or []:
        value = pack.get(dim, item.get(dim))
        if _missing(value) and dim not in (cfg.get("allow_empty") or []):
            bad.append(f"missing design dimension: {dim}")
    tokens = [str(x).lower() for x in (cfg.get("placeholder_tokens") or [])]
    for src_name, src in (("design_pack", pack), ("item", item)):
        for key in ("risks",):
            if key in src:
                for s in dcc._iter_strings(src[key]):
                    if any(t in s.lower() for t in tokens):
                        bad.append(f"placeholder in {src_name}.{key}")
    return sorted(set(bad))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Design completeness check")
    ap.add_argument("--item", required=True)
    a = ap.parse_args(argv)
    bad = problems(a.item)
    if bad:
        print(f"design-completeness: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("design-completeness: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
