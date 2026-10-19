"""BI-PF-1433: deterministic Gate 1 gate - the latest Gate 1.5 findings MUST be dispositioned.

Gate 1 (HIL design approval) is only valid when the Gate 1.5 findings are visible **and** every
BLOCKER/MAJOR has a disposition (actioned/accepted/deferred/rejected). Pending MINOR/NIT never block.

This renders the SAME consolidated view as the reviewer tool (no duplicate renderer) and exits:
  0  all BLOCKER/MAJOR dispositioned (Gate 1 may proceed)
  1  one or more BLOCKER/MAJOR still PENDING (Gate 1 must not proceed)
  2  no Gate 1.5 (design) review evidence exists

Run: ``python scripts/dev/gate1_check.py --item <ID>`` (add ``--json`` for machine output).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import architect_review as ar  # noqa: E402


def evaluate(item_id: str, mode: str = "design") -> dict | None:
    """Pure-ish evaluation over the latest review + the item's dispositions (no LLM calls)."""
    rev = ar._latest_review(item_id, mode)
    if not rev:
        return None
    findings = rev.get("findings") or {}
    disp = ar._item_dispositions(item_id, mode)
    total, pending, blocking = ar.pending_blocking(findings, disp)
    return {"review": rev, "dispositions": disp, "total": total,
            "pending": pending, "blocking": blocking}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate 1 check: BLOCKER/MAJOR findings must be dispositioned")
    ap.add_argument("--item", required=True)
    ap.add_argument("--mode", choices=["design", "diff"], default="design")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    res = evaluate(a.item, a.mode)
    if res is None:
        gate = "1.5" if a.mode == "design" else "2.5"
        if a.json:
            print(json.dumps({"ok": False, "reason": "no_evidence", "gate": gate}))
        else:
            print(f"gate1: FAIL - no Gate {gate} review evidence for {a.item}")
            print(f"  run: python scripts/dev/architect_review.py run --item {a.item} --mode {a.mode}")
        return 2

    if a.json:
        print(json.dumps({
            "ok": not res["blocking"],
            "item": a.item,
            "total": res["total"],
            "pending": res["pending"],
            "blocking_pending": [{"n": n, "severity": s, "finding": t} for n, s, t in res["blocking"]],
            "review_sha": res["review"].get("sha"),
            "model": res["review"].get("model"),
        }, indent=2))
    else:
        print(ar._render_review(res["review"], res["dispositions"], a.mode))
        if res["blocking"]:
            print(f"gate1: FAIL - {len(res['blocking'])} BLOCKER/MAJOR finding(s) still PENDING "
                  f"(of {res['total']} total) - disposition them before Gate 1")
        else:
            print(f"gate1: PASS - {res['total']} finding(s); no BLOCKER/MAJOR pending")
    return 0 if not res["blocking"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
