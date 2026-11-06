"""Backfill file backlog items into the PostgreSQL backlog authority.

Scans PF-SB item files and generated-product item files and POSTs each full item through the Go
edpsvc /backlog writer. Idempotent because BacklogStore.Put upserts by (tenant_id, id).

Usage:
  PF_EDP_API_URL=http://127.0.0.1:8030 PF_API_TOKEN=... python scripts/dev/backlog_db_backfill.py --dry-run
  PF_EDP_API_URL=http://127.0.0.1:8030 PF_API_TOKEN=... python scripts/dev/backlog_db_backfill.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import backlog, backlog_scope  # noqa: E402


def tenant_for_item(it: dict, path: Path) -> str:
    tenant = str(it.get("project") or it.get("scope") or "product_forge")
    parts = path.parts
    if "products" in parts:
        i = parts.index("products")
        expected = parts[i + 1] if i + 1 < len(parts) else ""
        if expected and tenant != expected:
            raise ValueError(f"tenant attribution mismatch: file={path} tenant={tenant} expected={expected}")
    return tenant


def candidates() -> list[Path]:
    out = []
    out.extend(sorted((ROOT / "data" / "backlog" / "items").glob("*.json")))
    for p in sorted((ROOT / "products").glob("*/data/backlog/items/*.json")):
        out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill backlog files into PostgreSQL")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tenant", default="", help="only backfill this tenant")
    ap.add_argument("--rate", type=float, default=float(os.environ.get("PF_BACKLOG_DB_BACKFILL_RPS", "8")))
    a = ap.parse_args()
    if not os.environ.get("PF_EDP_API_URL"):
        print("PF_EDP_API_URL is required", file=sys.stderr)
        return 2
    if not (os.environ.get("PF_EDP_TOKEN") or os.environ.get("PF_ADMIN_TOKEN")):
        print("PF_EDP_TOKEN or PF_ADMIN_TOKEN is required", file=sys.stderr)
        return 2
    if str(os.environ.get("PF_BACKLOG_DB", "on")).strip().lower() != "on":
        print("backfill: PF_BACKLOG_DB=on is required", file=sys.stderr)
        return 2
    files = candidates()
    if not files:
        print("backfill: no item files found")
        return 0
    ok = fail = 0
    for f in files:
        try:
            it = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"backfill: cannot read {f}: {e}", file=sys.stderr)
            fail += 1
            continue
        if not isinstance(it, dict) or not it.get("id"):
            print(f"backfill: invalid item file {f}", file=sys.stderr)
            fail += 1
            continue
        try:
            tenant = tenant_for_item(it, f)
            if a.tenant:
                if tenant != a.tenant:
                    continue
            elif not backlog_scope.enabled(tenant):
                print(f"backfill: skip unlisted tenant {tenant} ({f})", file=sys.stderr)
                continue
        except ValueError as e:
            print(f"backfill: {e}", file=sys.stderr)
            fail += 1
            continue
        if a.dry_run:
            print(f"would backfill {it['id']} ({tenant})")
            ok += 1
            continue
        try:
            try:
                backlog.store_item_to_db(it)
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                retry = float(e.headers.get("Retry-After") or 1)
                time.sleep(retry)
                backlog.store_item_to_db(it)
            ok += 1
            time.sleep(1.0 / max(a.rate, 0.1))
        except Exception as e:
            print(f"backfill: {it['id']} failed: {e}", file=sys.stderr)
            fail += 1
    print(f"backfill: {'dry-run ' if a.dry_run else ''}ok={ok} failed={fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
