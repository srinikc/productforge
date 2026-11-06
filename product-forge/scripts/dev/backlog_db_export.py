"""Export PostgreSQL backlog rows back to file projections for rollback/reconcile.

Use before setting PF_BACKLOG_DB=off after DB-mode writes, or to rebuild missing projections.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def target_dir(tenant: str) -> Path:
    if tenant == "product_forge":
        return ROOT / "data" / "backlog" / "items"
    return ROOT / "products" / tenant / "data" / "backlog" / "items"


def main() -> int:
    ap = argparse.ArgumentParser(description="Export DB backlog rows to file projections")
    ap.add_argument("--tenant", default="product_forge")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dsn = os.environ.get("PF_DB_DSN")
    if not dsn:
        print("PF_DB_DSN required", file=sys.stderr)
        return 2
    out = Path(a.out_dir) if a.out_dir else target_dir(a.tenant)
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute("SELECT id, data FROM backlog_items WHERE tenant_id=%s ORDER BY id", (a.tenant,))
        rows = cur.fetchall()
    if a.dry_run:
        print(f"export: dry-run tenant={a.tenant} rows={len(rows)} out={out}")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    for iid, data in rows:
        p = out / f"{iid}.json"
        if p.exists() and not a.overwrite:
            skipped += 1
            continue
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1
    print(f"export: tenant={a.tenant} rows={len(rows)} written={written} skipped={skipped} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
