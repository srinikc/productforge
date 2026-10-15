"""Hard DoD gate (BI-PF-1410): detailed Acceptance Criteria + independent verification.

Two baseline-aware checks (grandfathered id lists live in ``config/backlog-dod-baseline.json`` so adopting
the gate does not retro-fail the existing backlog; the goal is to drive both lists to zero):

  1. AC: every non-epic, non-legacy OPEN item must have >= 1 acceptance criterion, each >= MIN_AC chars.
  2. VERIFICATION: every DELIVERED item (carries ``delivery``) must carry a non-empty ``verification`` or
     ``evidence`` record - proof produced and checked outside the implementation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "config" / "backlog-dod-baseline.json"
MIN_AC = 40


def _baseline() -> tuple[set[str], set[str]]:
    if BASELINE.is_file():
        try:
            d = json.loads(BASELINE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return set(), set()
        return set(d.get("ac_grandfathered", [])), set(d.get("verification_grandfathered", []))
    return set(), set()


def _scan() -> tuple[list[str], list[str]]:
    from core import backlog

    bad_ac: list[str] = []
    bad_ver: list[str] = []
    for it in backlog.list_open("product_forge"):
        if backlog.is_epic(it):
            continue
        iid = str(it.get("id"))
        ac = [str(x).strip() for x in (it.get("acceptance_criteria") or [])]
        if not ac or any(len(x) < MIN_AC for x in ac):
            bad_ac.append(iid)
        if it.get("delivery") and not (it.get("verification") or it.get("evidence")):
            bad_ver.append(iid)
    return bad_ac, bad_ver


def write_baseline() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    bad_ac, bad_ver = _scan()
    BASELINE.write_text(json.dumps(
        {"ac_grandfathered": sorted(set(bad_ac)), "verification_grandfathered": sorted(set(bad_ver))},
        indent=2) + "\n", encoding="utf-8")
    print(f"backlog-dod: wrote baseline (ac={len(set(bad_ac))}, verification={len(set(bad_ver))})")
    return 0


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from core import backlog

    ac_base, ver_base = _baseline()
    items = backlog.list_open("product_forge")
    bad_ac: list[str] = []
    bad_ver: list[str] = []
    for it in items:
        if backlog.is_epic(it):
            continue
        iid = str(it.get("id"))
        ac = [str(x).strip() for x in (it.get("acceptance_criteria") or [])]
        if (not ac or any(len(x) < MIN_AC for x in ac)) and iid not in ac_base:
            bad_ac.append(iid)
        if it.get("delivery") and iid not in ver_base and not (it.get("verification") or it.get("evidence")):
            bad_ver.append(iid)

    if bad_ac or bad_ver:
        print(f"backlog-dod: FAIL (ac_missing={len(bad_ac)}, delivered_without_verification={len(bad_ver)})")
        for i in bad_ac[:12]:
            print(f"   no detailed AC: {i}")
        for i in bad_ver[:12]:
            print(f"   delivered but no verification/evidence: {i}")
        print("   fix: set acceptance_criteria (>=1, each >=40 chars) and, on delivery, verification/evidence")
        return 1
    print(f"backlog-dod: OK (open={len(items)}; grandfathered ac={len(ac_base)}, verification={len(ver_base)})")
    return 0


if __name__ == "__main__":
    if "--write-baseline" in sys.argv:
        raise SystemExit(write_baseline())
    raise SystemExit(main())
