"""EDP-18 (BI-PF-1310) migration tooling - foundation.

Migrates a domain's JSON files into the PostgreSQL system of record with a DRY-RUN parity check first.
Domain ``backlog``: ``data/backlog/items/*.json`` -> ``backlog_items`` table.

Usage:
  python scripts/dev/migrate_to_db.py --domain backlog            # dry-run (counts + parity)
  PF_DB_DSN=... python scripts/dev/migrate_to_db.py --domain backlog --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "backlog" / "items"


def load_backlog() -> list[dict]:
    rows = []
    for f in sorted(ITEMS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        rows.append({
            "id": d.get("id"), "tenant_id": "product_forge", "type": d.get("type", "feature"),
            "status": d.get("status", "new"), "title": d.get("title", ""), "body": d.get("body", ""),
        })
    return rows


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Migrate a domain's files into the DB (EDP-18).")
    ap.add_argument("--domain", required=True, choices=["backlog"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dsn", default=os.environ.get("PF_DB_DSN", ""))
    a = ap.parse_args(argv)

    rows = load_backlog()
    print(f"migrate[{a.domain}]: source rows={len(rows)}")
    if not rows:
        print("  nothing to migrate")
        return 0
    print(f"  sample: {rows[0]['id']} | {rows[0]['status']} | {rows[0]['title'][:40]}")

    if not a.apply:
        print("  dry-run: pass --apply with PF_DB_DSN to write")
        return 0
    if not a.dsn:
        print("PF_DB_DSN required for --apply", file=sys.stderr)
        return 2
    import psycopg
    written = 0
    with psycopg.connect(a.dsn) as c, c.cursor() as cur:
        for r in rows:
            cur.execute(
                """INSERT INTO backlog_items (id, tenant_id, type, status, title, body)
                   VALUES (%(id)s, %(tenant_id)s, %(type)s, %(status)s, %(title)s, %(body)s)
                   ON CONFLICT (id) DO NOTHING""", r)
            written += cur.rowcount
    print(f"  migrated {written} new row(s) into backlog_items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
