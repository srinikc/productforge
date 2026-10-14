"""EDP-17 (BI-PF-1309): bootstrap Product Forge's system-of-record PostgreSQL.

Deploy step (never run on application startup): creates the ``schema_migrations`` bookkeeping table and
applies every ``migrations/NNNN_*.up.sql`` in ascending order, recording applied versions. Connection is
taken from the ``PF_DB_DSN`` env var (or ``--dsn``); credentials are never stored in the repo.

Self-skips (exit 0) when no DSN is set (unless ``--required``), and fails clearly when no PostgreSQL
driver is installed — so offline/CI stays green.

Usage:
  python scripts/dev/db_bootstrap.py                 # uses $PF_DB_DSN
  python scripts/dev/db_bootstrap.py --dsn postgres://pf_owner:...@localhost:5432/productforge
  python scripts/dev/db_bootstrap.py --skip-roles    # skip 0001_roles (needs a superuser)
  python scripts/dev/db_bootstrap.py --required      # exit 1 if DSN missing
"""
import argparse
import glob
import os
import re
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_MIG_DIR = os.path.join(_ROOT, "migrations")
_MIG_RE = re.compile(r"^(\d+)_(.+)\.up\.sql$")


def _driver():
    for name in ("psycopg", "psycopg2"):
        try:
            return __import__(name)
        except Exception:
            continue
    return None


def _migrations() -> list:
    out = []
    for p in glob.glob(os.path.join(_MIG_DIR, "*.up.sql")):
        m = _MIG_RE.match(os.path.basename(p))
        if m:
            out.append((int(m.group(1)), m.group(2), p))
    return sorted(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("PF_DB_DSN", ""))
    ap.add_argument("--skip-roles", action="store_true", help="skip 0001_roles (needs a superuser)")
    ap.add_argument("--required", action="store_true", help="fail if no DSN is set")
    a = ap.parse_args(argv)

    if not a.dsn:
        print("db-bootstrap: no PF_DB_DSN set - nothing to do (set it, or pass --dsn)")
        return 1 if a.required else 0

    drv = _driver()
    if drv is None:
        print("db-bootstrap: FAIL - no PostgreSQL driver (pip install 'psycopg[binary]')")
        return 1

    migs = _migrations()
    if not migs:
        print(f"db-bootstrap: FAIL - no migrations found in {_MIG_DIR}")
        return 1

    try:
        conn = drv.connect(a.dsn)
    except Exception as e:  # noqa: BLE001
        print(f"db-bootstrap: FAIL - cannot connect: {type(e).__name__}: {e}")
        return 1

    try:
        try:
            conn.autocommit = True
        except Exception:
            pass
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version BIGINT PRIMARY KEY, name TEXT NOT NULL, "
                    "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        cur.execute("SELECT version FROM schema_migrations")
        applied = {int(r[0]) for r in cur.fetchall()}
        n = 0
        for ver, name, path in migs:
            if ver in applied:
                print(f"db-bootstrap: skip {ver:04d} {name} (already applied)")
                continue
            if a.skip_roles and name.startswith("roles"):
                print(f"db-bootstrap: skip {ver:04d} {name} (--skip-roles)")
                continue
            with open(path, encoding="utf-8") as f:
                cur.execute(f.read())
            cur.execute("INSERT INTO schema_migrations(version, name) VALUES (%s, %s)", (ver, name))
            n += 1
            print(f"db-bootstrap: applied {ver:04d} {name}")
        print(f"db-bootstrap: OK ({n} applied, {len(applied)} already present)")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
