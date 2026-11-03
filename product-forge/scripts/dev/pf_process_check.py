"""Validate the generic design/delivery framework itself (no item-specific logic)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "docs/PF-DESIGN-DELIVERY-CONTRACT.md",
    "docs/WORK-EXECUTION-CONTRACT.md",
    "config/design-contract.json",
    "config/glossary.json",
    "config/ownership.json",
    "config/coding-guidelines.json",
    "config/design-completeness.json",
    "config/biis-tiers.json",
    "config/control-matrix.json",
    "config/review-attribution.json",
    "scripts/dev/design_contract_check.py",
    "scripts/dev/ownership_check.py",
    "scripts/dev/review_ledger.py",
    "scripts/dev/guideline_compliance_check.py",
    "scripts/dev/control_runner.py",
    "scripts/dev/control_gate.py",
    "scripts/dev/review_attribution_check.py",
    "scripts/dev/design_completeness_check.py",
    "scripts/dev/biis_tier_check.py",
    "scripts/dev/biis_completeness_check.py",
    "scripts/dev/fix_evidence_check.py",
    "scripts/dev/self_review_check.py",
    "scripts/dev/framework_ref_check.py",
    "scripts/dev/rcca_link_check.py",
]
JSON = ["config/design-contract.json", "config/glossary.json", "config/ownership.json", "config/coding-guidelines.json", "config/design-completeness.json", "config/biis-tiers.json"]


def problems() -> list[str]:
    bad = []
    for rel in FILES:
        if not (ROOT / rel).is_file():
            bad.append(f"missing: {rel}")
    wf = ROOT.parent / ".github" / "workflows" / ("pf-gates" + ".yml")
    if not wf.is_file():
        bad.append("missing generic CI workflow: .github/workflows/pf-gates.yml")
    for rel in JSON:
        try:
            json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))
        except Exception as e:
            bad.append(f"invalid JSON {rel}: {e}")
    for rel in ("scripts/dev/design_contract_check.py", "scripts/dev/ownership_check.py", "scripts/dev/review_ledger.py"):
        p = ROOT / rel
        if not p.is_file():
            continue
        spec = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            bad.append(f"cannot import {rel}: {e}")
    return bad


def main() -> int:
    bad = problems()
    if bad:
        print("pf-process: FAIL")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("pf-process: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
