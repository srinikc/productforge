"""Tests for Plane A one-command delivery CLI (BI-PF-1549)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DEV = ROOT / "scripts" / "dev"


def test_deliver_cli_help():
    """Verify scripts/dev/deliver.py exposes --item flag."""
    res = subprocess.run([sys.executable, str(SCRIPTS_DEV / "deliver.py"), "--help"],
                         capture_output=True, text=True, check=True)
    assert "--item" in res.stdout
    assert "Plane A: deliver a specific completed item" in res.stdout
    assert "--no-push" in res.stdout


def test_finalize_item_cli_help():
    """Verify scripts/dev/finalize_item.py exposes --deliver flag."""
    res = subprocess.run([sys.executable, str(SCRIPTS_DEV / "finalize_item.py"), "--help"],
                         capture_output=True, text=True, check=True)
    assert "--deliver" in res.stdout
    assert "Plane A: execute one-command delivery" in res.stdout


def test_deliver_refuses_on_integration_branch(monkeypatch):
    """Verify deliver_plane_a rejects execution if invoked directly on develop/main."""
    sys.path.insert(0, str(SCRIPTS_DEV))
    import deliver

    # Mock git branch to simulate being on develop
    monkeypatch.setattr(deliver, "_run_cmd", lambda cmd, **kwargs:
                        type("CP", (), {"stdout": "develop\n", "returncode": 0})())

    with pytest.raises(RuntimeError, match="Cannot deliver from integration branch 'develop'"):
        deliver.deliver_plane_a("BI-PF-9999", scope="product_forge")


def test_deliver_plane_a_signature():
    """Verify deliver_plane_a has expected arguments and defaults."""
    sys.path.insert(0, str(SCRIPTS_DEV))
    import deliver
    import inspect

    sig = inspect.signature(deliver.deliver_plane_a)
    params = list(sig.parameters.keys())
    assert "item_id" in params
    assert "scope" in params
    assert "project" in params
    assert "push" in params
    assert "delete_branch" in params
