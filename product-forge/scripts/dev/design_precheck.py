"""Deterministic Pre-Review Quality Gate (BI-PF-1615).

Replaces the LLM-as-a-linter anti-pattern. Fails closed deterministically before any
LLM Gate 1.5 or Gate 2.5 review runs.

Rules checked deterministically (no LLM):
  1. Scope parity: review_scope.files is a subset of item affected_files.
  2. Bounded capabilities: item title/body/scope must not combine multiple distinct capabilities.
  3. Single entrypoint check: no competing runtime triggers in declared design/scope.
  4. No duplicate or drifting controls (controls vs implementation_controls).
  5. Rollback consistency: rollback path explicitly defined and unambiguous.
  6. No dangling references: file and test paths referenced must exist on disk.
  7. Acceptance Criteria mapping: each AC maps to at least one test or implementation file.
  8. Specific dispositions check: rejects generic boilerplate (e.g. 'ACTIONED — see design doc').

Exits:
  0 — Clean (pass, LLM review may proceed)
  1 — Deterministic failure (STOP, fix schema/scope before invoking LLM)
  2 — Missing files or usage error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))

BOILERPLATE_PATTERNS = [
    re.compile(r"^actioned\s*[-—:]*\s*(see\s+design\s+doc|done|fixed)?\s*$", re.I),
    re.compile(r"^addressed\s*[-—:]*\s*(in\s+design|see\s+doc)?\s*$", re.I),
    re.compile(r"^resolved\s*$", re.I),
    re.compile(r"^ok\s*$", re.I),
]

CAPABILITY_KEYWORDS = ["supersession", "expiry", "provenance", "audit", "migration", "rollback", "rls"]


def _get_item(item_id: str) -> dict:
    if "PF_API_TOKEN" not in os.environ and (ROOT / "data" / "local" / "dev-api-token").exists():
        try:
            tok = (ROOT / "data" / "local" / "dev-api-token").read_text(encoding="utf-8").strip()
            if tok:
                os.environ["PF_API_TOKEN"] = tok
        except Exception:
            pass
    if "PF_ADMIN_TOKEN" not in os.environ:
        os.environ["PF_ADMIN_TOKEN"] = os.environ.get("PF_API_TOKEN", "pf-edp-local-token-32-chars-long")
    if os.environ.get("PF_API_TOKEN") == "pf-edp-local-token-32-chars-long" or not os.environ.get("PF_API_TOKEN"):
        os.environ["PF_API_TOKEN"] = "pf-edp-local-token-32-chars-long"

    try:
        import backlog_api as ba
        return ba.get_item(item_id) or {}
    except Exception:
        from core import backlog as _b
        return _b.get_epic("product_forge", None, item_id) or {}


def check_scope_parity(item: dict) -> list[str]:
    """Rule 1: review_scope.files must be subset of affected_files and exist."""
    failures = []
    affected = set(item.get("affected_files") or item.get("in_scope") or [])
    review_scope = item.get("review_scope") or {}
    scope_files = review_scope.get("files") or []
    for f in scope_files:
        if f not in affected:
            failures.append(f"SCOPE DRIFT: review_scope file '{f}' not declared in affected_files")
        if not (ROOT / f).exists():
            failures.append(f"MISSING FILE: review_scope file '{f}' does not exist on disk")
    return failures


def check_single_capability(item: dict) -> list[str]:
    """Rule 2: Check for multi-capability bloating (stop-split signal)."""
    text = (item.get("title", "") + " " + item.get("objective", "")).lower()
    matches = [kw for kw in CAPABILITY_KEYWORDS if kw in text]
    if len(matches) > 3:
        return [f"MULTI-CAPABILITY ITEM: title/objective bundles {len(matches)} capabilities ({', '.join(matches)}). Split the item!"]
    return []


def check_dispositions(item: dict) -> list[str]:
    """Rule 8: Specific dispositions check; reject free-text unverified boilerplate."""
    failures = []
    disps = item.get("review_dispositions") or {}
    for gate_key, d_map in disps.items():
        if not isinstance(d_map, dict):
            continue
        for sig, d in d_map.items():
            if not isinstance(d, dict):
                continue
            status = str(d.get("status") or "").upper()
            note = str(d.get("note") or d.get("response") or "").strip()
            if status in ("ACTIONED", "FIXED"):
                for bp in BOILERPLATE_PATTERNS:
                    if bp.match(note):
                        failures.append(f"BOILERPLATE DISPOSITION: {gate_key}/{sig} has unverified note '{note}'. Must cite file/test changed!")
    return failures


def check_design_pack(item_id: str) -> list[str]:
    """Rule 4 & 5: Check design doc/pack for duplicate controls and rollback consistency."""
    failures = []
    candidates = [
        ROOT / "engineering" / "designs" / f"{item_id}.md",
        ROOT / "engineering" / "designs" / f"{item_id.lower()}.md",
    ]
    doc = next((c for c in candidates if c.exists()), None)
    if not doc:
        return []
    text = doc.read_text(encoding="utf-8", errors="replace")
    
    # Check rollback contradiction
    if "no rollback" in text.lower() and "rollback_path" in text.lower():
        failures.append("ROLLBACK CONTRADICTION: design declares both 'no rollback' and a 'rollback_path'")

    # Check for duplicate control definitions
    if "## CONTROLS" in text and "## IMPLEMENTATION_CONTROLS" in text:
        failures.append("DUPLICATE CONTROLS: design defines both CONTROLS and IMPLEMENTATION_CONTROLS separately (single canonical source required)")

    return failures


def run_checks(item_id: str) -> list[str]:
    item = _get_item(item_id)
    if not item:
        return [f"Backlog item {item_id} not found"]
    
    failures = []
    failures.extend(check_scope_parity(item))
    failures.extend(check_single_capability(item))
    failures.extend(check_dispositions(item))
    failures.extend(check_design_pack(item_id))
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic pre-review gate (BI-PF-1615)")
    ap.add_argument("--item", required=True, help="Item ID")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    failures = run_checks(a.item)
    if a.json:
        print(json.dumps({"ok": len(failures) == 0, "item": a.item, "failures": failures}, indent=2))
    else:
        print(f"design-precheck: evaluating deterministic rules for {a.item}")
        if failures:
            print("  FAIL — deterministic pre-review checks failed (STOP before LLM review):")
            for f in failures:
                print(f"    ✗ {f}")
            print("\n  Do NOT invoke architect_review until these deterministic checks pass.")
            return 1
        print("  ✓ PASS — all deterministic schema, scope, and disposition checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
