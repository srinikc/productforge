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


def file_ids() -> set[str]:
    ids = set()
    for f in ITEMS.glob("*.json"):
        ids.add(json.loads(f.read_text(encoding="utf-8")).get("id"))
    return {i for i in ids if i}


def main() -> int:
    dsn = os.environ.get("PF_DB_DSN")
    if not dsn:
        print("PF_DB_DSN required", file=sys.stderr)
        return 2
    fids = file_ids()
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute("SELECT id FROM backlog_items")
        dids = {r[0] for r in cur.fetchall()}
    missing = sorted(fids - dids)
    extra = sorted(dids - fids)
    print(f"backlog parity: files={len(fids)} db={len(dids)} missing_in_db={len(missing)} extra_in_db={len(extra)}")
    if missing or extra:
        for i in missing[:10]:
            print(f"   missing_in_db: {i}")
        for i in extra[:10]:
            print(f"   extra_in_db: {i}")
        return 1
    print("backlog parity: OK (files == DB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
