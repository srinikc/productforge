"""Runtime launcher for the generic Go capability service (capsvc) - ADR-0007/0008, BI-PF-1401.

Starts ``go/capsvc`` with the local dev token so it can authenticate inbound calls and call the backlog
API (the single writer). This is the service's runtime entry point (the Go equivalent of dev_server.py).

Run from product-forge/:  python scripts/dev/run_capsvc.py [--addr 127.0.0.1:8020]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _dev_token() -> str:
    tok = os.environ.get("PF_API_TOKEN", "").strip()
    if tok:
        return tok
    tf = ROOT / "data" / "local" / "dev-api-token"
    return tf.read_text(encoding="utf-8").strip() if tf.is_file() else ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run the Go capability service (capsvc).")
    ap.add_argument("--addr", default=os.environ.get("PF_CAP_ADDR", "127.0.0.1:8020"))
    ap.add_argument("--backlog-api", default=os.environ.get("PF_BACKLOG_API", "http://127.0.0.1:8010/api/v1"))
    a = ap.parse_args(argv)

    token = _dev_token()
    if not token:
        print("no dev token: run scripts/dev/dev_server.py first (or set PF_API_TOKEN)", file=sys.stderr)
        return 2
    env = dict(os.environ)
    env.update({
        "PF_CAP_TOKEN": os.environ.get("PF_CAP_TOKEN", token),
        "PF_BACKLOG_TOKEN": os.environ.get("PF_BACKLOG_TOKEN", token),
        "PF_BACKLOG_API": a.backlog_api,
        "PF_CAP_ADDR": a.addr,
    })
    return subprocess.call(["go", "run", "."], cwd=str(ROOT / "go" / "capsvc"), env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
