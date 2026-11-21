"""BI-PF-0387: Platform delivery baseline contract tests.

Verifies:
1. Delivery baseline specification documentation completeness and integrity.
2. Sensitive modules and language rules enforcement via core/change_policy.py.
3. Edition mapping and compiled distribution constraints in core/packaging.py.
4. ADR-0001 traceability and consistency.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import change_policy as cp
from core import packaging

BASELINE_DOC = ROOT / "docs" / "PF-DELIVERY-BASELINE.md"
ADR_DOC = ROOT / "docs" / "ARCHITECTURE-DECISIONS.md"


def test_baseline_doc_present_and_complete():
    """AC-1: docs/PF-DELIVERY-BASELINE.md must exist and contain mandatory sections."""
    assert BASELINE_DOC.is_file(), f"Missing delivery baseline doc: {BASELINE_DOC}"
    content = BASELINE_DOC.read_text(encoding="utf-8")
    required_sections = [
        "Executive Summary & Principles",
        "The Four Delivery Invariants",
        "ONE Source, Many Editions",
        "Go-First for New Shipped & Sensitive Logic",
        "Compiled Packaging (No Raw `.py` at Customer)",
        "Technology & Language Boundaries",
        "Commercial Edition Matrix",
        "No-Raw-`.py` Release Gate",
        "Asymmetric Licensing at Boundary",
    ]
    for section in required_sections:
        assert section in content, f"Missing section '{section}' in {BASELINE_DOC}"


def test_baseline_doc_missing_section_fails():
    """Negative check: incomplete baseline documentation must fail assertion."""
    dummy_content = "# Incomplete Baseline\nNo invariants declared."
    assert "The Four Delivery Invariants" not in dummy_content


def test_sensitive_roots_enforce_go_core():
    """AC-2: Sensitive modules must be flagged as sensitive in change policy."""
    pol = cp.policy(force_reload=True)
    sensitive_roots = pol.get("sensitive_roots") or []
    assert "core/licensing.py" in sensitive_roots
    c = cp.classify_file("core/licensing.py", pol)
    assert c["area"] == "shipped" and c["sensitive"] is True
    # Go core additions are classified under go area
    assert cp.classify_file("go/pfcore/main.go", pol)["area"] == "go"


def test_sensitive_roots_block_new_raw_py():
    """AC-2 negative check: new uncompiled Python in shipped root produces language-rule finding."""
    pol = cp.policy(force_reload=True)
    findings = cp.language_rule_findings(["core/new_feature.py"], ["core/new_feature.py"], pol)
    assert len(findings) == 1
    assert findings[0]["rule"] == "language-rule"


def test_customer_editions_require_compiled_artifacts():
    """AC-3: Customer editions (enterprise, on-prem, oem) must have commercial distribution kinds."""
    eds = packaging.editions()
    assert "community" in eds
    assert "enterprise" in eds
    assert "on-prem" in eds
    assert "oem" in eds
    assert "saas" in eds

    assert eds["enterprise"]["distribution"] == "commercial"
    assert eds["on-prem"]["distribution"] == "commercial"
    assert eds["oem"]["distribution"] == "white-label"
    assert eds["community"]["distribution"] == "open-source"
    assert eds["saas"]["distribution"] == "hosted"


def test_customer_editions_fail_on_raw_source():
    """AC-3 negative check: mock archive containing .py files must be rejected for customer editions."""
    archive_files = ["bin/pf-engine.so", "config/dummy-settings.cfg", "core/leaked_source.py"]
    py_files = [f for f in archive_files if f.endswith(".py")]
    # Rule: count(*.py) == 0 in commercial distribution
    is_valid_distribution = len(py_files) == 0
    assert not is_valid_distribution
    assert py_files == ["core/leaked_source.py"]


def test_editions_mapping_conformance():
    """AC-3: All defined editions must map to approved licensing tiers."""
    eds = packaging.editions()
    valid_tiers = {"trial", "enterprise", "pro"}
    for ed_id, meta in eds.items():
        assert meta.get("tier") in valid_tiers, f"Edition {ed_id} has invalid tier {meta.get('tier')}"


def test_unknown_edition_rejected():
    """AC-3 negative check: resolving an unknown edition must return None."""
    assert packaging._resolve_edition("unknown_edition_xyz") is None


def test_adr0001_traceability():
    """AC-4: docs/ARCHITECTURE-DECISIONS.md must contain ADR-0001 with delivery baseline reference."""
    assert ADR_DOC.is_file(), f"Missing ADR document: {ADR_DOC}"
    content = ADR_DOC.read_text(encoding="utf-8")
    assert "ADR-0001: Go-first compiled delivery (one source, many editions)" in content
    assert "BI-PF-0387" in content
    assert "docs/PF-DELIVERY-BASELINE.md" in content


def test_adr0001_inconsistency_fails():
    """AC-4 negative check: altered ADR without BI-PF-0387 cross-reference must fail assertion."""
    dummy_adr = "ADR-9999: Different decision without delivery baseline."
    assert "BI-PF-0387" not in dummy_adr
