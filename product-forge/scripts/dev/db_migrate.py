"""Deploy-step wrapper for the Go migration runner (EDP-08/EDP-17, BI-PF-1309).

Runs ``pfmigrate`` (go/store/cmd/pfmigrate) as an EXPLICIT deploy step. Migrations are never applied on
application startup. Requires ``PF_DB_DSN`` (owner role). Migrations live in ``<repo>/migrations``.

Usage:
  python scripts/dev/db_migrate.py status
  python scripts/dev/db_migrate.py up
  python scripts/dev/db_migrate.py down
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "go" / "store"
MIGRATIONS_DIR = ROOT / "migrations"


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    if cmd not in ("up", "down", "status"):
        print("usage: python scripts/dev/db_migrate.py {up|down|status}", file=sys.stderr)
        return 2
    if not os.environ.get("PF_DB_DSN"):
        print("PF_DB_DSN is not set (owner-role DSN required)", file=sys.stderr)
        return 2
    return subprocess.call(
        ["go", "run", "./cmd/pfmigrate", "-dir", str(MIGRATIONS_DIR), cmd],
        cwd=str(MODULE_DIR),
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
