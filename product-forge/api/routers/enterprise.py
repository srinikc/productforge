"""Enterprise / SaaS / OEM API (API-4): tenants, users, licenses, entitlements, members, seats, billing.

A thin, API-first HTTP surface over the EXISTING canonical owners: ``core.control_plane`` (control-plane
tenants/users), ``core.licensing`` (tiers/license keys/entitlements), ``core.tenancy`` (members/seats) and
``core.billing`` (self-service checkout). No new engine and no new store; every owner import is lazy.
Reads are authenticated; mutations are operator-gated.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/enterprise", tags=["enterprise"])


def _tenant_id(tenant: str) -> str:
    t = str(tenant or "").strip()
    if not t or "/" in t or "\\" in t or t in (".", ".."):
        raise ApiError("VALIDATION_FAILED", "invalid tenant", details={"tenant": tenant})
    return t


def _tier(tier: str) -> str:
    from core import licensing
    t = str(tier or "").strip()
    if t not in licensing.tiers():
        raise ApiError("VALIDATION_FAILED", "unknown tier",
                       details={"allowed": sorted(licensing.tiers().keys())})
    return t


def _int_or_fail(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError("VALIDATION_FAILED", f"{field} must be an integer", details={field: value})


@router.get("/instance", dependencies=[Depends(authenticate)])
def get_instance(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import licensing, tenancy
    data = {"role": licensing.instance_role(),
            "tenant": tenancy.instance_tenant(),
            "platform_admin": licensing.is_platform_admin(ctx.get("roles") or [])}
    return from_request(request, data, resource="enterprise", resource_id="instance")


@router.get("/tenants", dependencies=[Depends(authenticate)])
def list_tenants(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import control_plane
    return from_request(request, control_plane.list_tenants(), resource="enterprise")


@router.get("/tenants/{tenant}", dependencies=[Depends(authenticate)])
def get_tenant(tenant: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import control_plane, licensing
    t = _tenant_id(tenant)
    rec = (licensing.load_tenants() or {}).get(t)
    if not rec:
        try:
            rec = next((r for r in control_plane.list_tenants() if r.get("id") == t), None)
        except Exception:
            rec = None
    if not rec:
        raise ApiError("NOT_FOUND", "tenant not found")
    return from_request(request, rec, resource="enterprise", resource_id=t)


@router.get("/users", dependencies=[Depends(authenticate)])
def list_users(request: Request, tenant: str = "", ctx: Dict[str, Any] = Depends(authenticate)):
    from core import control_plane
    t = _tenant_id(tenant) if str(tenant or "").strip() else ""
    return from_request(request, control_plane.list_users(t), resource="enterprise", resource_id=t)


@router.get("/tiers", dependencies=[Depends(authenticate)])
def list_tiers(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import licensing
    return from_request(request, licensing.tiers(), resource="enterprise")


@router.get("/tenants/{tenant}/license", dependencies=[Depends(authenticate)])
def get_license(tenant: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import licensing
    t = _tenant_id(tenant)
    rec = (licensing.load_tenants() or {}).get(t)
    if not rec:
        raise ApiError("NOT_FOUND", "tenant not found")
    key = rec.get("license_key", "") or ""
    return from_request(request, {"tenant": t, "tier": rec.get("tier"), "status": rec.get("status"),
                                  "license_key": key, "expires_at": rec.get("expires_at"),
                                  "payload": licensing.verify_key(key) if key else None},
                        resource="enterprise", resource_id=t)


@router.get("/tenants/{tenant}/entitlements", dependencies=[Depends(authenticate)])
def get_entitlements(tenant: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import licensing
    t = _tenant_id(tenant)
    rec = (licensing.load_tenants() or {}).get(t)
    if not rec:
        raise ApiError("NOT_FOUND", "tenant not found")
    return from_request(request, licensing.entitlements(rec.get("tier") or "trial"),
                        resource="enterprise", resource_id=t)


@router.get("/tenants/{tenant}/members", dependencies=[Depends(authenticate)])
def list_members(tenant: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import tenancy
    t = _tenant_id(tenant)
    return from_request(request, tenancy.members(t), resource="enterprise", resource_id=t)


@router.get("/tenants/{tenant}/seats", dependencies=[Depends(authenticate)])
def get_seats(tenant: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import tenancy
    t = _tenant_id(tenant)
    return from_request(request, tenancy.seats(t), resource="enterprise", resource_id=t)


@router.post("/tenants", dependencies=[Depends(require_operator)])
def create_tenant(body: Dict[str, Any], request: Request,
                  ctx: Dict[str, Any] = Depends(require_operator)):
    from core import control_plane, licensing
    name = str(body.get("name") or "").strip()
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ApiError("VALIDATION_FAILED", "name required")
    tier = _tier(str(body.get("tier") or "trial"))
    owner_email = str(body.get("owner_email") or "").strip()
    try:
        rec = licensing.provision_tenant(name, tier, owner_email=owner_email)
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e))
    try:
        control_plane.create_tenant(name, tier=tier, status=rec.get("status", "active"))
        if owner_email:
            control_plane.upsert_user(name, owner_email, roles=["owner"])
    except Exception:
        pass
    return from_request(request, rec, resource="enterprise", resource_id=name, status="ok")


@router.post("/tenants/{tenant}/members", dependencies=[Depends(require_operator)])
def add_member(tenant: str, body: Dict[str, Any], request: Request,
               ctx: Dict[str, Any] = Depends(require_operator)):
    from core import tenancy
    t = _tenant_id(tenant)
    email = str(body.get("email") or "").strip()
    if not email or "@" not in email:
        raise ApiError("VALIDATION_FAILED", "valid email required")
    try:
        rec = tenancy.invite(t, email, roles=body.get("roles"), team=str(body.get("team") or ""))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e))
    return from_request(request, rec, resource="enterprise", resource_id=t)


@router.post("/tenants/{tenant}/license", dependencies=[Depends(require_operator)])
def issue_license(tenant: str, body: Dict[str, Any], request: Request,
                  ctx: Dict[str, Any] = Depends(require_operator)):
    from core import licensing
    t = _tenant_id(tenant)
    tier = _tier(str(body.get("tier") or "trial"))
    seats = body.get("seats")
    if seats is not None:
        seats = _int_or_fail(seats, "seats")
    key = licensing.issue_key(t, tier, seats=seats)
    return from_request(request, {"tenant": t, "tier": tier, "license_key": key,
                                  "payload": licensing.verify_key(key)},
                        resource="enterprise", resource_id=t)


@router.post("/tenants/{tenant}/checkout", dependencies=[Depends(require_operator)])
def checkout(tenant: str, body: Dict[str, Any], request: Request,
             ctx: Dict[str, Any] = Depends(require_operator)):
    from core import billing
    t = _tenant_id(tenant)
    tier = _tier(str(body.get("tier") or "trial"))
    email = str(body.get("email") or "").strip()
    trial_days = _int_or_fail(body.get("trial_days") or 0, "trial_days")
    res = billing.checkout(t, tier, email=email, trial_days=trial_days)
    if not res.get("ok"):
        raise ApiError("CONFLICT", res.get("error") or "checkout failed")
    return from_request(request, res, resource="enterprise", resource_id=t)
