"""EDP-22 sampled EXPLAIN(ANALYZE,BUFFERS) capture.

Production is sampling-only: sample rate is capped at 0.05 and rate/concurrency limits are enforced by the
caller. Every statement is allowlisted, read-only, timed out, rolled back, and redacted before output.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from datetime import datetime, timezone

ALLOWED = {
    "backlog_items": "SELECT id, tenant_id, status FROM backlog_items WHERE tenant_id = 't' ORDER BY id LIMIT 50",
    "projects": "SELECT id, tenant_id, slug FROM projects WHERE tenant_id = 't' ORDER BY slug LIMIT 50",
    "runs": "SELECT id, tenant_id, status FROM runs WHERE tenant_id = 't' AND status = 'running' LIMIT 50",
    "jobs": "SELECT id, tenant_id, status FROM jobs WHERE tenant_id = 't' AND status = 'queued' LIMIT 50",
    "audit": "SELECT id, tenant_id, event_type FROM audit WHERE tenant_id = 't' ORDER BY id DESC LIMIT 50",
}
MAX_PROD_SAMPLE = 0.05
MAX_PER_MINUTE = 60


def validate(env: str, sample_rate: float, per_minute: int, allow_production: bool = False) -> str:
    if sample_rate < 0 or sample_rate > 1:
        return "sample rate must be between 0 and 1"
    if env.strip().lower() == "production" and sample_rate > 0 and not allow_production:
        return "production EXPLAIN requires --allow-production"
    if env.strip().lower() == "production" and sample_rate > MAX_PROD_SAMPLE:
        return f"production sample rate must be <= {MAX_PROD_SAMPLE}"
    if per_minute < 1 or per_minute > MAX_PER_MINUTE:
        return f"per-minute cap must be between 1 and {MAX_PER_MINUTE}"
    return ""


def rate_ok(state_path: str, per_minute: int, now: datetime) -> bool:
    if not state_path:
        return True
    try:
        rows = [datetime.fromisoformat(x) for x in json.loads(open(state_path, encoding="utf-8").read())]
    except Exception:
        rows = []
    rows = [r for r in rows if (now - r).total_seconds() < 60]
    if len(rows) >= per_minute:
        return False
    rows.append(now)
    try:
        open(state_path, "w", encoding="utf-8").write(json.dumps([r.isoformat() for r in rows]))
    except OSError:
        return False
    return True


def audit(path: str, rec: dict) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def redact(plan: str) -> str:
    plan = re.sub(r"'[^']*'", "'?'", plan)
    plan = re.sub(r"\b\d{4,}\b", "?", plan)
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description="Sampled read-only EXPLAIN capture")
    ap.add_argument("--dsn", default=os.environ.get("PF_EXPLAIN_DSN", ""))
    ap.add_argument("--query", choices=sorted(ALLOWED), required=True)
    ap.add_argument("--env", default=os.environ.get("PF_ENV", "dev"))
    ap.add_argument("--sample-rate", type=float, default=0.0)
    ap.add_argument("--per-minute", type=int, default=60)
    ap.add_argument("--out", default="")
    ap.add_argument("--audit", default="")
    ap.add_argument("--state", default="")
    ap.add_argument("--allow-production", action="store_true")
    a = ap.parse_args()
    bad = validate(a.env, a.sample_rate, a.per_minute, a.allow_production)
    if bad:
        print(f"explain: REFUSE - {bad}", file=sys.stderr)
        return 2
    now = datetime.now(timezone.utc)
    if not rate_ok(a.state, a.per_minute, now):
        print("explain: REFUSE - per-minute cap reached", file=sys.stderr)
        return 2
    if a.sample_rate == 0 or random.random() > a.sample_rate:
        print("explain: skipped (sampling)")
        audit(a.audit, {"at": now.isoformat(), "actor": os.environ.get("PF_ACTOR", ""), "query": a.query,
                        "decision": "skipped", "env": a.env})
        return 0
    if not a.dsn:
        print("explain: PF_EXPLAIN_DSN is required", file=sys.stderr)
        return 2
    import psycopg

    out = []
    with psycopg.connect(a.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + ALLOWED[a.query])
            out = [redact(str(r[0])) for r in cur.fetchall()]
        conn.rollback()
    text = "\n".join(out) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    audit(a.audit, {"at": now.isoformat(), "actor": os.environ.get("PF_ACTOR", ""), "query": a.query,
                    "decision": "captured", "env": a.env, "artifact": a.out})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
