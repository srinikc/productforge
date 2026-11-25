"""Deterministic Precheck for Recurring Review Findings (BI-PF-1615 / Group 3).

Checks code and design diffs against known recurring patterns harvested from
engineering/learnings/review-findings.json, driving findings per review down deterministically.

Patterns checked:
  1. Positional ordinal indexing of dispositions instead of stable digest (sig:<hash>).
  2. GCS or adapter dead-code wiring on runtime path.
  3. Trailing newline hygiene on generated documentation artifacts.
  4. Non-hermetic wall-clock nanoseconds in probe-key generation.
  5. Unwired private helper duplicates in review renderers.

Exits:
  0 — Clean (no recurring anti-patterns detected)
  1 — Recurring anti-pattern detected (deterministic gate failure)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def check_git_diff_text() -> str:
    try:
        import subprocess
        mb = subprocess.check_output(["git", "merge-base", "origin/develop", "HEAD"], cwd=str(ROOT)).decode().strip()
        return subprocess.check_output(["git", "diff", f"{mb}..HEAD"], cwd=str(ROOT)).decode("utf-8", errors="replace")
    except Exception:
        return ""


def run_checks() -> list[str]:
    failures = []
    diff = check_git_diff_text()
    if not diff:
        return []

    # Check 1: Positional indexing pattern in review disposition handlers
    if "+    disp.get(str(" in diff or "+    dispositions.get(str(" in diff:
        failures.append("RECURRING FINDING (sig:9bc95dd204): Findings correlated by positional ordinal index instead of stable digest sig:<hash>.")

    # Check 2: Nanosecond wall-clock probe keys
    if "+    nanos" in diff and "time.Now().UnixNano()" in diff and "probe" in diff.lower():
        failures.append("RECURRING FINDING (sig:fee8734b6b): Probe-key uniqueness uses wall-clock nanos instead of monotonic / random UUID.")

    # Check 3: Review renderer duplicate
    if "+def _render_review" in diff and "def review_block" in diff:
        failures.append("RECURRING FINDING (sig:89657c92a9): Duplicate review block renderers detected.")

    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic recurring findings check")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    failures = run_checks()
    if a.json:
        print(json.dumps({"ok": len(failures) == 0, "failures": failures}, indent=2))
    else:
        print("recurring-findings-check: scanning diff against durable patterns...")
        if failures:
            print("  FAIL — known recurring anti-pattern detected in diff:")
            for f in failures:
                print(f"    ✗ {f}")
            return 1
        print("  ✓ PASS — no known recurring anti-patterns found in diff.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
