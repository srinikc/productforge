"""Gate 2.5 review-churn budget (BI-PF-1480).

Counts diff-mode architect reviews per item (committed HEAD evidence) after the item's Gate 1 epoch. Warns
above warn_after, and fails a completion in the committed diff when the count exceeds fail_after unless the
item carries a HIL-attested `review_churn` decision citing the latest review sha.

Usage:
  python scripts/dev/review_churn_check.py            # gate (exit 1 on fail, 2 on scan error)
  python scripts/dev/review_churn_check.py --report   # dry-run, always exit 0 (scan errors still 2)
  python scripts/dev/review_churn_check.py --json     # machine output
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "dev"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import architect_review as ar  # noqa: E402
import gate2_completion_check as g2  # noqa: E402


def evaluate(ids: list[str]) -> list[dict]:
    rows = []
    for iid in ids:
        item = ar._get_item(iid)
        rows.append(ar.churn_verdict(iid, item, committed=True))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate 2.5 review-churn budget")
    ap.add_argument("--base", default="")
    ap.add_argument("--report", action="store_true", help="dry-run: report only, exit 0")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    base = a.base or ar._git_text(["merge-base", "develop", "HEAD"])
    if not base:
        payload = {"verdict": "skipped", "reason": "base_unavailable", "rows": []}
        print(json.dumps(payload) if a.json else "review-churn: skipped (base ref unavailable)")
        return 0
    try:
        rows = evaluate(g2.transitions(base))
    except Exception as e:  # fail closed on unreadable evidence/git
        print(f"review-churn: ERROR {e}", file=sys.stderr)
        return 2

    fails = [r for r in rows if r["fail"]]
    if a.json:
        print(json.dumps({"ok": not fails, "rows": rows}, indent=2))
    else:
        print("review-churn: diff reviews after the Gate 1 epoch")
        print("| item | count | warn_after | fail_after | warn | fail | attested | latest_sha | epoch |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['item']} | {r['count']} | {r['warn_after']} | {r['fail_after']} | "
                  f"{r['warn']} | {r['fail']} | {r['attested']} | {r['latest_sha']} | {r['epoch']} |")
    for r in rows:
        if r["fail"]:
            print(json.dumps({"event": "review_churn_fail", "item": r["item"], "count": r["count"],
                              "latest_sha": r["latest_sha"]}), file=sys.stderr)
        elif r["warn"]:
            print(json.dumps({"event": "review_churn_warn", "item": r["item"], "count": r["count"],
                              "latest_sha": r["latest_sha"]}), file=sys.stderr)
    if a.report:
        print(f"review-churn: REPORT {len(rows)} item(s), {len(fails)} over budget")
        return 0
    if fails:
        print(f"review-churn: FAIL ({len(fails)} item(s) over budget) - disposition instead of re-review or "
              "record a HIL-attested review_churn decision")
        return 1
    print(f"review-churn: OK ({len(rows)} completion(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
