"""A5 (BI-PF-0399): Runtime Dependency Compiler (RDC) — Python Seam Client.

Authoritative runtime composition engine and fail-closed IP-leakage guard.
Per the language rule, core composition logic and IP-leakage guard run natively in
Go (go/pfcore/rdc.go), invoked through the canonical A1 wire seam (core.go_host).
"""
from __future__ import annotations

import json
import os
from typing import Any


def compose(eap: dict[str, Any] | None = None,
            target_os: str = "linux",
            target_arch: str = "amd64",
            edition: str = "community",
            license_tier: str = "",
            dry_run: bool = False) -> dict[str, Any]:
    """Compose deterministic runtime package plan via native Go RDC engine."""
    from core import go_host
    payload = {
        "eap": eap or {},
        "target_os": target_os,
        "target_arch": target_arch,
        "edition": edition,
        "license_tier": license_tier,
        "dry_run": dry_run,
    }
    resp = go_host.invoke("rdc.compose", "runtime-profile", payload, source="python")
    if not resp.get("ok"):
        return {"ok": False, "error": resp.get("error", "rdc.compose failed")}
    res = resp.get("result") or {}
    return {"ok": True, **res}


def validate_ip(edition: str = "community", files: list[str] | None = None) -> dict[str, Any]:
    """Inspect file list for raw .py sources in customer editions (fail-closed IP guard)."""
    from core import go_host
    payload = {
        "edition": edition,
        "files": files or [],
    }
    resp = go_host.invoke("rdc.validate_ip", "runtime-profile", payload, source="python")
    if not resp.get("ok"):
        return {"ok": False, "valid": False, "error": resp.get("error", "rdc.validate_ip failed"),
                "unmet": (resp.get("result") or {}).get("unmet", ["ip_leakage:rejected"])}
    res = resp.get("result") or {}
    return {"ok": True, "valid": res.get("valid", False), **res}


def plan(eap: dict[str, Any] | None = None,
         target_os: str = "linux",
         target_arch: str = "amd64",
         edition: str = "community") -> dict[str, Any]:
    """Output the planned directory layout and file list for package assembly."""
    from core import go_host
    payload = {
        "eap": eap or {},
        "target_os": target_os,
        "target_arch": target_arch,
        "edition": edition,
    }
    resp = go_host.invoke("rdc.plan", "runtime-profile", payload, source="python")
    if not resp.get("ok"):
        return {"ok": False, "error": resp.get("error", "rdc.plan failed")}
    res = resp.get("result") or {}
    return {"ok": True, **res}


def write_runtime_package(composition: dict[str, Any], output_dir: str) -> dict[str, Any]:
    """Assemble a runtime package directory containing runtime-composition.json and binaries."""
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, "runtime-composition.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(composition, f, indent=2, sort_keys=True)
        f.write("\n")

    # If dry-run, materialize mock binary and library artifacts
    if composition.get("dry_run"):
        for b in composition.get("native_binaries", []):
            bpath = os.path.join(output_dir, b)
            with open(bpath, "wb") as f:
                f.write(b"\x7fELF_COMPILED_MOCK_BIN")
        for lib in composition.get("shared_libraries", []):
            lpath = os.path.join(output_dir, lib)
            with open(lpath, "wb") as f:
                f.write(b"\x7fELF_COMPILED_MOCK_LIB")

    return {
        "ok": True,
        "output_dir": output_dir,
        "manifest_path": manifest_path,
        "artifacts": composition.get("native_binaries", []) + composition.get("shared_libraries", [])
    }
