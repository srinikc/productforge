"""BI-PF-1399 cutover step: files <-> DB parity for the backlog.

Compares the canonical file backlog (``data/backlog/items/*.json``) against the ``backlog_items`` table.
Compares full JSON item data (not counts), plus missing/extra ids. Exit 1 on any drift. Prereq: migrations 0021/0022 applied.

Usage: PF_DB_DSN=... python scripts/dev/backlog_db_parity.py
"""
from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_LEGACY_FORGE_SCOPE = "factory"
ITEMS = ROOT / "data" / "backlog" / "items"


def item_tenant(d: dict) -> str:
    raw = str(d.get("project") or d.get("scope") or "product_forge")
    return "product_forge" if raw in ("portfolio", "product_forge", _LEGACY_FORGE_SCOPE) else raw


def file_items(tenant: str, source_dir: str = "") -> dict[str, dict]:
    out = {}
    base = Path(source_dir) if source_dir else None
    paths = (list(base.glob("*.json")) if base else
             list(ITEMS.glob("*.json")) + list((ROOT / "products").glob("*/data/backlog/items/*.json")))
    for f in paths:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("id") and item_tenant(d) == tenant:
            out[d["id"]] = d
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Scoped backlog file/DB parity")
    ap.add_argument("--tenant", default="product_forge")
    ap.add_argument("--source-dir", default="")
    a = ap.parse_args()
    dsn = os.environ.get("PF_DB_DSN")
    if not dsn:
        print("PF_DB_DSN required", file=sys.stderr)
        return 2
    fitems = file_items(a.tenant, a.source_dir)
    fids = set(fitems)
    if not fids and not os.environ.get("PF_PARITY_ALLOW_EMPTY"):
        print(f"BACKLOG_DB_PARITY_EMPTY: no file sources for tenant {a.tenant}", file=sys.stderr)
        return 1
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute("SELECT id, data FROM backlog_items WHERE tenant_id=%s", (a.tenant,))
        drows = {r[0]: r[1] for r in cur.fetchall()}
    if not drows and not os.environ.get("PF_PARITY_ALLOW_EMPTY"):
        print(f"BACKLOG_DB_PARITY_EMPTY: no DB rows for tenant {a.tenant}", file=sys.stderr)
        return 1
    missing = sorted(fids - set(drows))
    extra = sorted(set(drows) - fids)
    def canon(x):
        if isinstance(x, float) and x.is_integer():
            return int(x)
        if isinstance(x, dict):
            return {k: canon(v) for k, v in x.items()}
        if isinstance(x, list):
            return [canon(v) for v in x]
        return x
    mism = [i for i in sorted(fids & set(drows)) if canon(drows[i]) != canon(fitems[i])]
    print(f"backlog parity[{a.tenant}]: files={len(fids)} db={len(drows)} missing_in_db={len(missing)} "
          f"extra_in_db={len(extra)} data_mismatch={len(mism)}")
    if missing or extra or mism:
        for i in missing[:10]:
            print(f"   missing_in_db: {i}")
        for i in extra[:10]:
            print(f"   extra_in_db: {i}")
        for i in mism[:10]:
            print(f"   data_mismatch: {i}")
        print("BACKLOG_DB_PARITY_DRIFT: fix drift before setting PF_BACKLOG_DB=on")
        return 1
    print("backlog parity: OK (files == DB, full item data)")
    print("cutover gate: OK -> safe to set PF_BACKLOG_DB=on (BI-PF-1399 Phase 3)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
