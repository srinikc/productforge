"""A5 (BI-PF-0399): Tests for Runtime Dependency Compiler (RDC).

Verifies:
- AC-1: Multi-target OS/arch resolution (linux/amd64, linux/arm64, windows/amd64, darwin/arm64) and deterministic composition.
- AC-2: Fail-closed IP-leakage guard refusing compositions with raw .py sources in customer editions.
- AC-3: Native Go engine wire seam invocation (rdc.compose, rdc.validate_ip, rdc.plan).
- AC-4: sample-runtime-package fixture verification and contract compliance.
- AC-5: REST API surface and complete pipeline verification.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import packaging, rdc  # noqa: E402


@pytest.fixture
def sample_eap():
    fx = ROOT / "test-framework" / "tests" / "fixtures" / "contracts" / "sample-product" / "sample.eap"
    if fx.exists():
        with open(fx, encoding="utf-8") as f:
            return json.load(f)
    return packaging.eap_build("product_forge", "", "enterprise")


def test_rdc_multi_target_composition(sample_eap):
    """AC-1: Multi-target OS/arch resolution produces deterministic composition."""
    targets = [
        ("linux", "amd64", "pf-core", "core_runtime.so"),
        ("linux", "arm64", "pf-core", "core_runtime.so"),
        ("windows", "amd64", "pf-core.exe", "core_runtime.pyd"),
        ("darwin", "arm64", "pf-core", "core_runtime.dylib"),
    ]
    for target_os, target_arch, expected_bin, expected_lib in targets:
        res = rdc.compose(sample_eap, target_os=target_os, target_arch=target_arch,
                          edition="enterprise", dry_run=True)
        assert res["ok"] is True, f"Failed for {target_os}/{target_arch}: {res.get('error')}"
        assert res["target_platform"] == f"{target_os}/{target_arch}"
        assert expected_bin in res["native_binaries"]
        assert expected_lib in res["shared_libraries"]
        assert res["ip_guard_verified"] is True
        assert res["schema"] == "product-forge/runtime-composition@1"


def test_rdc_unsupported_target_fails():
    """AC-1: Unsupported OS/arch targets fail closed."""
    res = rdc.compose(target_os="plan9", target_arch="mips")
    assert res["ok"] is False
    assert "ERR_RDC_UNSUPPORTED_TARGET" in res.get("error", "")


def test_rdc_ip_leakage_guard_refusal():
    """AC-2: Customer editions containing raw .py files are fail-closed rejected."""
    customer_editions = ["enterprise", "on-prem", "saas", "oem"]
    for ed in customer_editions:
        check = rdc.validate_ip(edition=ed, files=["bin/pf-core", "core/secret_logic.py"])
        assert check["ok"] is False, f"Expected rejection for {ed}"
        assert check["valid"] is False
        assert "IP_LEAKAGE_DETECTED" in check.get("error", "")
        assert any("secret_logic.py" in u for u in check.get("unmet", []))

    # Community edition allows raw .py
    comm_check = rdc.validate_ip(edition="community", files=["core/secret_logic.py"])
    assert comm_check["ok"] is True
    assert comm_check["valid"] is True


def test_rdc_native_go_wire_seam():
    """AC-3: Go core exposes rdc.compose, rdc.validate_ip, rdc.plan over A1 wire seam."""
    from core import go_host
    ping_resp = go_host.invoke("ping")
    assert ping_resp["ok"] is True
    caps = (ping_resp.get("result") or {}).get("capabilities", [])
    assert "rdc.compose" in caps
    assert "rdc.validate_ip" in caps
    assert "rdc.plan" in caps

    # Plan invocation
    plan_res = rdc.plan(target_os="linux", target_arch="amd64", edition="enterprise")
    assert plan_res["ok"] is True
    assert plan_res["total_files"] > 0
    assert "bin/pf-core" in plan_res["paths"]


def test_sample_runtime_package_fixture(sample_eap, tmp_path):
    """AC-4: sample-runtime-package fixture validates against contracts."""
    comp = rdc.compose(sample_eap, target_os="linux", target_arch="amd64", edition="enterprise", dry_run=True)
    assert comp["ok"] is True

    pkg_dir = str(tmp_path / "sample-runtime-package")
    res = rdc.write_runtime_package(comp, pkg_dir)
    assert res["ok"] is True
    assert os.path.exists(res["manifest_path"])

    with open(res["manifest_path"], encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["schema"] == "product-forge/runtime-composition@1"
    assert manifest["edition"] == "enterprise"
    assert manifest["ip_guard_verified"] is True
    assert len(manifest["components"]) > 0


def test_rdc_api_endpoints(monkeypatch):
    """AC-5: Packaging router exposes /api/v1/packaging/rdc/compose and /validate."""
    token = "test-rdc-api-token-secret"
    monkeypatch.setenv("PF_API_TOKEN", token)
    client = TestClient(app)
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "X-Roles": "operator"
    }

    # Test compose endpoint
    compose_body = {
        "target_os": "linux",
        "target_arch": "amd64",
        "edition": "enterprise",
        "dry_run": True,
    }
    r = client.post("/api/v1/packaging/rdc/compose", json=compose_body, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json().get("data", {})
    assert data.get("ok") is True
    assert data.get("target_platform") == "linux/amd64"

    # Test IP validate endpoint with clean files
    val_clean = {
        "edition": "enterprise",
        "files": ["bin/pf-core", "lib/core_runtime.so"],
    }
    r = client.post("/api/v1/packaging/rdc/validate", json=val_clean, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json().get("data", {}).get("valid") is True

    # Test IP validate endpoint with raw .py in enterprise (must fail 400)
    val_bad = {
        "edition": "enterprise",
        "files": ["bin/pf-core", "core/logic.py"],
    }
    r = client.post("/api/v1/packaging/rdc/validate", json=val_bad, headers=auth_headers)
    assert r.status_code == 400, r.text
    assert "IP_LEAKAGE_DETECTED" in r.text
