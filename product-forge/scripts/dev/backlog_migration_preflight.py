"""Preflight for backlog migration 0021 (scoped uniqueness).

Requires an explicit verified-backup confirmation, reports legacy duplicate IDs, table size, and
blocking locks. Run after migrations through 0020 and before 0021.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    dsn = os.environ.get("PF_DB_DSN")
    if not dsn:
        print("PF_DB_DSN required", file=sys.stderr)
        return 2
    if os.environ.get("PF_BACKUP_CONFIRMED") != "1":
        print("PF_BACKUP_CONFIRMED=1 is required before migration 0021", file=sys.stderr)
        return 2
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM backlog_items")
        rows = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM (SELECT id FROM backlog_items GROUP BY id HAVING count(*) > 1) x")
        dup_ids = cur.fetchone()[0]
        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('backlog_items'))")
        size = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM pg_locks WHERE relation='backlog_items'::regclass AND NOT granted")
        waiting = cur.fetchone()[0]
        cur.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE confrelid='backlog_items'::regclass AND contype='f'")
        fks = cur.fetchall()
        cur.execute("SELECT conname FROM pg_constraint WHERE conrelid='backlog_items'::regclass AND contype='u'")
        uniques = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT tgname FROM pg_trigger WHERE tgrelid='backlog_items'::regclass AND NOT tgisinternal")
        triggers = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT indexname FROM pg_indexes WHERE tablename='backlog_items'")
        indexes = [r[0] for r in cur.fetchall()]
        print(f"preflight: rows={rows} legacy_duplicate_ids={dup_ids} size={size} waiting_locks={waiting}")
        print(f"preflight: fks={[r[0] for r in fks]} uniques={uniques} triggers={triggers} indexes={indexes}")
        unknown_fks = [r[0] for r in fks if r[0] != "fk_traceability_item"]
        unknown_uniques = [u for u in uniques if u != "backlog_items_pkey"]
        if waiting:
            print("preflight: BLOCKED by waiting locks", file=sys.stderr)
            return 1
        if unknown_fks or unknown_uniques or triggers:
            print(f"preflight: BLOCKED unknown dependencies fks={unknown_fks} uniques={unknown_uniques} triggers={triggers}", file=sys.stderr)
            return 1
    print("preflight: OK (backup confirmed; proceed in maintenance window)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
