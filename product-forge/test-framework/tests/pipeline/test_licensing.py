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
    # v1.0 model (BI-PF-1264): base 'Create Products' is in every tier; add-ons differentiate tiers.
    assert lic.entled("trial", "build-products")            # base group
    assert lic.entled("pro", "content-media")               # add-on present in pro
    assert not lic.entled("trial", "content-media")         # add-on not in trial
    assert not lic.entled("trial", "worker-internals")      # internal-only never granted
    eff = lic.effective_limits("trial", {"max_parallel_projects": 3, "max_created_projects": 20})
    assert eff["max_parallel_projects"] == 1  # tier 1 < global 3
    assert eff["max_created_projects"] == 2


def test_entitlement_model_version_and_internal():
    assert lic.model_version()
    assert "security" in lic.baseline()
    assert lic.is_internal("worker-internals") and not lic.is_internal("build-products")
    ent = lic.entitlements("enterprise")
    assert ent["model_version"] == lic.model_version() and "security" in ent["baseline"]
    # internal groups are NEVER part of any tier's granted groups (customers can't buy them)
    for t in lic.tiers().values():
        assert not any(lic.is_internal(g) for g in (t.get("groups") or []))


def test_instance_role_and_platform_admin(monkeypatch):
    monkeypatch.setenv("INSTANCE_ROLE", "tenant")
    assert lic.instance_role() == "tenant"
    assert lic.is_platform_admin(["platform_admin"]) is False
    monkeypatch.setenv("INSTANCE_ROLE", "operator")
    assert lic.instance_role() == "operator"
    assert lic.is_platform_admin(["platform_admin"]) is True
