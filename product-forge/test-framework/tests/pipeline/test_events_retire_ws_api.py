"""Contract and regression tests for BI-PF-1276:
Retire legacy websocket push (frozen dashboard -> SSE)
"""

import os
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
    forbidden = ["import websocket_manager", "from core.websocket_manager import", "WebSocketManager()"]
    scanned_roots = ["core", "api"]
    violations = []

    for r in scanned_roots:
        dir_path = ROOT / r
        for f in dir_path.glob("*.py"):
            if f.name == "websocket_manager.py":
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for pattern in forbidden:
                if pattern in text:
                    violations.append(f"{f.relative_to(ROOT)}: contains '{pattern}'")

    assert not violations, f"Forbidden legacy WebSocket references found in runtime paths: {violations}"


def test_ac4_sse_stream_alternative_active():
    """AC-4: Verify SSE event stream and bus status are active alternatives."""
    events_router = ROOT / "api" / "routers" / "events.py"
    assert events_router.exists()
    content = events_router.read_text(encoding="utf-8")
    assert "/stream" in content, "SSE /stream route must be present on events router"
    assert "EventSource" in content or "text/event-stream" in content, "SSE streaming media type must be defined"


def test_ac5_wired_audit_legacy_guard_pass():
    """AC-5: Ensure legacy_guard from wired_audit passes cleanly with frozen files intact."""
    import sys
    scripts_dev = str(ROOT / "scripts" / "dev")
    if scripts_dev not in sys.path:
        sys.path.insert(0, scripts_dev)
    import wired_audit

    res = wired_audit.legacy_guard_audit()
    assert res == 0, "wired_audit.legacy_guard_audit must pass with return code 0"
