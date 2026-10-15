"""API-first enforcement gate (ADR-0007/0008; BI-PF-1404).

Every NEW backlog item (i.e. not grandfathered at the gate's introduction) must record an
``api_impact`` DECISION: ``needs_api`` (true/false) plus a reason (and route(s) when true). Reuses
``core.backlog.api_impact_warnings()`` so there is a single source for the decision logic.

Baseline-aware: ``config/api-first-baseline.json`` grandfathers items that predate the gate, so adopting
the gate does not retro-fail the existing backlog.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "config" / "api-first-baseline.json"


def grandfathered() -> set[str]:
    if BASELINE.is_file():
        try:
            return set(json.loads(BASELINE.read_text(encoding="utf-8")).get("grandfathered", []) or [])
        except (ValueError, OSError):
            return set()
    return set()


def _id_of(warning: object) -> str:
    return str(warning).split(":", 1)[0].strip()


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from core import backlog

    base = grandfathered()
    warns = list(backlog.api_impact_warnings() or [])
    new = [w for w in warns if _id_of(w) not in base]
    if new:
        print(f"api-first: FAIL ({len(new)} new item(s) without an api_impact decision)")
        for w in new[:20]:
            print(f"   {w}")
        if len(new) > 20:
            print(f"   ... and {len(new) - 20} more")
        print("   fix: set api_impact (needs_api + reason; routes when true) via the backlog API")
        return 1
    print(f"api-first: OK ({len(base)} grandfathered; no NEW item missing an api_impact decision)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
