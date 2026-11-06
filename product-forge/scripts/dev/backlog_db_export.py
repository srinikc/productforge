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
    if not tenant or tenant in (".", "..") or any(x in tenant for x in ("/", "\\", ":")):
        raise ValueError(f"invalid tenant path: {tenant!r}")
    if tenant == "product_forge":
        return ROOT / "data" / "backlog" / "items"
    return ROOT / "products" / tenant / "data" / "backlog" / "items"


def main() -> int:
    ap = argparse.ArgumentParser(description="Export DB backlog rows to file projections")
    ap.add_argument("--tenant", default="product_forge")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true", help="delete projections not present in DB")
    ap.add_argument("--allow-empty-prune", action="store_true", help="dangerous: allow prune with zero DB rows")
    ap.add_argument("--confirm-prune", action="store_true", help="required to delete projections")
    ap.add_argument("--allow-external-out", action="store_true", help="allow out-dir outside the repo")
    a = ap.parse_args()
    dsn = os.environ.get("PF_DB_DSN")
    if not dsn:
        print("PF_DB_DSN required", file=sys.stderr)
        return 2
    out = Path(a.out_dir) if a.out_dir else target_dir(a.tenant)
    if a.out_dir and not a.allow_external_out:
        try:
            out.resolve().relative_to(ROOT.resolve())
        except ValueError:
            print("export: out-dir outside repo requires --allow-external-out", file=sys.stderr)
            return 2
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute("SELECT id, data FROM backlog_items WHERE tenant_id=%s ORDER BY id", (a.tenant,))
        rows = cur.fetchall()
    for iid, data in rows:
        if not isinstance(data, dict) or str(data.get("id") or "") != str(iid):
            print(f"export: id mismatch row={iid} data_id={data.get('id') if isinstance(data, dict) else '?'}", file=sys.stderr)
            return 1
    db_ids = {str(r[0]) for r in rows}
    prunable = []
    if a.prune and out.is_dir():
        prunable = [p for p in out.glob("*.json") if p.stem not in db_ids]
    if a.dry_run:
        print(f"export: dry-run tenant={a.tenant} rows={len(rows)} prunable={len(prunable)} out={out}")
        for p in prunable[:20]:
            print(f"export: would-prune {p.name}")
        return 0
    if a.prune:
        if not rows and not a.allow_empty_prune:
            print("export: refusing --prune with zero DB rows", file=sys.stderr)
            return 2
        if not a.confirm_prune:
            print("export: --prune requires --confirm-prune", file=sys.stderr)
            return 2
        try:
            from core import backlog
            if not backlog._db_for(a.tenant) and not os.environ.get("PF_BACKLOG_PRUNE_UNLISTED"):
                print(f"export: refusing prune for unlisted tenant {a.tenant}", file=sys.stderr)
                return 2
        except Exception:
            pass
    out.mkdir(parents=True, exist_ok=True)
    written = skipped = pruned = 0
    for _iid, _data in rows:
        if a.tenant != "product_forge" and isinstance(_data, dict):
            _data.setdefault("project", a.tenant)
    for p in prunable:
        p.unlink()
        pruned += 1
    for iid, data in rows:
        p = out / f"{iid}.json"
        if p.exists() and not a.overwrite:
            skipped += 1
            continue
        tmp = p.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            f.flush()
            import os as _os
            _os.fsync(f.fileno())
        tmp.replace(p)
        written += 1
    if out.resolve() == target_dir(a.tenant).resolve():
        try:
            from core import backlog
            op, cl = [], []
            for _iid, _data in rows:
                (cl if backlog._normalize_status(_data.get("status", "new")) in backlog._CLOSED else op).append(_data)
            backlog._write_indexes("product_forge" if a.tenant == "product_forge" else "project",
                                   None if a.tenant == "product_forge" else a.tenant, op, cl)
        except Exception as e:
            print(f"export: index refresh failed: {e}", file=sys.stderr)
            return 1
    print(f"export: tenant={a.tenant} rows={len(rows)} written={written} skipped={skipped} pruned={pruned} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
