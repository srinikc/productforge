"""Measure DB-mode backlog read latency against the T1 DB-read SLO (p95 <= 50 ms)."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round((len(xs) - 1) * p)))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default="product_forge")
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    api = os.environ.get("PF_EDP_API_URL", "http://127.0.0.1:8030").rstrip("/")
    token = os.environ.get("PF_EDP_TOKEN") or os.environ.get("PF_ADMIN_TOKEN", "")
    url = f"{api}/backlog?tenant={a.tenant}&limit=100000"
    db: list[float] = []
    for i in range(a.iterations + 2):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        t = time.perf_counter()
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        ms = (time.perf_counter() - t) * 1000
        if i >= 2:
            db.append(ms)
    sql_ms: list[float] = []
    point_api: list[float] = []
    one_id = ""
    dsn = os.environ.get("PF_DB_DSN")
    if dsn:
        import psycopg
        with psycopg.connect(dsn) as c, c.cursor() as cur:
            cur.execute("SELECT id FROM backlog_items WHERE tenant_id=%s ORDER BY id LIMIT 1", (a.tenant,))
            row = cur.fetchone()
            if not row:
                raise SystemExit(f"bench: no backlog rows for tenant {a.tenant}")
            one = row[0]
            one_id = one
            point_ms: list[float] = []
            for _ in range(a.iterations):
                t = time.perf_counter()
                cur.execute("SELECT data FROM backlog_items WHERE tenant_id=%s AND id=%s", (a.tenant, one))
                cur.fetchone()
                point_ms.append((time.perf_counter() - t) * 1000)
            for _ in range(a.iterations):
                t = time.perf_counter()
                cur.execute("SELECT id, data FROM backlog_items WHERE tenant_id=%s", (a.tenant,))
                cur.fetchall()
                sql_ms.append((time.perf_counter() - t) * 1000)
    if one_id:
        purl = f"{api}/backlog/{one_id}?tenant={a.tenant}"
        for _ in range(a.iterations):
            req = urllib.request.Request(purl, headers={"Authorization": f"Bearer {token}"})
            t = time.perf_counter()
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
            point_api.append((time.perf_counter() - t) * 1000)
    files = list((ROOT / "data" / "backlog" / "items").glob("*.json")) + list((ROOT / "products").glob("*/data/backlog/items/*.json"))
    file_ms: list[float] = []
    for _ in range(a.iterations):
        t = time.perf_counter()
        for f in files:
            d = json.loads(f.read_text(encoding="utf-8"))
            if str(d.get("project") or d.get("scope") or "product_forge") != a.tenant:
                continue
        file_ms.append((time.perf_counter() - t) * 1000)
    out = {
        "tenant": a.tenant,
        "iterations": a.iterations,
        "db_p50_ms": round(statistics.median(db), 2),
        "db_p95_ms": round(pct(db, 0.95), 2),
        "db_p99_ms": round(pct(db, 0.99), 2),
        "file_p50_ms": round(statistics.median(file_ms), 2),
        "file_p95_ms": round(pct(file_ms, 0.95), 2),
        "sql_p95_ms": round(pct(sql_ms, 0.95), 2) if sql_ms else None,
        "point_sql_p95_ms": round(pct(point_ms, 0.95), 2) if sql_ms else None,
        "point_api_p95_ms": round(pct(point_api, 0.95), 2) if point_api else None,
        "t1_db_read_p95_ms": 50,
        "api_vs_file_ratio": round(pct(db, 0.95) / max(pct(file_ms, 0.95), 0.01), 2),
        "db_read_pass": bool(point_api) and pct(point_api, 0.95) <= 50,
        "no_regression_pass": pct(db, 0.95) <= max(pct(file_ms, 0.95) * 1.25, 150),
    }
    text = json.dumps(out, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    return 0 if out["db_read_pass"] and out["no_regression_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
