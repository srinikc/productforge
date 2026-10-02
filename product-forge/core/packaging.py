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
