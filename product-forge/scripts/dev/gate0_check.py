"""Gate 0 - take-up completeness (BI-PF-1471).

An item entering `new -> in_progress` must carry the decision-ready context BEFORE work starts:
  * reconciliation: prior_decisions, existing_path, assumptions, divergences, open_questions;
  * impact review table: claim | verdict | evidence | recommendation, including API and AC rows;
  * language decision and an api_impact decision (needs_api + reason).

`--report` is a dry-run (exit 0). The table is printed for the HIL.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "dev"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

VERDICTS = {"aligned", "violates", "new-path", "derails", "stale"}
REC_KEYS = ("prior_decisions", "existing_path", "assumptions", "divergences", "open_questions")


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    return (r.stdout or "").strip()


def transitions(base: str = "") -> list[dict]:
    base = base or _git("merge-base", "develop", "HEAD") or "origin/develop"
    out = []
    for rel in _git("diff", "--name-only", f"{base}..HEAD").splitlines():
        rel = rel.replace("\\", "/")
        if "/data/backlog/items/" not in rel or not rel.endswith(".json"):
            continue
        try:
            cur = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(cur.get("status") or "") != "in_progress":
            continue
        try:
            prev = json.loads(_git("show", f"{base}:{rel}") or "{}")
        except Exception:
            prev = {}
        if str(prev.get("status") or "") != "in_progress":
            out.append(cur)
    return out


def problems(item: dict) -> list[str]:
    bad: list[str] = []
    rec = ((item.get("review") or {}).get("reconciliation") or {})
    for k in REC_KEYS:
        if not rec.get(k):
            bad.append(f"reconciliation.{k} is empty")
    rows = ((item.get("review") or {}).get("impact_review") or [])
    if not rows:
        bad.append("impact_review table is missing")
    for r in rows:
        if not isinstance(r, dict):
            bad.append("impact_review row is not an object")
            continue
        for k in ("claim", "verdict", "evidence", "recommendation"):
            if not str(r.get(k) or "").strip():
                bad.append(f"impact_review row missing {k}")
        if str(r.get("verdict") or "").lower() not in VERDICTS:
            bad.append(f"impact_review verdict {r.get('verdict')!r} is not one of {sorted(VERDICTS)}")
    claims = " ".join(str(r.get("claim") or "").lower() for r in rows if isinstance(r, dict))
    if "api" not in claims:
        bad.append("impact_review has no API CHECK row")
    if "ac" not in claims and "acceptance" not in claims:
        bad.append("impact_review has no AC row")
    if "language" not in claims and not str(item.get("language_rule") or "").strip():
        bad.append("no language-rule decision")
    api = item.get("api_impact") or {}
    if "needs_api" not in api or not str(api.get("reason") or "").strip():
        bad.append("api_impact decision (needs_api + reason) missing")
    return bad


def render(item: dict) -> str:
    rec = ((item.get("review") or {}).get("reconciliation") or {})
    lines = [f"RECONCILIATION - {item.get('id')}",
             f"  prior_decisions : {rec.get('prior_decisions')}",
             f"  existing_path   : {rec.get('existing_path')}",
             f"  assumptions     : {rec.get('assumptions')}",
             f"  divergences     : {rec.get('divergences')}",
             f"  open_questions  : {rec.get('open_questions')}",
             "IMPACT REVIEW",
             "  claim | verdict | evidence | recommendation"]
    for r in ((item.get("review") or {}).get("impact_review") or []):
        lines.append(f"  {r.get('claim')} | {r.get('verdict')} | {r.get('evidence')} | {r.get('recommendation')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate 0 take-up completeness")
    ap.add_argument("--report", action="store_true", help="dry-run: report only, exit 0")
    ap.add_argument("--base", default="")
    a = ap.parse_args(argv)
    items = transitions(a.base)
    problems_all = []
    for it in items:
        print(render(it))
        bad = problems(it)
        problems_all.extend(f"{it.get('id')}: {b}" for b in bad)
    if a.report:
        print(f"gate0: REPORT {len(items)} transition(s), {len(problems_all)} problem(s)")
        return 0
    if problems_all:
        print(f"gate0: FAIL ({len(problems_all)} problem(s))")
        for p in problems_all:
            print("   - " + p)
        return 1
    print(f"gate0: OK ({len(items)} transition(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
