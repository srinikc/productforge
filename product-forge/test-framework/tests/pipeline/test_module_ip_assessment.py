"""BI-PF-0386: Module IP-value assessment and inventory contract tests.

Verifies:
1. Module IP assessment documentation completeness and structural integrity.
2. Machine-readable inventory config schema and completeness across core/, api/, and adapters/.
3. 100% classification coverage of all platform shipped modules.
4. Harmonization of sensitive_roots in config/language-rule.json with Tier 1 sensitive modules.
5. Traceability to ADR-0001 and docs/PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import change_policy as cp  # noqa: E402

ASSESSMENT_DOC = ROOT / "docs" / "PF-MODULE-IP-ASSESSMENT.md"
INVENTORY_FILE = ROOT / "config" / "module-ip-inventory.json"
LANGUAGE_RULE_FILE = ROOT / "config" / "language-rule.json"
TARGET_ARCH_DOC = ROOT / "docs" / "PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md"


def test_assessment_doc_present_and_complete():
    """AC-1: Assessment document exists and contains all required sections."""
    assert ASSESSMENT_DOC.exists(), f"Missing required doc: {ASSESSMENT_DOC}"
    content = ASSESSMENT_DOC.read_text(encoding="utf-8")
    required_sections = [
        "Executive Summary & Context",
        "Four-Tier Classification Model",
        "Tier 1: High IP / Sensitive Modules",
        "Tier 2: Medium IP / Core Capabilities",
        "Tier 3: Low IP / Plumbing & Utilities",
        "Tier 4: Tooling & Build-Time Only",
        "Configuration & Policy Integration",
        "Definition of Done & Traceability"
    ]
    for sec in required_sections:
        assert sec in content, f"Missing section '{sec}' in {ASSESSMENT_DOC}"
    assert "BI-PF-0386" in content, "Doc must reference BI-PF-0386"
    assert "ADR-0001" in content, "Doc must reference ADR-0001"


def test_inventory_schema_and_integrity():
    """AC-2: Machine-readable inventory exists with valid schema and non-empty categories."""
    assert INVENTORY_FILE.exists(), f"Missing inventory file: {INVENTORY_FILE}"
    with open(INVENTORY_FILE, encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("$schema") == "pf-module-ip-inventory-v1"
    assert "summary" in data
    assert data["summary"]["total_modules"] > 0
    assert data["summary"]["tier_1_count"] > 0
    assert data["summary"]["tier_2_count"] > 0
    assert "tier_definitions" in data
    assert "modules" in data
    for mod_path, details in data["modules"].items():
        assert details.get("tier") in (1, 2, 3, 4), f"Invalid tier for {mod_path}"
        assert details.get("target") in ("Go", "Rust", "compiled-Python", "Python"), f"Invalid target for {mod_path}"
        assert details.get("sensitivity") in ("critical", "high", "medium", "low", "none"), f"Invalid sensitivity for {mod_path}"
        assert details.get("rationale"), f"Missing rationale for {mod_path}"


def test_all_shipped_modules_classified():
    """AC-1 / AC-4: 100% of python modules under core/, api/, and adapters/ are classified."""
    with open(INVENTORY_FILE, encoding="utf-8") as f:
        data = json.load(f)
    inventory = data.get("modules", {})

    core_files = sorted([f.relative_to(ROOT).as_posix() for f in (ROOT / "core").glob("**/*.py")])
    api_files = sorted([f.relative_to(ROOT).as_posix() for f in (ROOT / "api").glob("**/*.py")])
    adapter_files = sorted([f.relative_to(ROOT).as_posix() for f in (ROOT / "adapters").glob("**/*.py")])
    all_shipped = set(core_files + api_files + adapter_files)

    unclassified = [m for m in all_shipped if m not in inventory]
    assert not unclassified, f"Found unclassified modules in inventory: {unclassified[:10]}"


def test_sensitive_roots_contain_tier1_modules():
    """AC-3: language-rule sensitive_roots contains core Tier 1 commercial/security roots."""
    pol = cp.policy(force_reload=True)
    sensitive_roots = [cp.normalize(r) for r in pol.get("sensitive_roots", [])]
    expected_tier1_roots = [
        "core/licensing.py",
        "core/billing.py",
        "core/credentials.py",
        "core/packaging.py",
        "core/release.py",
        "api/auth.py"
    ]
    for r in expected_tier1_roots:
        assert r in sensitive_roots, f"Tier 1 module '{r}' must be in sensitive_roots"


def test_target_architecture_traceability():
    """AC-4: Inventory aligns with target architecture IP plan (§4.5)."""
    assert TARGET_ARCH_DOC.exists(), f"Missing target architecture doc: {TARGET_ARCH_DOC}"
    with open(INVENTORY_FILE, encoding="utf-8") as f:
        data = json.load(f)
    inventory = data.get("modules", {})

    high_value_must_be_tier1 = [
        "core/pipeline_executor.py",
        "core/product_analyzer.py",
        "core/product_plan.py",
        "core/service_catalog.py",
        "core/global_orchestrator.py",
        "core/intent_router.py",
        "core/tech_stack.py",
        "core/model_gate.py",
        "core/pidl.py",
        "core/agent_memory.py"
    ]
    for mod in high_value_must_be_tier1:
        assert mod in inventory, f"Module {mod} missing from inventory"
        assert inventory[mod]["tier"] == 1, f"Module {mod} must be classified as Tier 1"
        assert inventory[mod]["target"] in ("Go", "Rust"), f"Module {mod} target must be Go/Rust"
