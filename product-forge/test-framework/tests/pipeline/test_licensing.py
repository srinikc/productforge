"""Tests for core/licensing.py (BI-0057/0060..0064/0069 + A2 asymmetric licensing BI-PF-0396)."""
import base64
import json
import sys
from pathlib import Path

import pytest

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


# --- A2 (BI-PF-0396): asymmetric licensing + entitlement-at-boundary ---

def test_asymmetric_license_unlocks_entitlements():
    """AC1: a license issued (private key) + verified (public key) unlocks its tier's capabilities."""
    k = lic.issue_key("acme", "pro", days=30)
    assert k and lic.public_key()
    p = lic.verify_key(k)
    assert p and p["tier"] == "pro"
    ent = lic.entitlements(p["tier"])
    assert "content-media" in ent["groups"] and lic.entled(p["tier"], "content-media")


def test_unentitled_action_refused():
    """AC2: an unentitled action is refused at the boundary (fail-closed)."""
    with pytest.raises(lic.LicenseError):
        lic.require_entitlement("trial", "content-media")
    lic.require_entitlement("pro", "content-media")  # entitled -> no raise
    assert lic.enforcement("trial", "content-media")["allowed"] is False
    assert lic.enforcement("", "build-products")["allowed"] is False  # unknown tier refused


def test_forged_license_payload_rejected():
    """AC4: tampering the license body fails verification (install stays locked)."""
    k = lic.issue_key("acme", "trial", days=30)
    body, sig = k[3:].split(".", 1)
    raw = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    raw["tier"] = "enterprise"
    forged = base64.urlsafe_b64encode(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
    assert lic.verify_key("PF-" + forged + "." + sig) is None


def test_verify_uses_public_key_only():
    """AC3: the token carries body.signature only (no private key); verify works via the public key."""
    k = lic.issue_key("acme", "starter", days=30)
    assert lic.public_key() and k.count(".") == 1
    assert lic.verify_key(k) is not None


def test_enforce_for_instance(monkeypatch):
    """AC2/AC6: the instance boundary refuses unentitled groups (tenant), operator is exempt."""
    monkeypatch.setenv("INSTANCE_ROLE", "operator")
    lic.enforce_for_instance("content-media")  # operator instance not gated -> allowed
    monkeypatch.setenv("INSTANCE_ROLE", "tenant")
    monkeypatch.setenv("PF_TENANT", "no-such-tenant")
    with pytest.raises(lic.LicenseError):
        lic.enforce_for_instance("content-media")  # unknown tenant tier -> refused
