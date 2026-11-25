"""PF backlog item session state machine (P2a — BI-PF-XXXX).

Provides a machine-enforced state machine for the PF backlog item implementation lifecycle.
Agents call this to get the NEXT required step, record gate stamps, and track gate failures.
All state is persisted in .pf-session.json at the repo root.

Gate chain (from docs/REVIEW-GATES-LIFECYCLE.md):
  kickoff → language_check → gate_1.5_design → [HIL: gate_1_approval] →
  implement → gate_2.5_delivery → [HIL: gate_2_approval] →
  precheck_fast → merge → closeout

Commands:
  next                  Print the next required step (what to do now)
  status                Print full session state
  advance --to <state>  Advance to the named state (records timestamp)
  record-gate-pass --gate <name>   Record a gate passing
  record-gate-fail --gate <name>   Record a gate failure (increments counter; prints BLOCKED if > 2)
  reset-gate --gate <name>         Reset failure counter for a gate (after a successful fix)

Exit codes:
  0  success
  1  blocked (gate failed > 2 times) — agent should STOP and report BLOCKED
  2  no session (run item_kickoff.py first)

Usage:
  python scripts/dev/session_state.py next
  python scripts/dev/session_state.py status
  python scripts/dev/session_state.py advance --to gate_1.5_design
  python scripts/dev/session_state.py record-gate-pass --gate precheck-wired-audit
  python scripts/dev/session_state.py record-gate-fail --gate precheck-language-rule
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION_FILE = ROOT / ".pf-session.json"

# Ordered state machine
STATES = [
    "kickoff",
    "language_check",
    "gate_1.5_design",
    "gate_1_approval",
    "implement",
    "gate_2.5_delivery",
    "gate_2_approval",
    "precheck_fast",
    "merge",
    "closeout",
    "closed",
]

STATE_DESCRIPTIONS = {
    "kickoff":           "Run item_kickoff.py --item <ID>",
    "language_check":    "Review language_rule_review.py output from kickoff; note verdict",
    "gate_1.5_design":   "Run: python scripts/dev/architect_review.py run --item <ID> --mode design\n"
                         "     Then: python scripts/dev/gate1_check.py --item <ID>",
    "gate_1_approval":   "[HIL] Present RECONCILIATION block + Gate 1.5 findings to operator. WAIT for approval.",
    "implement":         "Create feature branch. Implement ONLY files in item's in_scope/affected_files.\n"
                         "     Wire every new module. Add tests. Commit incrementally.",
    "gate_2.5_delivery": "Run: python scripts/dev/architect_review.py run --item <ID> --mode diff\n"
                         "     Commit the evidence file.",
    "gate_2_approval":   "[HIL] Present Gate 2.5 delivery review to operator. WAIT for approval.",
    "precheck_fast":     "Run: python scripts/dev/precheck.py\n"
                         "     Fix ONE failing group at a time. Max 2 attempts per gate → BLOCKED.",
    "merge":             "Open PR → merge to develop (operator-approved).",
    "closeout":          "Run: python scripts/dev/item_closeout.py --item <ID> --branch <B> --sha <S> --pr <PR>",
    "closed":            "Session complete.",
}

# States that REQUIRE HIL (agent must wait for human)
HIL_STATES = {"gate_1_approval", "gate_2_approval", "merge"}

MAX_FAILURES_BEFORE_BLOCKED = 2
MAX_REVIEW_CYCLES = 2  # Fix R3: hard cap on Gate 1.5/2.5 delta review rounds


def cmd_record_review_cycle(session: dict, gate: str) -> int:
    """Fix R3: increment review cycle counter; HARD STOP at MAX_REVIEW_CYCLES."""
    item_id = session.get("item_id", "<item>")
    key = f"review_cycles_{gate.replace('.', '_')}"
    count = session.get(key, 0) + 1
    session[key] = count
    _save_session(session)

    if count >= MAX_REVIEW_CYCLES:
        print(f"\n{'!'*70}")
        print(f"  🛑 HARD STOP: review cycle cap reached ({count}/{MAX_REVIEW_CYCLES} for gate_{gate}).")
        print(f"  Remaining PENDING findings require HIL disposition. Do NOT run another review.")
        print(f"  List all PENDING findings → present to HIL → record as WONTFIX/DEFERRED/escalate.")
        print(f"{'!'*70}\n")
        return 1

    remaining = MAX_REVIEW_CYCLES - count
    print(f"[session_state] {item_id}: review cycle {count}/{MAX_REVIEW_CYCLES} for gate {gate} "
          f"({remaining} delta round(s) remaining)")
    return 0


def _load_session() -> dict | None:
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_session(session: dict) -> None:
    SESSION_FILE.write_text(json.dumps(session, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _next_state(current: str) -> str | None:
    try:
        idx = STATES.index(current)
        return STATES[idx + 1] if idx + 1 < len(STATES) else None
    except ValueError:
        return STATES[0]


def cmd_next(session: dict) -> int:
    state = session.get("gate_state", "kickoff")
    item_id = session.get("item_id", "<item>")
    blocked = session.get("gates_blocked", [])

    print(f"\n{'─'*70}")
    print(f"  SESSION: {item_id}  |  Current gate: {state}")
    print(f"{'─'*70}")

    if blocked:
        print(f"\n  🛑 BLOCKED GATES: {', '.join(blocked)}")
        print("     The agent must STOP and request HIL assistance for blocked gates.")
        print("     Use 'session_state.py reset-gate --gate <name>' after the fix.")
        return 1

    if state == "closed":
        print("  ✓ Session is CLOSED. All done.")
        return 0

    desc = STATE_DESCRIPTIONS.get(state, "unknown state")
    print(f"\n  NEXT REQUIRED STEP: {state}")
    print(f"  {'─'*50}")
    for line in desc.replace("<ID>", item_id).splitlines():
        print(f"  {line}")

    next_st = _next_state(state)
    if next_st:
        print(f"\n  After completing this step, run:")
        print(f"    python scripts/dev/session_state.py advance --to {next_st}")

    if state in HIL_STATES:
        print(f"\n  ⚠  HIL GATE — do NOT proceed until operator provides explicit approval.")

    timestamps = session.get("gate_timestamps", {})
    if timestamps:
        print(f"\n  Completed gates:")
        for s, ts in timestamps.items():
            print(f"    ✓ {s:<25} at {ts}")

    print()
    return 0


def cmd_status(session: dict) -> int:
    item_id = session.get("item_id", "<item>")
    state = session.get("gate_state", "kickoff")
    blocked = session.get("gates_blocked", [])
    failures = session.get("gate_failures", {})
    timestamps = session.get("gate_timestamps", {})

    print(f"\n{'='*70}")
    print(f"  SESSION STATUS — {item_id}")
    print(f"{'='*70}")
    print(f"  Gate state  : {state}")
    print(f"  Started     : {session.get('started_at', 'unknown')}")
    print(f"  Session ID  : {session.get('session_id', 'unknown')}")
    print(f"  Blocked     : {', '.join(blocked) if blocked else 'none'}")

    if failures:
        print(f"\n  Gate failure counts:")
        for g, cnt in sorted(failures.items()):
            status = "BLOCKED" if g in blocked else f"{cnt}/{MAX_FAILURES_BEFORE_BLOCKED}"
            print(f"    {g:<35} {status}")

    if timestamps:
        print(f"\n  Gate timestamps:")
        for s, ts in timestamps.items():
            print(f"    {s:<25} {ts}")

    print(f"\n  Full gate chain:")
    for s in STATES:
        marker = "→" if s == state else ("✓" if s in timestamps else " ")
        hil = " [HIL]" if s in HIL_STATES else ""
        print(f"    {marker} {s}{hil}")

    print()
    return 1 if blocked else 0


def cmd_advance(session: dict, to_state: str) -> int:
    if to_state not in STATES:
        print(f"[session_state] Unknown state {to_state!r}. Valid: {', '.join(STATES)}")
        return 2

    current = session.get("gate_state", "kickoff")
    item_id = session.get("item_id", "<item>")

    # Validate ordering
    try:
        cur_idx = STATES.index(current)
        to_idx = STATES.index(to_state)
    except ValueError:
        cur_idx, to_idx = 0, 0

    if to_idx <= cur_idx and to_state != current:
        print(f"[session_state] Cannot advance backwards: {current} → {to_state}")
        print(f"  (Forward advance only. Use reset-gate to retry a gate.)")
        return 2

    # Record timestamp on current state before advancing
    timestamps = session.setdefault("gate_timestamps", {})
    if current not in timestamps:
        timestamps[current] = _now_iso()

    session["gate_state"] = to_state
    _save_session(session)

    print(f"[session_state] {item_id}: advanced {current} → {to_state} at {_now_iso()}")

    if to_state in HIL_STATES:
        print(f"  ⚠  HIL GATE — do NOT proceed until operator provides explicit approval.")

    desc = STATE_DESCRIPTIONS.get(to_state, "")
    if desc:
        for line in desc.replace("<ID>", item_id).splitlines():
            print(f"  {line}")

    return 0


def cmd_record_gate_pass(session: dict, gate: str) -> int:
    item_id = session.get("item_id", "<item>")
    # Clear failure count for this gate on success
    failures = session.setdefault("gate_failures", {})
    if gate in failures:
        del failures[gate]
    blocked = session.get("gates_blocked", [])
    if gate in blocked:
        blocked.remove(gate)
    session["gates_blocked"] = blocked

    attempts = session.setdefault("gates_attempted", [])
    attempts.append({"gate": gate, "result": "pass", "ts": _now_iso()})

    _save_session(session)
    print(f"[session_state] {item_id}: gate PASS — {gate}")
    return 0


def cmd_record_gate_fail(session: dict, gate: str) -> int:
    item_id = session.get("item_id", "<item>")
    failures = session.setdefault("gate_failures", {})
    failures[gate] = failures.get(gate, 0) + 1
    count = failures[gate]

    attempts = session.setdefault("gates_attempted", [])
    attempts.append({"gate": gate, "result": "fail", "attempt": count, "ts": _now_iso()})

    if count > MAX_FAILURES_BEFORE_BLOCKED:
        blocked = session.setdefault("gates_blocked", [])
        if gate not in blocked:
            blocked.append(gate)
        _save_session(session)
        print(f"\n{'!'*70}")
        print(f"  🛑 BLOCKED: {gate} (failed {count} times — exceeded {MAX_FAILURES_BEFORE_BLOCKED} attempt limit)")
        print(f"  AGENT MUST STOP. Output: \"BLOCKED: {gate} - failed after {count} attempts. Needs HIL review.\"")
        print(f"{'!'*70}\n")
        return 1

    _save_session(session)
    print(f"[session_state] {item_id}: gate FAIL — {gate} (attempt {count}/{MAX_FAILURES_BEFORE_BLOCKED})")
    if count == MAX_FAILURES_BEFORE_BLOCKED:
        print(f"  ⚠  Next failure will BLOCK this gate. Fix carefully before retrying.")
    return 0


def cmd_reset_gate(session: dict, gate: str) -> int:
    item_id = session.get("item_id", "<item>")
    failures = session.get("gate_failures", {})
    if gate in failures:
        failures.pop(gate, None)
        session["gate_failures"] = failures
    blocked = session.get("gates_blocked", [])
    if gate in blocked:
        blocked.remove(gate)
    session["gates_blocked"] = blocked
    _save_session(session)
    print(f"[session_state] {item_id}: gate {gate!r} reset (failure counter cleared)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PF session state machine (P2a)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("next", help="Print the next required step")
    sub.add_parser("status", help="Print full session state")

    adv = sub.add_parser("advance", help="Advance to a named gate state")
    adv.add_argument("--to", required=True, choices=STATES, help="State to advance to")

    gp = sub.add_parser("record-gate-pass", help="Record a gate passing")
    gp.add_argument("--gate", required=True, help="Gate name, e.g. precheck-language-rule")

    gf = sub.add_parser("record-gate-fail", help="Record a gate failure")
    gf.add_argument("--gate", required=True, help="Gate name, e.g. precheck-language-rule")

    rg = sub.add_parser("reset-gate", help="Reset a gate's failure counter")
    rg.add_argument("--gate", required=True, help="Gate name to reset")

    rc = sub.add_parser("record-review-cycle",
                        help="Increment delta review cycle counter (Fix R3: cap at 2)")
    rc.add_argument("--gate", required=True, choices=["1.5", "2.5"],
                    help="Gate whose cycle counter to increment")

    a = ap.parse_args(argv)

    session = _load_session()
    if session is None:
        print("[session_state] No .pf-session.json found. Run item_kickoff.py first.")
        return 2

    if a.cmd == "next":
        return cmd_next(session)
    elif a.cmd == "status":
        return cmd_status(session)
    elif a.cmd == "advance":
        return cmd_advance(session, a.to)
    elif a.cmd == "record-gate-pass":
        return cmd_record_gate_pass(session, a.gate)
    elif a.cmd == "record-gate-fail":
        return cmd_record_gate_fail(session, a.gate)
    elif a.cmd == "reset-gate":
        return cmd_reset_gate(session, a.gate)
    elif a.cmd == "record-review-cycle":
        return cmd_record_review_cycle(session, a.gate)
    else:
        ap.print_help()
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
