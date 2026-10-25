"""REL-0: Packaging / Licensing / Entitlement / Deployment (plan section 25).

Produces and validates the **deployment-specific package manifest** for an edition
(community | enterprise | saas | on-prem | oem), consuming the canonical owners:

  - ``core.bom``             -> package metadata, dependencies, SBOM, license metadata
  - ``core.build_manager``   -> version + build provenance
  - ``core.licensing``       -> entitlement requirements per edition/tier
  - ``core.deploy_providers``-> deployment manifest / runtime policy
  - ``core.release_manager`` -> install / upgrade / rollback path + installation validation

This module **orchestrates and validates**; it does not reimplement SBOM, entitlements or deployment,
and it makes no commercial decision — licensing/pricing stays human-governed (plan section 25).
Output is a single derived manifest (``packaging-manifest.json``; owner = this module).
"""
import json
import os
import re
from datetime import datetime
from typing import Any

from core.paths import PRODUCTS_DIR, ROOT

# edition -> (licensing tier, default deploy target, distribution kind)
EDITIONS: dict[str, dict[str, Any]] = {
    "community": {"tier": "trial", "target": "local", "distribution": "open-source"},
    "enterprise": {"tier": "enterprise", "target": "kubernetes", "distribution": "commercial"},
    "saas": {"tier": "pro", "target": "docker", "distribution": "hosted"},
    "on-prem": {"tier": "enterprise", "target": "docker", "distribution": "commercial"},
    "oem": {"tier": "enterprise", "target": "command", "distribution": "white-label"},
}

# the build-pipeline distinctions REL-0 must keep separate (plan section 25)
DISTINCTIONS = ("source", "build", "artifact", "package", "license", "entitlement",
                "configuration", "deployment_target", "runtime_policy")

MANIFEST = "packaging-manifest.json"
RESIDENCY_DEFAULT = os.path.join(str(ROOT), "config", "residency-manifest.json")
PROFILE_DIR = os.path.join(str(ROOT), "config", "residency-profiles")
RESIDENCY_GROUPS = ("data_classes", "home_region", "allowed_regions", "backup", "kms", "egress", "retention")
FREQUENCIES = ("hourly", "daily", "weekly", "monthly")


def _scope_dir(scope: str, project: str) -> str:
    from core import validation_engine as ve
    if ve._norm_scope(scope) == "product_forge":
        return str(ROOT)
    return os.path.join(str(PRODUCTS_DIR), project)


def editions() -> dict[str, dict[str, Any]]:
    return {k: dict(v) for k, v in EDITIONS.items()}


def _resolve_edition(edition: str) -> dict[str, Any] | None:
    e = str(edition or "").strip().lower()
    if e in EDITIONS:
        return dict(EDITIONS[e], id=e)
    return None


def residency_path(scope: str = "product_forge", project: str = "") -> str:
    """Product override first, then the shipped IN template (explicit, never silent)."""
    if project:
        p = os.path.join(str(PRODUCTS_DIR), project, "residency-manifest.json")
        if os.path.exists(p):
            return p
    return RESIDENCY_DEFAULT


def _load_json(path: str) -> dict:
    if os.path.getsize(path) > 64 * 1024:
        raise ValueError("residency file exceeds 64KB")
    with open(path, encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def residency_profiles_dir() -> str:
    return os.environ.get("PF_RESIDENCY_PROFILES") or PROFILE_DIR


def validate_residency(section: dict) -> dict:
    """Profile-bounded, fail-closed residency validation (Go is the deploy authority)."""
    unmet: list[str] = []
    sec = section or {}
    for k in RESIDENCY_GROUPS:
        if k == "egress":
            if "egress" not in sec or sec.get("egress") is None:
                unmet.append("RESIDENCY_MISSING_GROUP:egress")
            continue
        if k not in sec or sec.get(k) in (None, "", [], {}):
            unmet.append(f"RESIDENCY_MISSING_GROUP:{k}")
    if str(sec.get("schema_version") or "") != "1.0":
        unmet.append("RESIDENCY_SCHEMA_VERSION")
    home = str(sec.get("home_region") or "").upper()
    prof = {}
    if not home or not re.match(r"^[A-Z0-9-]+$", home):
        unmet.append("RESIDENCY_UNKNOWN_HOME")
    else:
        try:
            prof = _load_json(os.path.join(residency_profiles_dir(), f"{home.lower()}-v1.json"))
        except Exception:
            prof = {}
    allowed = {str(x).upper() for x in (prof.get("allowed_regions") or [])}
    if home and (not prof.get("id") or not prof.get("allowed_regions")):
        unmet.append("RESIDENCY_PROFILE_UNREADABLE")
    if home and home not in allowed:
        unmet.append("RESIDENCY_HOME_NOT_ALLOWED")
    sec_allowed = {str(x).upper() for x in (sec.get("allowed_regions") or [])}
    if not sec_allowed or home not in sec_allowed:
        unmet.append("RESIDENCY_HOME_NOT_ALLOWED")
    if prof.get("allowed_regions") and not sec_allowed <= allowed:
        unmet.append("RESIDENCY_REGION_NOT_ALLOWED")
    b = sec.get("backup") or {}
    k = sec.get("kms") or {}
    e = sec.get("egress") or {}
    if not b.get("regions"):
        unmet.append("RESIDENCY_BACKUP_REGION")
    if not str(k.get("region") or "").strip():
        unmet.append("RESIDENCY_KMS_REGION")
    for code, regions in (("BACKUP", b.get("regions") or []),
                          ("KMS", [k.get("region")] if k.get("region") else []),
                          ("EGRESS", e.get("allowed_regions") or [])):
        if not set(str(x).upper() for x in regions) <= allowed:
            unmet.append(f"RESIDENCY_{code}_REGION")
    if not str(k.get("provider") or "").strip():
        unmet.append("RESIDENCY_INVALID_FIELD:kms.provider")
    if b.get("encrypted") is not True:
        unmet.append("RESIDENCY_BACKUP_UNENCRYPTED")
    if b.get("frequency") not in FREQUENCIES:
        unmet.append("RESIDENCY_UNKNOWN_FREQUENCY")
    rot = k.get("rotation_days")
    if not isinstance(rot, int) or isinstance(rot, bool) or rot <= 0:
        unmet.append("RESIDENCY_KMS_ROTATION")
    r = sec.get("retention") or {}
    days = r.get("days")
    max_days = prof.get("retention_days") or 0
    if (not isinstance(days, int) or isinstance(days, bool) or days <= 0
            or (max_days and not r.get("legal_hold") and days > int(max_days))):
        unmet.append("RESIDENCY_RETENTION")
    return {"valid": not unmet, "unmet": unmet, "home_region": home, "profile": prof.get("id") or ""}


def residency_section(scope: str = "product_forge", project: str = "") -> dict:
    """Load the manifest and attach the profile-bounded validation result."""
    try:
        sec = _load_json(residency_path(scope, project))
    except Exception:
        return {"error": "RESIDENCY_MANIFEST_UNREADABLE"}
    sec.pop("notes", None)
    sec.pop("template", None)
    sec["validation"] = validate_residency(sec)
    return sec


def build(scope: str = "product_forge", project: str = "", edition: str = "community") -> dict[str, Any]:
    """Build the package manifest for an edition by consuming the canonical owners."""
    ed = _resolve_edition(edition)
    if ed is None:
        return {"ok": False, "error": f"unknown edition {edition!r}", "editions": list(EDITIONS)}
    d = _scope_dir(scope, project)
    out: dict[str, Any] = {"schema": "product-forge/packaging@1", "scope": scope, "project": project,
                           "edition": ed["id"], "generated_at": datetime.now().isoformat(),
                           "distinctions": dict.fromkeys(DISTINCTIONS), "ok": True}

    # package metadata + version + provenance + dependencies + SBOM + license metadata (core.bom)
    try:
        from core import bom
        b = bom.build(d)
        out["distinctions"]["package"] = {"dependencies": b.get("dependencies", {}),
                                          "licenses": b.get("licenses", []),
                                          "sbom_schema": b.get("schema"), "governance": b.get("governance", [])}
        out["distinctions"]["artifact"] = {"file_count": (b.get("footprint") or {}).get("file_count"),
                                           "total_bytes": (b.get("footprint") or {}).get("total_bytes")}
        out["sbom"] = {"schema": b.get("schema"), "dependencies": b.get("dependencies", {}),
                       "licenses": b.get("licenses", [])}
    except Exception as e:
        out["ok"] = False
        out["distinctions"]["package"] = {"error": type(e).__name__}
    try:
        from core import build_manager
        lb = build_manager.latest_build(d) or {}
        out["distinctions"]["build"] = {"build_id": lb.get("build_id"), "version": lb.get("version"),
                                        "commit": lb.get("commit")}
    except Exception as e:
        out["distinctions"]["build"] = {"error": type(e).__name__}

    # entitlement requirements (core.licensing) — generated, human-governed
    try:
        from core import licensing
        ent = licensing.entitlements(ed["tier"])
        out["distinctions"]["license"] = {"tier": ed["tier"], "distribution": ed["distribution"]}
        out["distinctions"]["entitlement"] = ent
        out["entitlement"] = ent
    except Exception as e:
        out["distinctions"]["entitlement"] = {"error": type(e).__name__}

    # deployment manifest + runtime policy (core.deploy_providers)
    try:
        from core import deploy_providers
        cfg = deploy_providers.load_deploy_cfg(d) or {}
        prov = deploy_providers.select_provider(d, {"target": ed["target"], **cfg})
        out["distinctions"]["deployment_target"] = {"target": ed["target"],
                                                    "provider": getattr(prov, "name", None)}
        out["distinctions"]["runtime_policy"] = {"provider": getattr(prov, "name", None),
                                                 "detected": bool(prov)}
        out["deployment_manifest"] = {"target": ed["target"], "provider": getattr(prov, "name", None)}
    except Exception as e:
        out["distinctions"]["deployment_target"] = {"error": type(e).__name__}

    # upgrade / rollback path + installation validation (core.release_manager)
    try:
        from core import release_manager
        rm = release_manager.ReleaseManager(project or scope, products_dir=str(ROOT / "products")
                                            if hasattr(ROOT, "__truediv__") else os.path.join(str(ROOT), "products"))
        fp = rm.get_resource_footprint()
        out["upgrade_rollback"] = {"strategy_candidates": [rm.select_strategy("medium", "saas")],
                                   "footprint": fp.to_dict() if hasattr(fp, "to_dict") else {}}
    except Exception as e:
        out["upgrade_rollback"] = {"error": type(e).__name__}

    out["residency"] = residency_section(scope, project)
    if (out["residency"].get("validation") or {}).get("valid") is not True:
        out["residency_warning"] = "RESIDENCY_POLICY_VIOLATION"
    out["distinctions"]["source"] = {"source_dir": d}
    out["distinctions"]["configuration"] = {"edition": ed["id"], "tier": ed["tier"]}
    return out


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed validation: every REL-0 distinction must be populated and coherent."""
    unmet: list[str] = []
    if not manifest or manifest.get("ok") is False:
        unmet.append("manifest_build_failed")
    for k in DISTINCTIONS:
        v = (manifest.get("distinctions") or {}).get(k)
        if v is None or (isinstance(v, dict) and v.get("error")):
            unmet.append(f"distinction:{k}")
    # edition-specific entitlement must exist
    if not (manifest.get("entitlement") or {}).get("tier"):
        unmet.append("entitlement:tier")
    rv = validate_residency(manifest.get("residency") or {})
    if not rv["valid"]:
        unmet.extend(f"residency:{e}" for e in rv["unmet"])
    return {"valid": not unmet, "unmet": unmet, "edition": manifest.get("edition"),
            "evaluated_at": datetime.now().isoformat()}


def manifest_path(scope: str = "product_forge", project: str = "") -> str:
    return os.path.join(_scope_dir(scope, project), MANIFEST)


def write(scope: str = "product_forge", project: str = "", edition: str = "community") -> dict[str, Any]:
    """Build + validate + persist the package manifest (single writer: this module)."""
    m = build(scope, project, edition=edition)
    v = validate(m)
    m["validation"] = v
    if not v["valid"]:
        m["ok"] = False
    p = manifest_path(scope, project)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
        m["manifest_path"] = p
    except Exception as e:
        m["ok"] = False
        m["write_error"] = type(e).__name__
    return m


def load(scope: str = "product_forge", project: str = "") -> dict[str, Any]:
    p = manifest_path(scope, project)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


# ── A4 (BI-PF-0397): EAP — the authoritative delivery/build manifest ─────────────────────────────────
# The EAP (Edition/Artifact Package) is how Product Forge decides WHAT GOES INTO a package for an edition:
# it composes the canonical A1 contracts + A2 entitlement + SBOM/build provenance, and declares the EAP
# version + compatibility. BUILD-TIME only (it decides package contents; it is not shipped to customers).
EAP_FILE = "eap.json"
EAP_SCHEMA = "product-forge/eap@1"
EAP_VERSION = "1.0"
EAP_REGISTRY_FILE = os.path.join(str(ROOT), "config", "eap-registry.json")
# canonical contracts the EAP composes (parity with core/contracts.py CONTRACTS)
EAP_CONTRACTS = ("component-manifest", "runtime-profile", "deployment-profile",
                 "license-profile", "entitlement-profile", "bom", "evidence")


def eap_registry() -> dict[str, Any]:
    """The EAP registry (`config/eap-registry.json`): known EAP schema versions + compatibility."""
    try:
        with open(EAP_REGISTRY_FILE, encoding="utf-8-sig") as f:
            d = json.load(f) or {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _compat_covers(ranges: list, version: str) -> bool:
    """Does any declared range (e.g. ``1.x``) cover ``version`` (e.g. ``1.0``)?"""
    v = str(version or "").strip()
    for r in ranges or []:
        r = str(r).strip()
        if not r:
            continue
        if r.endswith(".x") and v.startswith(r[:-1]):
            return True
        if r in (v, "*"):
            return True
    return False


def eap_build(scope: str = "product_forge", project: str = "", edition: str = "community") -> dict[str, Any]:
    """Compose the EAP for an edition from the canonical owners (build-time)."""
    ed = _resolve_edition(edition)
    if ed is None:
        return {"ok": False, "error": f"unknown edition {edition!r}", "editions": list(EDITIONS)}
    reg = eap_registry()
    versions = reg.get("versions") or {}
    eap: dict[str, Any] = {
        "schema": EAP_SCHEMA,
        "eap_version": EAP_VERSION,
        "edition": ed["id"],
        "tier": ed["tier"],
        "distribution": ed["distribution"],
        "deploy_target": ed["target"],
        "contracts": list(EAP_CONTRACTS),
        "compatible_with": list((versions.get(EAP_VERSION) or {}).get("compatible_with") or ["1.x"]),
        "generated_at": datetime.now().isoformat(),
        "ok": True,
    }
    pm = build(scope, project, edition=edition)   # reuse the existing packaging manifest
    eap["packaging"] = pm
    eap["entitlement"] = pm.get("entitlement") or {}
    eap["sbom"] = pm.get("sbom") or {}
    eap["build"] = (pm.get("distinctions") or {}).get("build") or {}
    if pm.get("ok") is False:
        eap["ok"] = False
    return eap


def eap_validate(eap: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed validation of an EAP: required fields, a known version, contracts + compatibility."""
    unmet: list[str] = []
    if not eap or eap.get("ok") is False:
        unmet.append("eap_build_failed")
    if eap.get("schema") != EAP_SCHEMA:
        unmet.append("schema")
    ver = str(eap.get("eap_version") or "")
    reg = eap_registry()
    if not ver or ver not in (reg.get("versions") or {}):
        unmet.append("eap_version:unknown")
    for k in ("edition", "tier", "distribution", "deploy_target"):
        if not eap.get(k):
            unmet.append(k)
    if not (eap.get("contracts") or []):
        unmet.append("contracts")
    if not (eap.get("compatible_with") or []):
        unmet.append("compatible_with")
    if not (eap.get("entitlement") or {}).get("tier"):
        unmet.append("entitlement:tier")
    return {"valid": not unmet, "unmet": unmet, "edition": eap.get("edition"),
            "eap_version": ver, "evaluated_at": datetime.now().isoformat()}


def eap_compatible(eap: dict[str, Any], target_version: str = "") -> dict[str, Any]:
    """Is this EAP compatible with the registry's current (or a given) EAP version?"""
    reg = eap_registry()
    cur = str(target_version or reg.get("current") or EAP_VERSION)
    ranges = list(eap.get("compatible_with") or [])
    ok = _compat_covers(ranges, cur)
    return {"compatible": ok, "current": cur, "declares": ranges,
            "reason": "" if ok else f"EAP compatible_with {ranges} does not cover {cur}"}


def eap_path(scope: str = "product_forge", project: str = "") -> str:
    return os.path.join(_scope_dir(scope, project), EAP_FILE)


def eap_write(scope: str = "product_forge", project: str = "", edition: str = "community") -> dict[str, Any]:
    """Build + validate + persist the EAP (single writer: this module)."""
    eap = eap_build(scope, project, edition=edition)
    v = eap_validate(eap)
    eap["validation"] = v
    eap["compatibility"] = eap_compatible(eap)
    if not v["valid"]:
        eap["ok"] = False
    p = eap_path(scope, project)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(eap, f, indent=2)
        eap["eap_path"] = p
    except Exception as e:
        eap["ok"] = False
        eap["write_error"] = type(e).__name__
    return eap


def eap_load(scope: str = "product_forge", project: str = "") -> dict[str, Any]:
    p = eap_path(scope, project)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}
