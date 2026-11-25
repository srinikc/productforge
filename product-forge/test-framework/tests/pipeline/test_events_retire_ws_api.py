"""Contract and regression tests for BI-PF-1276:
Retire legacy websocket push (frozen dashboard -> SSE)
"""

import os
import ast
import json
import hashlib
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_ac1_websocket_manager_deprecation_notice():
    """AC-1: core/websocket_manager.py has clear deprecation header and migration mapping to SSE."""
    ws_file = ROOT / "core" / "websocket_manager.py"
    assert ws_file.exists(), f"{ws_file} must exist (never deleted)"
    content = ws_file.read_text(encoding="utf-8")
    assert "DEPRECATED" in content, "core/websocket_manager.py must be marked DEPRECATED"
    assert "/api/v1/events/stream" in content, "core/websocket_manager.py must document migration to SSE stream"
    assert "BI-PF-1276" in content, "core/websocket_manager.py must reference BI-PF-1276"


def test_ac2_legacy_frozen_registration_and_hash():
    """AC-2: Freeze core/websocket_manager.py in config/legacy-frozen.json with matching sha256."""
    cfg_file = ROOT / "config" / "legacy-frozen.json"
    assert cfg_file.exists(), "config/legacy-frozen.json must exist"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    files = cfg.get("files", {})
    assert "core/websocket_manager.py" in files, "core/websocket_manager.py must be registered in legacy-frozen.json"

    meta = files["core/websocket_manager.py"]
    assert "sha256" in meta, "legacy-frozen entry must specify sha256"
    assert "SSE" in meta.get("reason", ""), "legacy-frozen reason must reference SSE"

    raw = (ROOT / "core" / "websocket_manager.py").read_bytes()
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    actual_sha = hashlib.sha256(normalized).hexdigest()
    assert actual_sha == meta["sha256"], f"SHA mismatch: expected {meta['sha256']}, got {actual_sha}"


def test_ac3_zero_new_websocket_consumers():
    """AC-3: Verify zero new WebSocket consumers or imports across core, api, and scripts."""
    scanned_roots = ["core", "api", "scripts"]
    violations = []

    for r in scanned_roots:
        dir_path = ROOT / r
        for f in dir_path.rglob("*.py"):
            if f.name == "websocket_manager.py":
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "websocket_manager" in alias.name:
                            violations.append(f"{f.relative_to(ROOT)} imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if "websocket_manager" in mod:
                        violations.append(f"{f.relative_to(ROOT)} imports from {mod}")
                    for alias in node.names:
                        if alias.name in ("WebSocketManager", "websocket_endpoint"):
                            violations.append(f"{f.relative_to(ROOT)} imports {alias.name}")

    assert not violations, f"Forbidden legacy WebSocket references found in runtime paths: {violations}"


def test_ac4_sse_stream_alternative_active(monkeypatch):
    """AC-4: Verify SSE event stream and bus status are active alternatives."""
    monkeypatch.setenv("PF_API_TOKEN", "test-token")
    from fastapi.testclient import TestClient
    from api.app import app

    client = TestClient(app)
    # Verify bus status endpoint is live and returning operational envelope
    res_bus = client.get("/api/v1/events/bus", headers={"authorization": "Bearer test-token"})
    assert res_bus.status_code == 200, f"Expected 200 from /events/bus, got {res_bus.status_code}"
    data = res_bus.json().get("data", res_bus.json())
    assert "running" in data, "Bus status envelope must contain 'running' field"

    # Verify SSE stream route is active on FastAPI router
    paths = app.openapi().get("paths", {})
    assert "/api/v1/events/stream" in paths, "/api/v1/events/stream must be registered on application router"


def test_ac5_wired_audit_legacy_guard_pass():
    """AC-5: Ensure legacy_guard from wired_audit passes cleanly with frozen files intact."""
    import sys
    scripts_dev = str(ROOT / "scripts" / "dev")
    added = False
    if scripts_dev not in sys.path:
        sys.path.insert(0, scripts_dev)
        added = True
    try:
        import wired_audit
        res = wired_audit.legacy_guard_audit()
        assert res == 0, "wired_audit.legacy_guard_audit must pass with return code 0"
    finally:
        if added and scripts_dev in sys.path:
            sys.path.remove(scripts_dev)
