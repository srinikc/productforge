"""Billing / self-service checkout (BI-0058, BI-0066).

Single concern: turn a plan choice into a paid entitlement + provisioned tenant.
The payment provider is PLUGGABLE (env ``BILLING_PROVIDER``):

  * ``null``   (default) - dev/self-host: mark paid immediately, issue license.
  * ``stripe`` - placeholder wired for later (needs STRIPE_API_KEY + webhook).

Flow: checkout(tenant, tier, email) -> provider.charge -> issue license
(core/licensing) -> provision tenant (core/licensing + core/control_plane).
No store is written outside the owning modules.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict


def provider_name() -> str:
    return os.getenv("BILLING_PROVIDER", "null").strip().lower() or "null"


def _charge(tenant: str, tier: str, email: str) -> Dict[str, Any]:
    """Charge via the configured provider. Returns {paid: bool, ...}."""
    p = provider_name()
    if p == "null":
        return {"paid": True, "provider": "null", "note": "dev/self-host: auto-paid"}
    if p == "stripe":
        key = os.getenv("STRIPE_API_KEY", "").strip()
        if not key:
            return {"paid": False, "provider": "stripe", "error": "STRIPE_API_KEY not set"}
        # Placeholder: real Checkout Session creation goes here (redirect_url).
        return {"paid": False, "provider": "stripe",
                "error": "stripe checkout not implemented yet", "next": "create Checkout Session"}
    return {"paid": False, "provider": p, "error": f"unknown billing provider: {p}"}


def checkout(tenant: str, tier: str, email: str = "", trial_days: int = 0) -> Dict[str, Any]:
    """Self-service: charge -> issue license -> provision tenant + owner user."""
    charge = _charge(tenant, tier, email)
    if not charge.get("paid"):
        return {"ok": False, "stage": "charge", **charge}

    from core import licensing
    if tier not in licensing.tiers():
        return {"ok": False, "stage": "plan", "error": f"unknown tier: {tier}"}
    rec = licensing.provision_tenant(tenant, tier, owner_email=email, trial_days=trial_days)

    try:
        from core import control_plane as cp
        cp.create_tenant(tenant, tier=tier, status=rec.get("status", "active"))
        if email:
            cp.upsert_user(tenant, email, roles=["owner"])
    except Exception:
        pass

    return {"ok": True, "tenant": tenant, "tier": tier, "status": rec.get("status"),
            "license_key": rec.get("license_key"), "expires_at": rec.get("expires_at"),
            "provider": charge.get("provider"), "at": datetime.now().isoformat()}
