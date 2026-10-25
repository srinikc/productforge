"""BI-PF-1449: deterministic Gate 1 gate - the latest Gate 1.5 findings MUST be dispositioned.

Gate 1 (HIL design approval) is only valid when the Gate 1.5 findings are visible **and** every
BLOCKER/MAJOR has a disposition (actioned/accepted/deferred/rejected). Pending MINOR/NIT never block.

Uses the reviewer tool's public ``gate_view``/``render_gate_view`` (ONE renderer, no duplication) and exits:
  0  all BLOCKER/MAJOR dispositioned (Gate 1 may proceed)
  1  one or more BLOCKER/MAJOR still PENDING (Gate 1 must not proceed)
  2  no Gate 1.5 (design) review evidence exists

Run: ``python scripts/dev/gate1_check.py --item <ID>`` (add ``--json`` for machine output).
The same enforcement is applied by ``architect_review.py gate --item <ID> --gate 1``.
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
import design_pack as dpack  # noqa: E402


def evaluate(item_id: str) -> dict | None:
    """Gate 1.5 (design) view: review + dispositions + pending/blocking counts (no LLM calls)."""
    return ar.gate_view(item_id, "design")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate 1 check: BLOCKER/MAJOR findings must be dispositioned")
    ap.add_argument("--item", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    view = evaluate(a.item)
    if view is None:
        if a.json:
            print(json.dumps({"ok": False, "reason": "no_evidence", "gate": "1.5"}))
        else:
            print(f"gate1: FAIL - no Gate 1.5 review evidence for {a.item}")
            print(f"  run: python scripts/dev/architect_review.py run --item {a.item} --mode design")
        return 2

    if not view.get("parsed_ok", True):
        if a.json:
            print(json.dumps({"ok": False, "reason": "unparsable_evidence", "gate": "1.5"}))
        else:
            print(f"gate1: FAIL - review evidence for {a.item} could not be parsed (indeterminate); re-run the review")
        return 2

    try:
        pack_bad = []
        cfg = dpack._cfg()
        item = ar._get_item(a.item)
        if dpack.should_enforce(item, cfg):
            pack_bad = dpack.check(item)
    except Exception as e:
        pack_bad = [f"design-pack config error ({type(e).__name__}): {e}"]
    if pack_bad:
        if a.json:
            print(json.dumps({"ok": False, "reason": "design_pack", "problems": pack_bad}))
        else:
            print("gate1: FAIL - design pack incomplete")
            for p in pack_bad:
                print("  - " + p)
        return 1

    if a.json:
        print(json.dumps({
            "ok": not view["blocking"],
            "item": a.item,
            "total": view["total"],
            "pending": view["pending"],
            "blocking_pending": [{"n": n, "severity": s, "finding": t} for n, s, t in view["blocking"]],
            "review_sha": view["review"].get("sha"),
            "model": view["review"].get("model"),
            "parsed_ok": view.get("parsed_ok", True),
        }, indent=2))
    else:
        print(ar.render_gate_view(view, "design"))
        if view["blocking"]:
            print(f"gate1: FAIL - {len(view['blocking'])} BLOCKER/MAJOR finding(s) still PENDING "
                  f"(of {view['total']} total) - disposition them before Gate 1")
        else:
            print(f"gate1: PASS - {view['total']} finding(s); no BLOCKER/MAJOR pending")
    return 0 if not view["blocking"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
