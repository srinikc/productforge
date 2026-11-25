"""PF backlog item session kickoff (P1a — BI-PF-XXXX).

Mandatory first step for any direct-agent (Antigravity / OpenCode) session that implements
a Product Forge backlog item. Run this BEFORE writing any code.

What it does:
  1. Reads and prints the full item (title, AC, in_scope, out_of_scope, affected_files, deps)
  2. Runs language_rule_review.py and prints the verdict
  3. Takes a usage snapshot (usage_capture.py snapshot) — skips gracefully if unavailable
  4. Writes start_time + session_id to .pf-session.json at the repo root
  5. Prints a KICKOFF COMPLETE banner with the RECONCILIATION block template

Exit codes:
  0  kickoff succeeded — agent may proceed to RECONCILIATION block
  1  item not in a startable state (not new/accepted/queued)
  2  item not found

Usage:
  python scripts/dev/item_kickoff.py --item BI-PF-1234
  python scripts/dev/item_kickoff.py --item BI-PF-1234 --source json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION_FILE = ROOT / ".pf-session.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))

STARTABLE_STATUSES = {"new", "accepted", "queued", "scheduled"}


def _get_item(item_id: str) -> dict:
    try:
        import backlog_api as ba
        return ba.get_item(item_id) or {}
    except Exception:
        try:
            from core import backlog as _b
            return _b.get_epic("product_forge", None, item_id) or {}
        except Exception:
            return {}


def _run_language_check(item_id: str) -> tuple[int, str]:
    """Run language_rule_review.py and return (exit_code, output)."""
    script = ROOT / "scripts" / "dev" / "language_rule_review.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script), item_id],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30
        )
        out = (result.stdout + result.stderr).strip()
        return result.returncode, out
    except Exception as e:
        return 3, f"language_rule_review failed: {e}"


def _take_usage_snapshot(item_id: str, source: str) -> str:
    """Take a usage snapshot; returns a status string."""
    script = ROOT / "scripts" / "dev" / "usage_capture.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--source", source, "snapshot", "--item", item_id],
            capture_output=True, text=True, cwd=str(ROOT), timeout=15
        )
        if result.returncode == 0:
            return result.stdout.strip()
        # Non-zero is usually "opencode usage db not found" — not fatal
        return f"[skipped: {result.stderr.strip()[:120]}]"
    except Exception as e:
        return f"[skipped: {e}]"


def _write_session(item_id: str, item: dict, usage_status: str) -> dict:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    session = {
        "item_id": item_id,
        "started_at": now_iso,
        "started_at_ts": time.time(),
        "session_id": str(uuid.uuid4()),
        "usage_source_status": usage_status,
        "gate_state": "kickoff",
        "gates_attempted": [],
        "gate_failures": {},
        "gates_blocked": [],
    }
    # Persist (overwrite any stale session)
    SESSION_FILE.write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session


def _print_item_summary(item: dict) -> None:
    sep = "─" * 70
    print(sep)
    print(f"  ITEM   : {item.get('external_id') or item.get('id', 'unknown')}")
    print(f"  TITLE  : {item.get('title', '')}")
    print(f"  STATUS : {item.get('status', '')}")
    print(f"  EPIC   : {item.get('epic', 'none')}")
    ac = item.get("acceptance_criteria") or []
    if ac:
        print("  AC:")
        for c in ac:
            print(f"      • {c}")
    scope_in = item.get("in_scope") or item.get("context", {}).get("in_scope") or []
    scope_out = item.get("out_of_scope") or item.get("context", {}).get("out_of_scope") or []
    affected = item.get("affected_files") or item.get("context", {}).get("affected_files") or []
    deps = item.get("depends_on") or item.get("context", {}).get("depends_on") or []
    if affected:
        print(f"  AFFECTED_FILES ({len(affected)}):")
        for f in affected[:20]:
            print(f"      {f}")
        if len(affected) > 20:
            print(f"      ... and {len(affected) - 20} more")
    if scope_in:
        print(f"  IN_SCOPE: {', '.join(scope_in)}")
    if scope_out:
        print(f"  OUT_OF_SCOPE: {', '.join(scope_out)}")
    if deps:
        print(f"  DEPS: {', '.join(str(d) for d in deps)}")
    print(sep)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PF item session kickoff (P1a)")
    ap.add_argument("--item", required=True, help="Backlog item ID, e.g. BI-PF-1234")
    ap.add_argument("--source", default=os.environ.get("PF_USAGE_SOURCE", "opencode"),
                    help="usage source: opencode | json  (default: opencode)")
    ap.add_argument("--force", action="store_true",
                    help="Allow kickoff even if item is not in a startable status")
    a = ap.parse_args(argv)

    item_id = a.item.strip()
    print(f"\n{'='*70}")
    print(f"  PF ITEM KICKOFF — {item_id}")
    print(f"{'='*70}\n")

    # 1. Read item
    print("Step 1/4 — Reading item from backlog ...")
    item = _get_item(item_id)
    if not item:
        print(f"\n[KICKOFF FAIL] Item {item_id!r} not found in backlog.")
        print("  Check the ID and ensure the PF backlog data is accessible.")
        return 2

    _print_item_summary(item)

    # Status gate
    status = item.get("status", "")
    if status not in STARTABLE_STATUSES and not a.force:
        print(f"\n[KICKOFF FAIL] Item {item_id} is in status '{status}' — not startable.")
        print(f"  Startable statuses: {', '.join(sorted(STARTABLE_STATUSES))}")
        print(f"  Use --force to override (e.g. resuming an in_progress item).")
        return 1

    # 2. Language rule check
    print("\nStep 2/4 — Running language rule review ...")
    lang_rc, lang_out = _run_language_check(item_id)
    print(lang_out or "(no output)")
    lang_verdict = "PASS" if lang_rc == 0 else ("FAIL" if lang_rc == 1 else "WARN/SKIP")
    print(f"  Language rule verdict: {lang_verdict}")

    # 3. Usage snapshot
    print("\nStep 3/4 — Taking usage snapshot ...")
    usage_status = _take_usage_snapshot(item_id, a.source)
    print(f"  {usage_status}")

    # 4. Write session state
    print("\nStep 4/4 — Writing session state to .pf-session.json ...")
    session = _write_session(item_id, item, usage_status)
    print(f"  session_id: {session['session_id']}")
    print(f"  started_at: {session['started_at']}")
    print(f"  gate_state: {session['gate_state']}")

    # Done
    print(f"\n{'='*70}")
    print(f"  KICKOFF COMPLETE — {item_id}")
    print(f"{'='*70}")
    print("""
NEXT: Produce your RECONCILIATION block BEFORE writing any code.
Required sections (paste this template, fill it in):

## RECONCILIATION — {item_id}

### PRIOR DECISIONS
  (List any design decisions already made in past sessions or related items)

### EXISTING PATH
  (Describe what already exists in the codebase that this item builds on or changes)

### ASSUMPTIONS
  (State any assumptions you are making about scope, behaviour, or design)

### DIVERGENCES
  (Note anything that differs from the original plan or existing patterns)

### OPEN QUESTIONS
  (List anything that needs HIL resolution before proceeding)

After completing the RECONCILIATION block, present it and WAIT for operator approval.
Then proceed to: python scripts/dev/architect_review.py run --item {item_id} --mode design
""".replace("{item_id}", item_id))

    if lang_verdict == "FAIL":
        print("  ⚠  LANGUAGE RULE FAIL — the item requires Go for new shipped logic.")
        print("     Verify: will any new Python be added to core/ ? If yes → Go only.")
        print("     Edits to existing shipped Python and all tooling scripts are OK.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
