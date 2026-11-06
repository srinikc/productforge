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
        print(f"preflight: rows={rows} legacy_duplicate_ids={dup_ids} size={size} waiting_locks={waiting}")
        if waiting:
            print("preflight: BLOCKED by waiting locks", file=sys.stderr)
            return 1
    print("preflight: OK (backup confirmed; proceed in maintenance window)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
