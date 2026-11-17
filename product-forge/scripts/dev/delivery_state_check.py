"""Delivery-state and RCCA closure gate (BI-PF-1538).

Code Complete -> Integration Complete -> Validation Complete -> Quality Approved
-> Delivery Complete. Gate 2/merge require Delivery Complete.

Run: python scripts/dev/delivery_state_check.py --item BI-PF-1234
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if p not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402

STATES = ("code_complete", "integration_complete", "validation_complete",
          "quality_approved", "delivery_complete")


def problems(item: dict) -> list[str]:
    bad: list[str] = []
    states = item.get("delivery_states") or {}
    for s in STATES:
        if states.get(s) is not True:
            bad.append(f"delivery state not true: {s}")
    if states.get("delivery_complete") is True:
        for s in STATES[:-1]:
            if states.get(s) is not True:
                bad.append(f"delivery_complete without {s}")
    if item.get("escaped_defect"):
        rcca = item.get("rcca") or {}
        if not rcca.get("cause") or not rcca.get("missing_control") or not rcca.get("linked_item"):
            bad.append("escaped defect requires RCCA cause, missing_control and linked_item")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Delivery-state/RCCA closure gate")
    ap.add_argument("--item", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    item = backlog.get_epic("product_forge", None, a.item)
    bad = ["item not found"] if not item else problems(item)
    out = {"ok": not bad, "item": a.item, "problems": bad}
    print(json.dumps(out, indent=2) if a.json else
          ("delivery-state: OK" if not bad else "delivery-state: FAIL\n" + "\n".join("  - " + p for p in bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
