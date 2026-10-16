"""BI-PF-1399 cutover step: files <-> DB parity for the backlog.

Compares the canonical file backlog (``data/backlog/items/*.json``) against the ``backlog_items`` table.
Reports missing/extra ids and a count parity. Exit 1 on any drift. Prereq: EDP-18 migration applied.

Usage: PF_DB_DSN=... python scripts/dev/backlog_db_parity.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "backlog" / "items"


def file_items() -> dict[str, dict]:
    out = {}
    for f in ITEMS.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("id"):
            out[d["id"]] = d
    return out


def file_ids() -> set[str]:
    return set(file_items().keys())


def main() -> int:
    dsn = os.environ.get("PF_DB_DSN")
    if not dsn:
        print("PF_DB_DSN required", file=sys.stderr)
        return 2
    fitems = file_items()
    fids = set(fitems)
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute("SELECT id, data FROM backlog_items")
        drows = {r[0]: r[1] for r in cur.fetchall()}
    missing = sorted(fids - set(drows))
    extra = sorted(set(drows) - fids)
    mism = [i for i in sorted(fids & set(drows)) if drows[i] != fitems[i]]
    print(f"backlog parity: files={len(fids)} db={len(drows)} missing_in_db={len(missing)} "
          f"extra_in_db={len(extra)} data_mismatch={len(mism)}")
    if missing or extra or mism:
        for i in missing[:10]:
            print(f"   missing_in_db: {i}")
        for i in extra[:10]:
            print(f"   extra_in_db: {i}")
        for i in mism[:10]:
            print(f"   data_mismatch: {i}")
        return 1
    print("backlog parity: OK (files == DB, full item data)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
