"""BI-PF-1423: GENERIC per-task usage capture with pluggable SOURCE adapters.

Each harness/usage source is an **adapter** returning a *cumulative* usage dict in the ``execution.usage``
schema the epic rollup reads (``core/scheduler._usage_rollup``):
``input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens, total_tokens, calls,
cost_usd``. Per-item attribution = **snapshot at task start -> delta at task end** -> recorded via
``POST /backlog/items/{id}/execution``.

Built-in adapters (add more for other harnesses - Claude Code, Codex, a provider API, PF's own call_ledger):
  - ``opencode`` : reads OpenCode's SQLite usage DB (session table: cost + tokens_*).
  - ``json``     : reads a JSON file any wrapper can write (same schema) - the framework-agnostic feed.

Usage:
  python scripts/dev/usage_capture.py snapshot --item BI-PF-XXXX [--source opencode|json]
  python scripts/dev/usage_capture.py delta --item BI-PF-XXXX [--apply]
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
DEFAULT_OPENCODE_DB = Path(os.environ.get("PF_OPENCODE_DB", str(Path.home() / ".local" / "share" / "opencode" / "opencode.db")))
BASELINE = ROOT / ".usage-baseline.json"
USAGE_KEYS = ("input_tokens", "output_tokens", "reasoning_tokens", "cache_read_tokens",
              "cache_write_tokens", "total_tokens", "calls", "cost_usd")


class OpencodeSource:
    """Usage adapter for the OpenCode harness (reads its local SQLite usage DB)."""

    name = "opencode"

    def __init__(self, db: Path | str | None = None):
        self.db = Path(db or DEFAULT_OPENCODE_DB)

    def total(self) -> dict:
        if not self.db.is_file():
            raise SystemExit(f"opencode usage db not found: {self.db}")
        con = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            cur = con.execute(
                "SELECT cost, tokens_input, tokens_output, tokens_reasoning, tokens_cache_read, "
                "tokens_cache_write FROM session ORDER BY CAST(time_updated AS INTEGER) DESC LIMIT 1")
            row = cur.fetchone() or (0, 0, 0, 0, 0, 0)
        finally:
            con.close()
        inp, out, rea = int(row[1] or 0), int(row[2] or 0), int(row[3] or 0)
        return {"input_tokens": inp, "output_tokens": out, "reasoning_tokens": rea,
                "cache_read_tokens": int(row[4] or 0), "cache_write_tokens": int(row[5] or 0),
                "total_tokens": inp + out, "calls": 0, "cost_usd": float(row[0] or 0)}


class JsonFileSource:
    """Usage adapter for a JSON file any wrapper can write (framework-agnostic feed)."""

    name = "json"

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or os.environ.get("PF_USAGE_FILE", str(ROOT / ".usage-current.json")))

    def total(self) -> dict:
        d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}
        return {k: (float(d.get(k) or 0) if k == "cost_usd" else int(d.get(k) or 0)) for k in USAGE_KEYS}


def build_source(name: str, db=None, usage_file=None):
    if name == "opencode":
        return OpencodeSource(db)
    if name == "json":
        return JsonFileSource(usage_file)
    raise SystemExit(f"unknown source '{name}' (available: opencode, json)")


def delta(base: dict, cur: dict) -> dict:
    return {k: round(float(cur.get(k, 0)) - float(base.get(k, 0)), 6) for k in USAGE_KEYS}


def record(item: str, usage: dict, duration: float, api: str) -> None:
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
    ap.add_argument("--source", default=os.environ.get("PF_USAGE_SOURCE", "opencode"),
                    help="usage source adapter: opencode | json")
    ap.add_argument("--db", default=None, help="opencode: usage db path")
    ap.add_argument("--usage-file", default=None, help="json: usage file path")
    sub = ap.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--item", required=True)
    dl = sub.add_parser("delta")
    dl.add_argument("--item", required=True)
    dl.add_argument("--apply", action="store_true")
    dl.add_argument("--api", default=os.environ.get("PF_BACKLOG_API", "http://127.0.0.1:8030"))
    a = ap.parse_args(argv)

    src = build_source(a.source, a.db, a.usage_file)
    cur = src.total()
    if a.cmd == "snapshot":
        BASELINE.write_text(json.dumps({"item": a.item, "source": a.source, "usage": cur, "ts": time.time()}),
                            encoding="utf-8")
        print(f"baseline[{a.item}] source={a.source} cost={cur['cost_usd']} "
              f"tokens={cur['input_tokens'] + cur['output_tokens']}")
        return 0

    if not BASELINE.is_file():
        print("no baseline; run 'snapshot' at task start first", file=sys.stderr)
        return 2
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    d = delta(base["usage"], cur)
    duration = round(time.time() - float(base.get("ts") or time.time()), 1)
    print(f"delta[{a.item}] source={base.get('source', a.source)} {json.dumps(d)} duration_seconds={duration}")
    if not a.apply:
        print("(dry-run; pass --apply to record on the item)")
        return 0
    record(a.item, d, duration, a.api)
    print("recorded execution.usage on the item")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
