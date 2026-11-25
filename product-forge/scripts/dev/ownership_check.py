"""Generic ownership/route-by-kind check for a design pack."""
from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402
import design_contract_check as dcc  # noqa: E402

CFG = ROOT / "config" / "ownership.json"


def _cfg() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8-sig"))


def _owner(path: str, owners: list[dict]) -> str:
    p = str(path or "").replace("\\", "/")
    hits = [o for o in owners if fnmatch(p, str(o.get("glob") or ""))]
    return str(max(hits, key=lambda o: len(str(o.get("glob")))).get("owner")) if hits else ""


def problems(item_id: str, item: dict | None = None) -> list[str]:
    if item is None:
        item = backlog.get_epic("product_forge", None, item_id)
    if not item:
        return [f"item not found: {item_id}"]
    if not dcc.enforced(item, dcc._cfg()):
        return []
    cfg = _cfg()
    owners = cfg.get("owners") or []
    routes = cfg.get("routes") or []
    bad = []
    pack = item.get("design_pack") or {}
    files = list(item.get("affected_files") or []) + list((pack.get("contracts") or {}).get("files") or [])
    for f in sorted(set(files)):
        if not _owner(str(f), owners):
            bad.append(f"no owner for file: {f}")
    trigger = str((pack.get("runtime_contract") or {}).get("trigger") or "")
    path = next((part for part in trigger.split() if part.startswith("/")), "")
    if path:
        hits = [r for r in routes if path.startswith(str(r.get("prefix") or ""))]
        if not hits:
            bad.append(f"no route owner for: {path}")
        else:
            owner = str(max(hits, key=lambda r: len(str(r.get("prefix")))).get("owner"))
            if files and owner and owner not in {_owner(f, owners) for f in files}:
                bad.append(f"route owner {owner} does not own the affected files")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ownership/route-by-kind check")
    ap.add_argument("--item", required=True)
    a = ap.parse_args(argv)
    bad = problems(a.item)
    if bad:
        print(f"ownership: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("ownership: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
