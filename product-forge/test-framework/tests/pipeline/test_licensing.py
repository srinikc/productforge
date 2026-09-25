"""Tests for core/licensing.py (BI-0057/0060..0064/0069)."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.licensing as lic  # noqa: E402


def test_issue_and_verify_key():
    k = lic.issue_key("acme", "pro", days=30)
    p = lic.verify_key(k)
    assert p and p["tenant"] == "acme" and p["tier"] == "pro"


def test_tampered_key_is_invalid():
    k = lic.issue_key("acme", "pro", days=30)
    body, sig = k[3:].split(".", 1)
    bad = "PF-" + body + "." + ("A" * len(sig))
    assert lic.verify_key(bad) is None


def test_trial_expiry_flags():
    k = lic.issue_key("t1", "trial", trial_days=-1)  # already past
    p = lic.verify_key(k)
    assert p and p.get("trial") and p.get("expired")


def test_entitlements_and_effective_limits():
    assert lic.entled("pro", "G4") and not lic.entled("trial", "G4")
    eff = lic.effective_limits("trial", {"max_parallel_projects": 3, "max_created_projects": 20})
    assert eff["max_parallel_projects"] == 1  # tier 1 < global 3
    assert eff["max_created_projects"] == 2


def test_instance_role_and_platform_admin(monkeypatch):
    monkeypatch.setenv("INSTANCE_ROLE", "tenant")
    assert lic.instance_role() == "tenant"
    assert lic.is_platform_admin(["platform_admin"]) is False
    monkeypatch.setenv("INSTANCE_ROLE", "operator")
    assert lic.instance_role() == "operator"
    assert lic.is_platform_admin(["platform_admin"]) is True
