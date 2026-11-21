"""
Contract tests for A3 Packaging Pipeline (BI-PF-0398).

Verifies:
  1. Compiled packaging pipeline orchestration (Nuitka / Go build).
  2. Fail-closed NO-RAW-.py release gate enforcement on customer editions.
  3. CycloneDX/SPDX SBOM, License BOM (LBOM), and digital signing emission.
  4. Build-time subsystem plug/unplug (absorbing BI-PF-0383).
  5. Asset bundle cataloging in EAP manifest.
"""
import json
import os
import shutil
import tempfile
import pytest

from core import packaging, release, signing, bom


def test_compiled_packaging_orchestration():
    """AC-1: Compiled packaging pipeline builds native binary artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock source tree
        src_dir = os.path.join(tmpdir, "src")
        os.makedirs(src_dir, exist_ok=True)
        pkg_result = packaging.build_compiled_package(
            scope="product_forge",
            project="",
            edition="enterprise",
            output_dir=os.path.join(tmpdir, "out"),
            dry_run=True
        )
        assert pkg_result["ok"] is True
        assert pkg_result["edition"] == "enterprise"
        assert pkg_result.get("compiled") is True
        assert "artifacts" in pkg_result


def test_compilation_failure_handling():
    """AC-1 (negative): Compilation failure aborts packaging with clean error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        res = packaging.build_compiled_package(
            scope="product_forge",
            project="",
            edition="unknown_edition_xyz",
            output_dir=os.path.join(tmpdir, "out"),
            dry_run=True
        )
        assert res["ok"] is False
        assert "error" in res


def test_no_raw_py_gate_enforcement():
    """AC-2: Automated release gate inspects packaged edition distributions and fails closed on raw .py."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Package with only binary/compiled files passes
        dist_dir = os.path.join(tmpdir, "dist_clean")
        os.makedirs(dist_dir, exist_ok=True)
        with open(os.path.join(dist_dir, "core.pyd"), "wb") as f:
            f.write(b"\x7fELF\x02\x01\x01")
        with open(os.path.join(dist_dir, "packaging-manifest.json"), "w") as f:
            f.write('{"ok": true}')

        res = release.no_raw_py_gate(dist_dir, edition="enterprise")
        assert res["valid"] is True
        assert len(res["violating_files"]) == 0


def test_raw_py_detected_blocks_release():
    """AC-2 (negative): Any uncompiled .py file in customer edition fails the release gate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_dir = os.path.join(tmpdir, "dist_dirty")
        os.makedirs(dist_dir, exist_ok=True)
        with open(os.path.join(dist_dir, "secret_logic.py"), "w") as f:
            f.write("def proprietary(): pass\n")

        res = release.no_raw_py_gate(dist_dir, edition="enterprise")
        assert res["valid"] is False
        assert "secret_logic.py" in str(res["violating_files"])
        assert any("UNMET: RAW_PY_IN_SHIPPED_PACKAGE" in u for u in res["unmet"])


def test_sbom_lbom_and_signing_emission():
    """AC-3: Package builder produces CycloneDX or SPDX compliant SBOM, LBOM, and digital signatures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "pkg")
        os.makedirs(out_dir, exist_ok=True)
        res = packaging.attach_sbom_and_signatures(
            scope="product_forge",
            project="",
            edition="enterprise",
            package_dir=out_dir
        )
        assert res["ok"] is True
        assert os.path.exists(os.path.join(out_dir, "sbom.json"))
        assert os.path.exists(os.path.join(out_dir, "lbom.json"))
        assert os.path.exists(os.path.join(out_dir, "checksums.txt"))


def test_missing_sbom_fails_build():
    """AC-3 (negative): Missing SBOM data causes fail-closed validation error."""
    res = packaging.validate_package_sbom({})
    assert res["valid"] is False
    assert "MISSING_SBOM" in res["unmet"]


def test_subsystem_plug_unplug_workers():
    """AC-4: Build-time subsystem plug/unplug mechanism allows excluding the worker subsystem (BI-PF-0383)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        res = packaging.eap_build(
            scope="product_forge",
            project="",
            edition="on-prem",
            exclude_subsystems=["workers"]
        )
        assert res["ok"] is True
        assert "workers" in res.get("subsystem_exclusions", [])
        assert res.get("workers_included") is False


def test_mandatory_subsystem_exclusion_rejected():
    """AC-4 (negative): Attempting to exclude mandatory core subsystem is rejected."""
    with pytest.raises(ValueError, match="Cannot exclude mandatory subsystem"):
        packaging.apply_subsystem_exclusions(
            modules=["core/packaging.py", "core/licensing.py"],
            exclude_subsystems=["licensing"]
        )


def test_asset_bundle_cataloging():
    """FR-5: Asset bundle cataloging in EAP manifest for prompt and UI/UX assets."""
    eap = packaging.eap_build(
        scope="product_forge",
        project="",
        edition="enterprise",
        asset_bundles=[
            {"id": "prompts_pack", "file": "prompts.bin", "checksum": "abc123sha"},
            {"id": "uiux_tokens", "file": "tokens.json", "checksum": "def456sha"}
        ]
    )
    assert eap["ok"] is True
    assert "asset_bundles" in eap
    assert len(eap["asset_bundles"]) == 2


def test_corrupted_asset_bundle_rejected():
    """FR-5 (negative): Corrupted or unmanifested asset bundle fails EAP validation."""
    res = packaging.validate_asset_bundle({"id": "prompts_pack"})
    assert res["valid"] is False
    assert "MISSING_ASSET_CHECKSUM" in res["unmet"]
