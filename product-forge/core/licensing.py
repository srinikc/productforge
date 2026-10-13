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

try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

REPO = str(_PF_ROOT)
FORGE_DIR = os.path.join(REPO, "data", "licensing")
TIERS_FILE = os.path.join(REPO, "config", "licensing-tiers.json")
LICENSES_FILE = os.path.join(FORGE_DIR, "licenses.json")
TENANTS_FILE = os.path.join(FORGE_DIR, "tenants.json")
KEY_FILE = os.path.join(FORGE_DIR, ".signing-key")

# Entitlement model v1.0 (BI-PF-1264): customer-centric feature groups. Each group carries a name,
# a category (base | addon | internal) and an `internal` flag. BASE 'Create Products' is in every tier;
# ADD-ONS differentiate tiers; INTERNAL groups (worker, PF's own work, platform ops) are NEVER granted to a
# customer tier. `FEATURE_GROUPS` is kept as a {key: name} map for existing read-models.
DEFAULT_GROUPS: Dict[str, Dict[str, Any]] = {
    "build-products": {"name": "Build Products (generation engine/workspace)", "category": "base", "internal": False},
    "ideate-design": {"name": "Ideate & Design", "category": "base", "internal": False},
    "assure-quality": {"name": "Assure Quality", "category": "base", "internal": False},
    "plan-deliver": {"name": "Plan & Deliver", "category": "base", "internal": False},
    "extend-integrate": {"name": "Integrate & Extend", "category": "addon", "internal": False},
    "team-multi-tenancy": {"name": "Team & Multi-Tenancy", "category": "addon", "internal": False},
    "choose-ai-models": {"name": "Choose Your AI Models", "category": "addon", "internal": False},
    "content-media": {"name": "Create Content & Media", "category": "addon", "internal": False},
    "ai-agents": {"name": "Automate with AI Agents", "category": "addon", "internal": False},
    "launch-grow": {"name": "Launch & Grow", "category": "addon", "internal": False},
    "advanced-compliance": {"name": "Advanced Compliance", "category": "addon", "internal": False},
    "worker-internals": {"name": "Worker / Orchestration (internal)", "category": "internal", "internal": True},
    "pf-internal-work": {"name": "PF Internal Work (internal)", "category": "internal", "internal": True},
    "platform-ops-licensing": {"name": "Platform Ops & Licensing (internal)", "category": "internal", "internal": True},
}
_BASE_GROUPS = ["build-products", "ideate-design", "assure-quality", "plan-deliver"]
_ADDON_GROUPS = ["extend-integrate", "team-multi-tenancy", "choose-ai-models", "content-media",
                 "ai-agents", "launch-grow", "advanced-compliance"]

# Back-compat {key: name} map consumed by read-models (API/dashboard); the config is the source of truth.
FEATURE_GROUPS = {k: v["name"] for k, v in DEFAULT_GROUPS.items()}
DEFAULT_BASELINE = ["security"]
MODEL_VERSION = "1.0"

DEFAULT_TIERS = {
    "trial": {"rank": 0, "groups": list(_BASE_GROUPS), "seats": 3,
              "max_parallel_projects": 1, "max_created_projects": 2, "trial_days": 14},
    "starter": {"rank": 1, "groups": _BASE_GROUPS + ["extend-integrate"], "seats": 10,
                "max_parallel_projects": 3, "max_created_projects": 20},
    "pro": {"rank": 2, "groups": _BASE_GROUPS + ["extend-integrate", "team-multi-tenancy", "choose-ai-models",
                                                 "content-media", "ai-agents"], "seats": 50,
            "max_parallel_projects": 10, "max_created_projects": 100},
    "enterprise": {"rank": 3, "groups": _BASE_GROUPS + _ADDON_GROUPS, "seats": 0,
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


def _cfg() -> Dict[str, Any]:
    c = _rj(TIERS_FILE, {}) or {}
    return c if isinstance(c, dict) else {}


def tiers() -> Dict[str, Dict[str, Any]]:
    prof = _cfg().get("tiers")
    return prof or DEFAULT_TIERS


def model_version() -> str:
    """The entitlement model version governing this install (BI-PF-1264)."""
    return str(_cfg().get("entitlement_model_version") or MODEL_VERSION)


def baseline() -> List[str]:
    """Entitlements present in EVERY tier (e.g., security)."""
    return list(_cfg().get("baseline") or DEFAULT_BASELINE)


def feature_groups() -> Dict[str, Dict[str, Any]]:
    """The feature-group model: ``{key: {name, category, internal}}``."""
    g = _cfg().get("feature_groups")
    return g if isinstance(g, dict) and g else DEFAULT_GROUPS


def is_internal(group: str) -> bool:
    """Internal-only groups (worker, PF's own work, platform ops) - never granted to a customer tier."""
    return bool((feature_groups().get(group) or {}).get("internal"))


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
    """Is `group` entitled by `tier`? Internal-only groups are never entitled to a customer tier."""
    t = tiers().get(tier)
    if not t or is_internal(group):
        return False
    return group in (t.get("groups") or [])


def entitlements(tier: str) -> Dict[str, Any]:
    t = tiers().get(tier) or {}
    gi = feature_groups()
    return {"tier": tier, "model_version": model_version(), "groups": t.get("groups", []),
            "baseline": baseline(),
            "seats": t.get("seats", 0),
            "max_parallel_projects": t.get("max_parallel_projects", 0),
            "max_created_projects": t.get("max_created_projects", 0),
            "group_titles": {g: (gi.get(g) or {}).get("name", g) for g in (t.get("groups") or [])}}


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
