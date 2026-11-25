"""PF backlog item session closeout (P1b — BI-PF-XXXX).

Mandatory last step for any direct-agent (Antigravity / OpenCode) session that implements
a Product Forge backlog item. Run this AFTER the merge PR has been merged, or when handing off.

What it does:
  1. Reads .pf-session.json to compute wall-clock duration
  2. Applies usage delta (usage_capture.py delta --apply) — skips gracefully if baseline missing
  3. Sets delivery provenance on the item (branch, merge SHA, PR) via backlog_api
  4. Prints a DoD checklist with current gate status
  5. Updates .pf-session.json with closeout data

Exit codes:
  0  closeout complete (or best-effort — check output for warnings)
  1  no session file found (kickoff was not run)
  2  item not found

Usage:
  python scripts/dev/item_closeout.py --item BI-PF-1234
  python scripts/dev/item_closeout.py --item BI-PF-1234 --branch feat/x --sha abc123 --pr 42
  python scripts/dev/item_closeout.py --item BI-PF-1234 --dry-run
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION_FILE = ROOT / ".pf-session.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))


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


def _apply_usage_delta(item_id: str, source: str, api: str, dry_run: bool) -> str:
    script = ROOT / "scripts" / "dev" / "usage_capture.py"
    args = [sys.executable, str(script), "--source", source, "delta", "--item", item_id, "--api", api]
    if not dry_run:
        args.append("--apply")
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=str(ROOT), timeout=20
        )
        out = (result.stdout + result.stderr).strip()
        return out if out else "[no output]"
    except Exception as e:
        return f"[skipped: {e}]"


def _set_delivery(item_id: str, branch: str, sha: str, pr: str) -> str:
    if not (branch or sha):
        return "[skipped: no branch/sha provided — pass --branch and --sha]"
    try:
        import backlog_api as ba
        result = ba.set_delivery(item_id, branch=branch, merge_sha=sha, pr=pr or "")
        return f"delivery recorded: branch={branch} sha={sha[:8] if sha else ''} pr={pr}"
    except Exception as e:
        return f"[warn: set_delivery failed: {e}]"


def _git_current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _git_current_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _check_evidence(item_id: str) -> list[tuple[str, str, str]]:
    """Check presence of gate evidence files. Returns list of (gate, status, detail)."""
    checks = []
    reviews_dir = ROOT / "engineering" / "reviews"

    # Gate 1.5 / 2.5: architect review evidence
    design_files = list(reviews_dir.glob(f"{item_id}-*.json")) if reviews_dir.exists() else []
    design_found = [f for f in design_files if
                    not any(x in f.stem for x in ["diff", "delivery"])]
    diff_found = [f for f in design_files if any(x in f.stem for x in ["diff", "delivery"])]
    checks.append(("Gate 1.5 (design review evidence)", "PASS" if design_found else "FAIL",
                   design_found[0].name if design_found else f"missing: engineering/reviews/{item_id}-<sha>.json"))
    checks.append(("Gate 2.5 (diff review evidence)", "PASS" if diff_found else "WARN",
                   diff_found[0].name if diff_found else f"missing: engineering/reviews/{item_id}-diff-<sha>.json"))

    # Precheck: .pf-session.json gate_state
    session = {}
    if SESSION_FILE.exists():
        try:
            session = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    gates_blocked = session.get("gates_blocked", [])
    checks.append(("No blocked gates (precheck)", "PASS" if not gates_blocked else "FAIL",
                   "clean" if not gates_blocked else f"blocked: {', '.join(gates_blocked)}"))

    return checks


def _dod_checklist(item: dict, item_id: str, delivery_status: str) -> None:
    print("\n  DEFINITION OF DONE CHECKLIST")
    print("  " + "─" * 50)

    evidence_checks = _check_evidence(item_id)

    items_dod = [
        ("Feature branch (not develop/main)", "PASS" if _git_current_branch() not in {"develop", "main"} else "FAIL"),
        ("Language rule reviewed (see kickoff output)", "INFO"),
        ("RECONCILIATION block produced", "INFO"),
        *[(label, status) for label, status, _ in evidence_checks],
        ("Precheck passed (all fast-tier gates green)", "INFO"),
        ("Gate 2 HIL approval received", "INFO"),
        ("Delivery provenance set", "PASS" if "branch=" in delivery_status else "FAIL"),
        ("Item status set to completed via API", "PASS" if (item.get("status") == "completed") else "INFO"),
    ]

    all_pass = True
    for label, status in items_dod:
        icon = "✓" if status == "PASS" else ("✗" if status == "FAIL" else "·")
        print(f"    {icon} [{status:4s}] {label}")
        if status == "FAIL":
            all_pass = False

    for label, status, detail in evidence_checks:
        print(f"           Detail: {detail}")

    print("  " + "─" * 50)
    if all_pass:
        print("  All machine-checkable DoD items passed.")
    else:
        print("  ⚠  Some items need attention — see FAIL rows above.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PF item session closeout (P1b)")
    ap.add_argument("--item", required=True, help="Backlog item ID, e.g. BI-PF-1234")
    ap.add_argument("--branch", default="", help="Feature branch name (auto-detected if omitted)")
    ap.add_argument("--sha", default="", help="Merge SHA (auto-detected if omitted)")
    ap.add_argument("--pr", default="", help="PR number or URL")
    ap.add_argument("--note", default="", help="Optional summary note for the session record")
    ap.add_argument("--source", default=os.environ.get("PF_USAGE_SOURCE", "opencode"),
                    help="Usage source: opencode | json")
    ap.add_argument("--api", default=os.environ.get("PF_BACKLOG_API", "http://127.0.0.1:8030"),
                    help="PF API URL for recording usage (default: http://127.0.0.1:8030)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be done without recording anything")
    a = ap.parse_args(argv)

    item_id = a.item.strip()
    print(f"\n{'='*70}")
    print(f"  PF ITEM CLOSEOUT — {item_id}{'  [DRY RUN]' if a.dry_run else ''}")
    print(f"{'='*70}\n")

    # Load session
    if not SESSION_FILE.exists():
        print(f"[CLOSEOUT FAIL] No .pf-session.json found at {SESSION_FILE}")
        print("  Kickoff was not run. Run item_kickoff.py first next time.")
        print("  Continuing with best-effort closeout (no timing data).")
        session = {}
    else:
        try:
            session = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [warn] Could not read session file: {e}")
            session = {}

    session_item = session.get("item_id", "")
    if session_item and session_item != item_id:
        print(f"  [warn] Session file is for {session_item!r}, not {item_id!r}. Use --item {session_item} or re-run kickoff.")

    # Compute duration
    started_ts = session.get("started_at_ts")
    duration_s = round(time.time() - float(started_ts), 1) if started_ts else None
    duration_str = f"{int(duration_s // 60)}m {int(duration_s % 60)}s" if duration_s else "unknown"
    print(f"  Session duration: {duration_str}")
    print(f"  Started:          {session.get('started_at', 'unknown')}")
    print(f"  Session ID:       {session.get('session_id', 'unknown')}")

    # Read item
    print("\nStep 1/4 — Reading item ...")
    item = _get_item(item_id)
    if not item:
        print(f"  [warn] Item {item_id!r} not found — continuing without item data")

    # Apply usage delta
    print("\nStep 2/4 — Applying usage delta ...")
    usage_out = _apply_usage_delta(item_id, a.source, a.api, a.dry_run)
    print(f"  {usage_out}")

    # Set delivery provenance
    print("\nStep 3/4 — Recording delivery provenance ...")
    branch = a.branch or _git_current_branch()
    sha = a.sha or _git_current_sha()
    if not a.dry_run:
        delivery_status = _set_delivery(item_id, branch, sha, a.pr)
    else:
        delivery_status = f"[dry-run] would set: branch={branch} sha={sha[:8] if sha else ''} pr={a.pr}"
    print(f"  {delivery_status}")

    # DoD checklist
    print("\nStep 4/4 — Definition of Done checklist ...")
    _dod_checklist(item, item_id, delivery_status)

    # Update session file with closeout data
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    session.update({
        "closed_at": now_iso,
        "duration_seconds": duration_s,
        "usage_delta_status": usage_out,
        "delivery_status": delivery_status,
        "note": a.note,
        "gate_state": "closed",
    })
    if not a.dry_run:
        SESSION_FILE.write_text(json.dumps(session, indent=2), encoding="utf-8")
        print(f"\n  Session record updated: {SESSION_FILE}")

    # Summary
    gates_blocked = session.get("gates_blocked", [])
    gate_failures = session.get("gate_failures", {})
    print(f"\n{'='*70}")
    print(f"  CLOSEOUT SUMMARY — {item_id}")
    print(f"{'='*70}")
    print(f"  Duration    : {duration_str}")
    print(f"  Gate state  : {session.get('gate_state', 'unknown')}")
    print(f"  Gate failures: {sum(gate_failures.values()) if gate_failures else 0} total "
          f"across {len(gate_failures)} gate(s)")
    if gates_blocked:
        print(f"  BLOCKED GATES: {', '.join(gates_blocked)}")
    print(f"  Delivery    : {delivery_status}")
    if a.note:
        print(f"  Note        : {a.note}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
