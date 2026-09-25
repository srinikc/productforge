"""
Tests for the invocation (reachability) audit — BI-0029.

Guards the "imported but never invoked" class that wired_audit's substring scan
cannot see (e.g. an unused ``# noqa: F401`` import marking a dead module RUNTIME).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
AUDIT = ROOT / "scripts" / "dev" / "invocation_audit.py"


def _run():
    return subprocess.run([sys.executable, str(AUDIT)], cwd=str(ROOT),
                          capture_output=True, text=True)


def test_invocation_audit_passes_with_zero_unwired():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "invocation-audit: OK" in r.stdout
    assert "UNWIRED: 0" in r.stdout


def test_wired_design_modules_are_reachable():
    """Regression for the design-phase modules that were imported-but-never-invoked."""
    r = _run()
    out = r.stdout
    for mod in ("core.discovery_engine", "core.product_design_spec",
                "core.design_tokens", "core.dashboard_archetypes",
                "core.websocket_manager", "core.intake_api"):
        assert mod not in out, f"{mod} is unreachable again"
