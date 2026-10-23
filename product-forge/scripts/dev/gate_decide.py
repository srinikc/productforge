"""Record a Gate 1 / Gate 2 HIL decision (BI-PF-1469).

The only supported way to record an approval: it validates the current evidence (Gate 1.5 design for gate 1,
Gate 2.5 diff for gate 2), requires zero PENDING BLOCKER/MAJOR, and binds findings_sha + findings_digest +
a monotonic seq to the decision.

Usage:
  python scripts/dev/gate_decide.py --item BI-PF-1234 --gate 1 --decision APPROVE_WITH_ATTENTION \
      --by hil:<actor> --note "design reviewed"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import backlog  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record a Gate 1/2 decision")
    ap.add_argument("--item", required=True)
    ap.add_argument("--gate", type=int, choices=(1, 2), required=True)
    ap.add_argument("--decision", required=True, choices=("APPROVE", "APPROVE_WITH_ATTENTION"))
    ap.add_argument("--by", required=True, help="hil:<actor>")
    ap.add_argument("--note", default="")
    ap.add_argument("--scope", default="product_forge")
    ap.add_argument("--project", default="")
    a = ap.parse_args(argv)
    res = backlog.record_gate_decision(a.scope, a.project or None, a.item, a.gate, a.decision, a.by, a.note)
    if not res:
        print(json.dumps({"ok": False, "item": a.item, "gate": a.gate}))
        return 1
    print(json.dumps({"ok": True, "item": a.item, "gate": a.gate, "decision": a.decision}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
