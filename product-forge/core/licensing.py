"""Licensing & entitlements for Product Forge (backend).

Single concern: subscription/licensing - tiers, feature-group entitlements, seats,
per-tier project concurrency, trials, signed license keys, tenant provisioning,
and the operator/tenant instance-role + platform_admin authorization.

Owner stores (single writer = this module):
  ``product-forge/licensing/licenses.json``  — issued license keys (kind=control)
  ``product-forge/licensing/tenants.json``   — tenants/subscriptions (kind=config)

Design:
- Feature GROUPS G1..G10 are categorized capabilities; each TIER enables a set.
- A license KEY is a compact signed token: base64url(payload).HMAC-SHA256(payload).
  Payload: {tenant, tier, seats, concurrency, trial, exp}. Signed with
  LICENSE_SIGNING_KEY (env) or a generated key file - no external deps.
- Enforcement points read `entled(tier, group)` + `effective_limits(...)`; the
  global capacity governor stays the hard ceiling, the tier quota is effective.
- Instance role: INSTANCE_ROLE=operator|tenant; platform_admin only on operator.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORGE_DIR = os.path.join(REPO, "data", "licensing")
TIERS_FILE = os.path.join(REPO, "config", "licensing-tiers.json")
LICENSES_FILE = os.path.join(FORGE_DIR, "licenses.json")
TENANTS_FILE = os.path.join(FORGE_DIR, "tenants.json")
KEY_FILE = os.path.join(FORGE_DIR, ".signing-key")

FEATURE_GROUPS = {
    "G1": "Core Orchestration & Portfolio",
    "G2": "Discovery & Design",
    "G3": "Quality & Compliance",
    "G4": "Build/Deploy/Ops",
    "G5": "Intake & Work Management",
    "G6": "Collaboration & Tenancy",
    "G7": "Intelligence (chat/learning/model-rec/BYOT)",
    "G8": "Content & Media",
    "G9": "Platform Ops & Licensing (operator-only)",
    "G10": "Extensibility & API",
}

DEFAULT_TIERS = {
    "trial": {"rank": 0, "groups": ["G1", "G2", "G5"], "seats": 3,
              "max_parallel_projects": 1, "max_created_projects": 2, "trial_days": 14},
    "starter": {"rank": 1, "groups": ["G1", "G2", "G3", "G5", "G10"], "seats": 10,
                "max_parallel_projects": 3, "max_created_projects": 20},
    "pro": {"rank": 2, "groups": ["G1", "G2", "G3", "G4", "G5", "G6", "G10"], "seats": 50,
            "max_parallel_projects": 10, "max_created_projects": 100},
    "enterprise": {"rank": 3, "groups": list(FEATURE_GROUPS.keys()), "seats": 0,
                   "max_parallel_projects": 0, "max_created_projects": 0},  # 0 = unlimited
}


def _rj(p: str, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _wj(p: str, data) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def tiers() -> Dict[str, Dict[str, Any]]:
    cfg = _rj(TIERS_FILE, {}) or {}
    prof = cfg.get("tiers") if isinstance(cfg, dict) else None
    return prof or DEFAULT_TIERS


def _signing_key() -> bytes:
    env = os.getenv("LICENSE_SIGNING_KEY", "").strip()
    if env:
        return env.encode()
    k = _rj(KEY_FILE, None)
    if not k:
        k = secrets.token_urlsafe(48)
        _wj(KEY_FILE, {"key": k})
        try:
            os.chmod(KEY_FILE, 0o600)
        except Exception:
            pass
    return (k.get("key") if isinstance(k, dict) else str(k)).encode()


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_key(tenant: str, tier: str, seats: Optional[int] = None,
              concurrency: Optional[int] = None, trial_days: int = 0,
              days: int = 365) -> str:
    """Sign and return a license key for a tenant/tier."""
    t = tiers().get(tier) or tiers()["trial"]
    exp = datetime.now() + timedelta(days=trial_days or days)
    payload = {
        "tenant": tenant, "tier": tier,
        "seats": int(t.get("seats", 0) if seats is None else seats),
        "concurrency": int(t.get("max_parallel_projects", 0) if concurrency is None else concurrency),
        "trial": bool(trial_days),
        "exp": exp.isoformat(),
        "iat": datetime.now().isoformat(),
        "nonce": secrets.token_hex(6),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(_signing_key(), raw, hashlib.sha256).digest()
    return f"PF-{_b64e(raw)}.{_b64e(sig)}"


def verify_key(key: str) -> Optional[Dict[str, Any]]:
    """Verify a license key; return its payload or None if invalid/expired."""
    try:
        if not key or not key.startswith("PF-"):
            return None
        body = key[3:]
        p_b64, s_b64 = body.split(".", 1)
        raw = _b64d(p_b64)
        sig = _b64d(s_b64)
        if not hmac.compare_digest(sig, hmac.new(_signing_key(), raw, hashlib.sha256).digest()):
            return None
        payload = json.loads(raw.decode())
        if payload.get("exp"):
            try:
                if datetime.fromisoformat(payload["exp"]) < datetime.now():
                    payload["expired"] = True
            except Exception:
                pass
        return payload
    except Exception:
        return None


def entled(tier: str, group: str) -> bool:
    """Is `group` (G1..G10) entitled by `tier`?"""
    t = tiers().get(tier)
    if not t:
        return False
    return group in (t.get("groups") or [])


def entitlements(tier: str) -> Dict[str, Any]:
    t = tiers().get(tier) or {}
    return {"tier": tier, "groups": t.get("groups", []),
            "seats": t.get("seats", 0),
            "max_parallel_projects": t.get("max_parallel_projects", 0),
            "max_created_projects": t.get("max_created_projects", 0),
            "group_titles": {g: FEATURE_GROUPS.get(g, g) for g in (t.get("groups") or [])}}


def effective_limits(tier: str, global_limits: Dict[str, Any]) -> Dict[str, Any]:
    """min(tier quota, global ceiling). 0 means unlimited on either side."""
    t = tiers().get(tier) or {}

    def _eff(a, b):
        a, b = int(a or 0), int(b or 0)
        if a == 0:
            return b
        if b == 0:
            return a
        return min(a, b)

    return {
        "max_parallel_projects": _eff(t.get("max_parallel_projects"), global_limits.get("max_parallel_projects")),
        "max_created_projects": _eff(t.get("max_created_projects"), global_limits.get("max_created_projects")),
        "seats": int(t.get("seats", 0) or 0),
    }


# ── stores ───────────────────────────────────────────────────────────────────
def load_tenants() -> Dict[str, Any]:
    return _rj(TENANTS_FILE, {}) or {}


def load_licenses() -> Dict[str, Any]:
    return _rj(LICENSES_FILE, {}) or {}


def provision_tenant(name: str, tier: str = "trial", owner_email: str = "",
                     trial_days: int = 0, days: int = 365) -> Dict[str, Any]:
    """Create/activate a tenant + issue its license (idempotent by name)."""
    if tier not in tiers():
        raise ValueError(f"unknown tier: {tier}")
    tenants = load_tenants()
    lic = load_licenses()
    if name in tenants and not trial_days:
        return tenants[name]
    key = issue_key(name, tier, trial_days=trial_days, days=days)
    now = datetime.now().isoformat()
    rec = {"tenant": name, "tier": tier, "owner_email": owner_email,
           "status": "trial" if trial_days else "active",
           "license_key": key, "created_at": tenants.get(name, {}).get("created_at", now),
           "updated_at": now,
           "expires_at": (verify_key(key) or {}).get("exp")}
    tenants[name] = rec
    lic[key] = {"tenant": name, "tier": tier, "status": rec["status"],
                "issued_at": now, "revoked": False, **(verify_key(key) or {})}
    _wj(TENANTS_FILE, tenants)
    _wj(LICENSES_FILE, lic)
    return rec


def revoke_key(key: str) -> bool:
    lic = load_licenses()
    if key not in lic:
        return False
    lic[key]["revoked"] = True
    lic[key]["status"] = "revoked"
    _wj(LICENSES_FILE, lic)
    return True


def extend_key(key: str, days: int) -> Optional[Dict[str, Any]]:
    p = verify_key(key)
    if not p:
        return None
    ten = p.get("tenant")
    new = issue_key(ten, p.get("tier", "trial"), seats=p.get("seats"),
                    concurrency=p.get("concurrency"), days=int(days))
    tenants = load_tenants()
    if ten in tenants:
        tenants[ten]["license_key"] = new
        tenants[ten]["updated_at"] = datetime.now().isoformat()
        _wj(TENANTS_FILE, tenants)
    return {"old_key": key, "new_key": new, "payload": verify_key(new)}


def expire_trials() -> List[str]:
    """Mark expired trials; return the affected tenants."""
    tenants = load_tenants()
    out = []
    for name, rec in tenants.items():
        if rec.get("status") == "trial":
            p = verify_key(rec.get("license_key", ""))
            if not p or p.get("expired"):
                rec["status"] = "expired"
                out.append(name)
    if out:
        _wj(TENANTS_FILE, tenants)
    return out


# ── instance role / authorization ────────────────────────────────────────────
def instance_role() -> str:
    """INSTANCE_ROLE=operator|tenant (default tenant for customer builds)."""
    r = os.getenv("INSTANCE_ROLE", "tenant").strip().lower()
    return r if r in ("operator", "tenant") else "tenant"


def is_platform_admin(roles: Optional[List[str]] = None) -> bool:
    """platform_admin is only meaningful on an operator instance (BI-0069)."""
    if instance_role() != "operator":
        return False
    return bool(roles and "platform_admin" in roles)
