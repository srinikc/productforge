"""Completion gate for the backlog execution trail (BI-PF-1481).

For every item completing in the committed diff, require the pre-merge stages in order and a follow-up
item id for every DEFERRED disposition. Run as a POST-precheck gate (after the precheck runner has written
the tests/precheck events) so it never races its own evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "dev"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core import execution_trail as trail  # noqa: E402
import gate2_completion_check as g2  # noqa: E402

FOLLOW_UP = re.compile(r"BI-(?:[A-Za-z0-9]+-)?\d+")


def deferred_problems(item: dict) -> list[str]:
    bad = []
    for mode, rows in ((item.get("review_dispositions") or {}) or {}).items():
        if not isinstance(rows, dict):
            continue
        for key, d in rows.items():
            if str((d or {}).get("status") or "").upper() != "DEFERRED":
                continue
            note = str((d or {}).get("note") or "")
            m = FOLLOW_UP.search(note)
            if not m:
                bad.append(f"{mode}/{key}: DEFERRED without a follow-up item id (BI-PF-...) in the note")
                continue
            try:
                from core import backlog
                if backlog.get_epic("product_forge", None, m.group(0)) is None:
                    bad.append(f"{mode}/{key}: follow-up {m.group(0)} does not exist in the backlog")
            except Exception as e:
                bad.append(f"{mode}/{key}: cannot verify follow-up {m.group(0)}: {e}")
    return bad


def evaluate(ids: list[str]) -> list[str]:
    problems = []
    for iid in ids:
        try:
            item = g2.ar._get_item(iid)
        except Exception as e:
            problems.append(f"{iid}: cannot read item: {e}")
            continue
        missing = trail.missing_stages(iid)
        if missing:
            problems.append(f"{iid}: missing stages: {', '.join(missing)}")
        for p in trail.order_problems(iid):
            problems.append(f"{iid}: {p}")
        problems += [f"{iid}: {p}" for p in deferred_problems(item)]
        failures = trail.TRAILS / "_failures.jsonl"
        if failures.is_file():
            for line in failures.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("item") == iid:
                    problems.append(f"{iid}: trail write failure at {ev.get('stage')}: {ev.get('error')}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backlog execution-trail completion gate")
    ap.add_argument("--base", default="")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    base = a.base or g2._git("merge-base", "develop", "HEAD")
    if not base:
        for ref in ("origin/develop",):
            try:
                base = g2._git("merge-base", ref, "HEAD")
            except Exception:
                base = ""
            if base:
                break
    if not base:
        print("execution-trail: skipped (base ref unavailable; fetch develop or pass --base)")
        return 0
    try:
        ids = g2.transitions(base)
    except Exception as e:
        print(f"execution-trail: ERROR {e}", file=sys.stderr)
        return 2
    problems = evaluate(ids)
    for p in problems:
        print("   - " + p)
    if a.report:
        print(f"execution-trail: REPORT {len(ids)} completion(s), {len(problems)} problem(s)")
        return 0
    if problems:
        print(f"execution-trail: FAIL ({len(problems)} problem(s))")
        return 1
    print(f"execution-trail: OK ({len(ids)} completion(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
