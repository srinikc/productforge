"""Independent-verification gate (BI-PF-1413).

A DELIVERED item (or one being completed) must carry:
  - a non-empty ``verification`` (or ``evidence``) record, AND
  - a ``verified_by`` that is present and **different from** the ``worker_id`` (no self-verification).

This is the write-time closure guard's precheck counterpart. Baseline-aware via
``config/backlog-verification-baseline.json`` (grandfathered ids) so adopting the gate does not retro-fail
items already delivered before it existed; the goal is to drive the baseline to zero.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "config" / "backlog-verification-baseline.json"


def _baseline() -> set[str]:
    if BASELINE.is_file():
        try:
            return set(json.loads(BASELINE.read_text(encoding="utf-8")).get("grandfathered", []))
        except (ValueError, OSError):
            return set()
    return set()


def _scan() -> list[str]:
    from core import backlog

    bad: list[str] = []
    for it in backlog.list_open("product_forge"):
        if backlog.is_epic(it):
            continue
        if not (it.get("delivery") or str(it.get("status") or "") in ("completed", "done")):
            continue
        vb = str(it.get("verified_by") or "").strip()
        wi = str(it.get("worker_id") or "").strip()
        if not (it.get("verification") or it.get("evidence")) or not vb or (wi and vb == wi):
            bad.append(str(it.get("id")))
    return bad


def write_baseline() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    bad = _scan()
    BASELINE.write_text(json.dumps({"grandfathered": sorted(set(bad))}, indent=2) + "\n", encoding="utf-8")
    print(f"backlog-verification: wrote baseline ({len(set(bad))} grandfathered)")
    return 0


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    base = _baseline()
    bad = [i for i in _scan() if i not in base]
    if bad:
        print(f"backlog-verification: FAIL ({len(bad)} delivered item(s) without independent verification)")
        for i in bad[:15]:
            print(f"   {i}")
        print("   fix: set verification/evidence and verified_by (a verifier distinct from worker_id)")
        return 1
    print(f"backlog-verification: OK ({len(base)} grandfathered; no NEW self/unverified delivery)")
    return 0


if __name__ == "__main__":
    if "--write-baseline" in sys.argv:
        raise SystemExit(write_baseline())
    raise SystemExit(main())
