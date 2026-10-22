"""BI-PF-1467 (RCCA): design-time guardrails - CLI view of ``core.design_guardrails``.

The rendering logic is owned by ``core/design_guardrails.py`` (grooming uses it directly). This script is the
author-facing view over the API-backed backlog.

Usage:
  python scripts/dev/design_guardrails.py --item <ID>            # print the block (author reads it)
  python scripts/dev/design_guardrails.py --item <ID> --record   # store it on the item evidence (idempotent)
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

from core.design_guardrails import (  # noqa: E402,F401  (re-exported for callers/tests)
    block_digest, checklist, item_text, ledger_rules, recurring, relevant_rules, render,
)


def _record(item_id: str, block: str) -> bool:
    import backlog_api as ba  # lazy: pulls the API app
    item = ba.get_item(item_id) or {}
    marker = f"Design guardrails applied ({item_id}):"
    ev = list(item.get("evidence") or [])
    if any(str(x).startswith(marker) for x in ev):
        return False
    ev.append(f"{marker} sig:{block_digest(block)} ({len(block.splitlines())} lines)")
    ba.set_context(item_id, {"evidence": ev})
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Design-time guardrails (BI-PF-1467)")
    ap.add_argument("--item", required=True)
    ap.add_argument("--record", action="store_true", help="store the applied guardrails on item evidence (idempotent)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    import backlog_api as ba
    item = ba.get_item(a.item) or {}
    block = render(item, a.item)
    if a.json:
        print(json.dumps({"item": a.item, "rules": [r["id"] for r in relevant_rules(item_text(item), ledger_rules())],
                          "recurring": len(recurring()), "block": block}, indent=2))
    else:
        print(block)
    if a.record:
        print("recorded on item evidence" if _record(a.item, block) else "already recorded (idempotent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
