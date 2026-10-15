"""Runtime launcher for the EDP data-plane service (edpsvc) - ADR-0008, BI-PF-1402.

Starts go/edpsvc (migrations admin + schema-check) with the DSN and an admin token. The Go equivalent of
dev_server.py for the EDP data-plane API surface.

Run from product-forge/:  python scripts/dev/run_edpsvc.py [--addr 127.0.0.1:8030] [--token ...]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run the EDP data-plane service (edpsvc).")
    ap.add_argument("--addr", default=os.environ.get("PF_EDP_ADDR", "127.0.0.1:8030"))
    ap.add_argument("--token", default=os.environ.get("PF_ADMIN_TOKEN", ""))
    a = ap.parse_args(argv)
    if not os.environ.get("PF_DB_DSN"):
        print("PF_DB_DSN is required (owner-role DSN)", file=sys.stderr)
        return 2
    token = a.token or os.environ.get("PF_API_TOKEN", "")
    if not token:
        print("an admin token is required (--token / PF_ADMIN_TOKEN / PF_API_TOKEN)", file=sys.stderr)
        return 2
    env = dict(os.environ)
    env.update({"PF_ADMIN_TOKEN": token, "PF_EDP_ADDR": a.addr,
                "PF_MIGRATIONS_DIR": str(ROOT / "migrations")})
    return subprocess.call(["go", "run", "."], cwd=str(ROOT / "go" / "edpsvc"), env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
