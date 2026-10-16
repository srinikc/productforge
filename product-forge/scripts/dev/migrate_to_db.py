"""EDP-18 (BI-PF-1310) migration/import framework.

Migrates a domain's file/SQLite data into the DB SoR with: DRY-RUN, counts + sha256 PARITY, a ROLLBACK
SNAPSHOT, and a CUTOVER flag. JSON is demoted to projections. Domains are registered in ``DOMAINS`` and each
returns rows shaped for its target table (here ``backlog_items``; the ``data`` column holds the FULL item so
nothing is lost).

Usage:
  python scripts/dev/migrate_to_db.py --domain backlog                       # dry-run (counts + hashes)
  PF_DB_DSN=... python scripts/dev/migrate_to_db.py --domain backlog --apply
  PF_DB_DSN=... python scripts/dev/migrate_to_db.py --domain backlog --snapshot .migration-snapshot
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "backlog" / "items"


def _sha(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda x: str(x.get("id") or "")):
        h.update(json.dumps(r, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return h.hexdigest()


def domain_backlog() -> list[dict]:
    rows = []
    for f in sorted(ITEMS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        rows.append({"id": d.get("id"), "tenant_id": "product_forge", "type": d.get("type", "feature"),
                     "status": d.get("status", "new"), "title": d.get("title", ""), "body": d.get("body", ""),
                     "data": json.dumps(d, separators=(",", ":")), "_item": d})
    return rows


# domain name -> (loader, target table, db-id column, db-data column)
DOMAINS = {"backlog": (domain_backlog, "backlog_items", "id", "data")}


def _db_state(dsn: str, table: str, id_col: str, data_col: str) -> dict[str, dict]:
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute(f'SELECT "{id_col}", "{data_col}" FROM "{table}"')
        return {r[0]: r[1] for r in cur.fetchall()}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="EDP-18: migrate a domain's files into the DB.")
    ap.add_argument("--domain", required=True, choices=sorted(DOMAINS))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--snapshot", default="", help="write a rollback snapshot of the DB rows to this dir")
    ap.add_argument("--cutover", action="store_true", help="mark cutover (DB -> source of truth)")
    ap.add_argument("--dsn", default=os.environ.get("PF_DB_DSN", ""))
    a = ap.parse_args(argv)
    loader, table, id_col, data_col = DOMAINS[a.domain]

    rows = loader()
    items = [r["_item"] for r in rows]
    src_hash = _sha(items)
    print(f"migrate[{a.domain}]: source rows={len(rows)} sha256={src_hash[:16]}")

    if not a.dsn:
        print("  dry-run (set PF_DB_DSN to compare/apply)")
        return 0
    before = _db_state(a.dsn, table, id_col, data_col)
    db_items = [v for v in before.values() if isinstance(v, dict)]
    print(f"  db rows={len(before)} sha256={_sha(db_items)[:16]}")

    if a.snapshot:
        snap = Path(a.snapshot)
        snap.mkdir(parents=True, exist_ok=True)
        (snap / f"{a.domain}.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
        print(f"  snapshot written: {snap / (a.domain + '.json')} ({len(before)} rows)")

    if not a.apply:
        print("  dry-run: pass --apply to write")
        return 0

    import psycopg
    written = 0
    with psycopg.connect(a.dsn) as c, c.cursor() as cur:
        for r in rows:
            cur.execute(
                f'''INSERT INTO "{table}" (id, tenant_id, type, status, title, body, data)
                    VALUES (%(id)s, %(tenant_id)s, %(type)s, %(status)s, %(title)s, %(body)s, %(data)s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data, type=EXCLUDED.type,
                      status=EXCLUDED.status, title=EXCLUDED.title, body=EXCLUDED.body
                    WHERE "{table}".data IS DISTINCT FROM EXCLUDED.data''', r)
            written += cur.rowcount
    after = _db_state(a.dsn, table, id_col, data_col)
    after_items = [v for v in after.values() if isinstance(v, dict)]
    ok = _sha(after_items) == src_hash
    print(f"  applied {written} row(s); paritY={'OK' if ok else 'MISMATCH'} (db sha256={_sha(after_items)[:16]})")
    if a.cutover and ok:
        (ROOT / "data" / f".cutover-{a.domain}").write_text(src_hash + "\n", encoding="utf-8")
        print(f"  cutover marked for {a.domain}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
