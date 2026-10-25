"""Persist the final report on a backlog item (BI-PF-1484).

Writes item.final_report: AC verification, test results by kind, totals (time/tokens/cost),
accepted/deferred with backlog ids, and gate decisions. Fails if any AC is not PASS or a
disposition policy is violated.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if p not in sys.path:
        sys.path.insert(0, p)

from core import backlog, execution_trail as tr  # noqa: E402
import disposition_policy as dp  # noqa: E402
import ac_policy  # noqa: E402


def build(item_id: str) -> dict:
    it = backlog.get_epic("product_forge", None, item_id) or {}
    evs = tr.events(item_id)
    acs = it.get("ac_verification") or []
    bad_ac = ac_policy.problems(it)
    bad = dp.problems(it, "design", lambda i: backlog.get_epic("product_forge", None, i))
    bad += dp.problems(it, "diff", lambda i: backlog.get_epic("product_forge", None, i))
    tests = [t for e in evs for t in (e.get("tests") or [])]
    u = tr.usage_totals(evs)
    start = evs[0]["at"] if evs else ""
    end = evs[-1]["at"] if evs else ""
    import hashlib
    ac_hash = hashlib.sha256(json.dumps({"acs": acs, "dispositions": it.get("review_dispositions") or {}},
                                        sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    total_ms = 0
    try:
        ordered = sorted(evs, key=lambda e: str(e.get("at") or ""))
        from datetime import datetime as _dt
        total_ms = max(0, int((_dt.fromisoformat(ordered[-1]["at"].replace("Z", "+00:00"))
                               - _dt.fromisoformat(ordered[0]["at"].replace("Z", "+00:00"))).total_seconds() * 1000)) if ordered else 0
    except Exception:
        total_ms = max(0, sum(int(e.get("duration_ms") or 0) for e in evs))
    return {"schema": "pf.final-report/1", "ac_hash": ac_hash, "total_time_ms": total_ms, "item": item_id, "generated_at": datetime.now(timezone.utc).isoformat(),
            "item_revision": it.get("revision"), "current_stage": tr.current_stage(item_id, it.get("status") or ""),
            "acs": acs, "ac_problems": bad_ac, "tests_by_kind": tr.tests_by_kind(evs),
            "usage": u, "started_at": start, "finished_at": end,
            "disposition_problems": bad,
            "dispositions": {m: {k: v for k, v in ((it.get("review_dispositions") or {}).get(m) or {}).items()
                                 if str((v or {}).get("status") or "").upper() in ("ACCEPTED", "DEFERRED")}
                             for m in ("design", "diff")},
            "gate_decisions": [d for d in (it.get("decisions") or [])
                               if str(d.get("decision") or "").upper() in ("APPROVE", "APPROVE_WITH_ATTENTION",
                                                                           "DISPOSITION_APPROVAL", "REVIEW_CHURN")],
            "other_decisions": [d for d in (it.get("decisions") or [])
                                if str(d.get("decision") or "").upper() not in ("APPROVE", "APPROVE_WITH_ATTENTION",
                                                                                "DISPOSITION_APPROVAL", "REVIEW_CHURN")]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Persist an item final report")
    ap.add_argument("--item", required=True)
    ap.add_argument("--report", action="store_true", help="print only; do not persist")
    a = ap.parse_args(argv)
    r = build(a.item)
    if r["ac_problems"] or r["disposition_problems"] or not r["acs"]:
        print("finalize: FAIL")
        for x in r["ac_problems"]:
            print(f"  - AC not PASS: {x}")
        for x in r["disposition_problems"]:
            print(f"  - {x}")
        if not r["acs"]:
            print("  - no ac_verification recorded")
        return 1
    if a.report:
        print(json.dumps(r, indent=2))
        return 0
    it = backlog.update("product_forge", None, a.item, final_report=r,
                        _note="final report persisted (BI-PF-1484)")
    print(f"finalize: persisted final_report on {a.item} (revision {it.get('revision')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
