"""BI-PF-1423: per-task usage capture for a backlog item from OpenCode's local usage DB.

OpenCode persists REAL (API-reported) usage in ``~/.local/share/opencode/opencode.db`` - the ``session`` table
carries ``cost, tokens_input, tokens_output, tokens_reasoning, tokens_cache_read, tokens_cache_write`` and
``time_updated``. That DB has no backlog id, so per-item attribution = **snapshot at task start, delta at task
end**, written to the item's ``execution.usage`` (+ ``duration_seconds``) via ``POST /backlog/items/{id}/execution``.

Usage:
  python scripts/dev/usage_capture.py snapshot --item BI-PF-1234
  python scripts/dev/usage_capture.py delta --item BI-PF-1234 [--apply]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("PF_OPENCODE_DB", str(Path.home() / ".local" / "share" / "opencode" / "opencode.db")))
BASELINE = ROOT / ".usage-baseline.json"


def latest_session() -> dict:
    if not DB.is_file():
        raise SystemExit(f"opencode usage db not found: {DB}")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        cur = con.execute(
            "SELECT id, cost, tokens_input, tokens_output, tokens_reasoning, tokens_cache_read, "
            "tokens_cache_write, time_updated FROM session "
            "ORDER BY CAST(time_updated AS INTEGER) DESC LIMIT 1")
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
    finally:
        con.close()
    return dict(zip(cols, row)) if row else {}


def usage_of(s: dict) -> dict:
    return {"input_tokens": int(s.get("tokens_input") or 0), "output_tokens": int(s.get("tokens_output") or 0),
            "reasoning_tokens": int(s.get("tokens_reasoning") or 0), "cache_read": int(s.get("tokens_cache_read") or 0),
            "cache_write": int(s.get("tokens_cache_write") or 0), "cost_usd": float(s.get("cost") or 0)}


def delta(base: dict, cur: dict) -> dict:
    return {k: round(cur[k] - base.get(k, 0), 6) for k in cur}


def _record(item: str, usage: dict, duration: float, api: str) -> None:
    token = os.environ.get("PF_API_TOKEN", "") or (ROOT / "data" / "local" / "dev-api-token").read_text().strip()
    body = json.dumps({"usage": usage, "duration_seconds": duration}).encode("utf-8")
    req = urllib.request.Request(f"{api.rstrip('/')}/backlog/items/{item}/execution", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Roles", "operator")
    with urllib.request.urlopen(req, timeout=15):
        pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Per-task usage capture (BI-PF-1423).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--item", required=True)
    dl = sub.add_parser("delta")
    dl.add_argument("--item", required=True)
    dl.add_argument("--apply", action="store_true")
    dl.add_argument("--api", default=os.environ.get("PF_BACKLOG_API", "http://127.0.0.1:8030"))
    a = ap.parse_args(argv)

    s = latest_session()
    cur = usage_of(s)
    if a.cmd == "snapshot":
        BASELINE.write_text(json.dumps({"item": a.item, "session_id": s.get("id"), "usage": cur,
                                        "ts": time.time()}), encoding="utf-8")
        print(f"baseline[{a.item}]: session={s.get('id')} cost={cur['cost_usd']} "
              f"tokens={cur['input_tokens'] + cur['output_tokens']}")
        return 0

    if not BASELINE.is_file():
        print("no baseline; run 'snapshot' at task start first", file=sys.stderr)
        return 2
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    d = delta(base["usage"], cur)
    duration = round(time.time() - float(base.get("ts") or time.time()), 1)
    print(f"delta[{a.item}]: {json.dumps(d)} duration_seconds={duration}")
    if not a.apply:
        print("(dry-run; pass --apply to record on the item)")
        return 0
    _record(a.item, d, duration, a.api)
    print("recorded execution.usage on the item")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
