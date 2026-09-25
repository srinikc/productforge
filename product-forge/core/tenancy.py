"""Tenancy: tenant members, teams, roles, seats (BI-0068).

Single concern: the customer (tenant) admin surface - who belongs to a tenant,
their team, their role, and seat accounting against the license tier.

Owner store: ``product-forge/tenancy/members.json`` (kind=evidence, scope=product_forge)
Roles: owner | admin | write | read (bidirectional checked by the API layer).
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

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

REPO = str(_PF_ROOT)
STORE = os.path.join(REPO, "data", "tenancy", "members.json")
VALID_ROLES = {"owner", "admin", "write", "read"}


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


def _norm_roles(roles) -> List[str]:
    if isinstance(roles, str):
        roles = [roles]
    out = [str(r).strip().lower() for r in (roles or []) if str(r).strip()]
    bad = [r for r in out if r not in VALID_ROLES]
    if bad:
        raise ValueError(f"invalid roles: {bad} (allowed: {sorted(VALID_ROLES)})")
    return sorted(set(out))


def members(tenant: str) -> List[Dict[str, Any]]:
    return (_rj(STORE, {}) or {}).get(tenant, [])


def invite(tenant: str, email: str, roles=None, team: str = "") -> Dict[str, Any]:
    """Invite a member (idempotent by tenant+email)."""
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email required")
    data = _rj(STORE, {}) or {}
    bucket = data.setdefault(tenant, [])
    rr = _norm_roles(roles or ["read"])
    for m in bucket:
        if m.get("email") == email:
            m["roles"] = rr
            m["team"] = team or m.get("team", "")
            m["updated_at"] = datetime.now().isoformat()
            _wj(STORE, data)
            return m
    rec = {"tenant": tenant, "email": email, "roles": rr, "team": team,
           "status": "invited", "invited_at": datetime.now().isoformat(),
           "updated_at": datetime.now().isoformat()}
    bucket.append(rec)
    _wj(STORE, data)
    return rec


def set_role(tenant: str, email: str, roles) -> Optional[Dict[str, Any]]:
    data = _rj(STORE, {}) or {}
    for m in data.get(tenant, []):
        if m.get("email") == (email or "").strip().lower():
            m["roles"] = _norm_roles(roles)
            m["updated_at"] = datetime.now().isoformat()
            _wj(STORE, data)
            return m
    return None


def remove_member(tenant: str, email: str) -> bool:
    data = _rj(STORE, {}) or {}
    bucket = data.get(tenant, [])
    n = len(bucket)
    data[tenant] = [m for m in bucket if m.get("email") != (email or "").strip().lower()]
    if len(data[tenant]) != n:
        _wj(STORE, data)
        return True
    return False


def seats(tenant: str, tier: str = "") -> Dict[str, Any]:
    used = len(members(tenant))
    limit = 0
    try:
        from core import licensing
        if not tier:
            tier = (licensing.load_tenants().get(tenant) or {}).get("tier", "trial")
        limit = int((licensing.tiers().get(tier) or {}).get("seats", 0) or 0)
    except Exception:
        pass
    return {"tenant": tenant, "tier": tier, "used": used, "limit": limit,
            "available": (limit - used) if limit else None}
