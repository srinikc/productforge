"""ENG-10: RELEASE execution — qualify a release candidate and apply a fail-closed release gate (plan section 24).

A release must validate the **actual artifact intended for distribution**, not merely source tests:
full regression, security, performance/NFR, packaging, SBOM/provenance, deployment, and upgrade/rollback,
then produce release evidence. Reuses canonical owners only: ``validation_engine`` (RELEASE profile),
``bom`` (packaging/provenance footprint), ``build_manager`` (build), ``deploy_providers`` (deployment),
``merge_gate`` (integration already green), ``change_log`` (release evidence).

The gate is **mechanical**: licensing/entitlement/pricing decisions are human-governed and live in REL-0.
"""
import contextlib
import os
from datetime import datetime
from typing import Any

from core.paths import ROOT

_ENGINEERING = os.path.join(str(ROOT), "engineering")
RELEASE_EVIDENCE = os.path.join(_ENGINEERING, "release-evidence.jsonl")


def _scope_dir(scope: str, project: str) -> str:
    from core import validation_engine as ve
    if ve._norm_scope(scope) == "product_forge":
        return str(ROOT)
    return ve._dir(scope, project)


def _fingerprint(scope: str, project: str, target: str) -> dict[str, Any]:
    d = _scope_dir(scope, project)
    out: dict[str, Any] = {"dir": d, "target": target}
    try:
        from core import build_manager
        b = build_manager.latest_build(d) or {}
        out["build_id"] = b.get("build_id")
        out["version"] = b.get("version")
        out["build"] = bool(b)
    except Exception:
        out["build"] = False
    try:
        from core import bom
        fp = bom.build(d)
        out["bom_present"] = bool(fp.get("dependencies") is not None)
        out["bom_deps"] = len(fp.get("dependencies") or [])
        out["bom_licenses"] = len(fp.get("licenses") or [])
    except Exception:
        out["bom_present"] = False
    return out


def _deployment(project_dir: str) -> dict[str, Any]:
    """Deployment/upgrade/rollback is proven only if a deploy actually ran and passed.

    Reads the single owner-written record (``core.deploy_providers`` -> ``deployment-evidence.json``);
    absent/unrun evidence is ``unknown`` (fail-closed), never an assumed pass.
    """
    try:
        from core import deploy_providers
    except Exception:
        return {"status": "unknown", "detail": "deploy_providers unavailable"}
    p = os.path.join(project_dir, deploy_providers.DEPLOYMENT_EVIDENCE)
    if not os.path.exists(p):
        return {"status": "unknown",
                "detail": {"evidence": deploy_providers.DEPLOYMENT_EVIDENCE, "present": False}}
    try:
        import json
        with open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
        latest = d.get("latest") or {}
        if not latest.get("ran"):
            return {"status": "unknown", "detail": {"present": True, "ran": False,
                                                    "reason": latest.get("reason", "")}}
        ok = bool(latest.get("passed"))
        return {"status": "pass" if ok else "fail",
                "detail": {"present": True, "provider": latest.get("provider"), "passed": ok}}
    except Exception as e:
        return {"status": "unknown", "detail": f"{deploy_providers.DEPLOYMENT_EVIDENCE}: {type(e).__name__}"}


def gate(scope: str = "product_forge", project: str = "", target: str = "",
         run_id: str = "", release_validation: dict | None = None) -> dict[str, Any]:
    """Build the release checklist (fail-closed) and a decision. Does not write stores."""
    d = _scope_dir(scope, project)
    items: dict[str, dict[str, Any]] = {}

    if release_validation is None:
        try:
            from core import validation_engine as ve
            release_validation = ve.run(project or scope, d, profile_name="RELEASE",
                                        target=target, run_id=run_id, scope=scope)
        except Exception as e:
            release_validation = {"result": "BLOCKED", "reason": f"validation error: {type(e).__name__}"}
    rv_checks = release_validation.get("checks") or {}
    items["release_validation"] = {"status": "pass" if release_validation.get("result") == "PASS" else "fail",
                                   "detail": {"result": release_validation.get("result"),
                                              "run_id": release_validation.get("run_id"),
                                              "checks": sorted(rv_checks)}}
    for name in ("security", "pr_gate", "tests", "verification", "quality_gate"):
        c = rv_checks.get(name)
        if c is not None:
            st = c.get("status")
            items[f"validation.{name}"] = {"status": "pass" if st == "pass" else ("skip" if st == "skip" else "fail"),
                                           "detail": c.get("detail")}

    fp = _fingerprint(scope, project, target)
    items["build"] = {"status": "pass" if fp.get("build") else "fail",
                      "detail": {"build_id": fp.get("build_id"), "version": fp.get("version")}}
    items["packaging_bom"] = {"status": "pass" if fp.get("bom_present") else "fail",
                              "detail": {"deps": fp.get("bom_deps"), "licenses": fp.get("bom_licenses")}}
    items["deployment"] = _deployment(d)

    # integration must be green for a release (merge gate)
    try:
        from core import merge_gate
        mg = merge_gate.evaluate(project or scope, d)
        items["merge_gate"] = {"status": "pass" if mg.get("passed") else "fail",
                               "detail": {"unmet": mg.get("unmet", [])}}
    except Exception as e:
        items["merge_gate"] = {"status": "unknown", "detail": type(e).__name__}

    failed = sorted(k for k, v in items.items() if v.get("status") != "pass")
    can_release = not failed
    return {"ok": True, "scope": scope, "project": project, "target": target,
            "evaluated_at": datetime.now().isoformat(),
            "items": items, "unmet": failed, "can_release": can_release,
            "fingerprint": fp, "release_validation_run": release_validation.get("run_id"),
            "decision": "release" if can_release else "blocked"}


def readiness(scope: str = "product_forge", project: str = "", target: str = "",
              run_id: str = "") -> dict[str, Any]:
    """Release-readiness decision (public/lower-risk read)."""
    g = gate(scope, project, target=target, run_id=run_id)
    return {"can_release": g["can_release"], "unmet": g["unmet"], "decision": g["decision"],
            "fingerprint": g["fingerprint"], "evaluated_at": g["evaluated_at"]}


def _evidence_path() -> str:
    # product-forge evidence lives under engineering/; project evidence is stored next to the project
    return RELEASE_EVIDENCE


def record_evidence(g: dict[str, Any]) -> str:
    """Append release evidence (release decision + fingerprint) to the evidence log."""
    import json
    d = _scope_dir(g.get("scope", "product_forge"), g.get("project", ""))
    path = _evidence_path() if d == str(ROOT) else os.path.join(d, "release-evidence.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    row = {"at": g.get("evaluated_at") or datetime.now().isoformat(),
           "scope": g.get("scope"), "project": g.get("project"), "target": g.get("target"),
           "decision": g.get("decision"), "can_release": g.get("can_release"),
           "unmet": g.get("unmet"), "fingerprint": g.get("fingerprint"),
           "release_validation_run": g.get("release_validation_run")}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def list_evidence(limit: int = 50) -> list[dict[str, Any]]:
    import json
    out: list[dict[str, Any]] = []
    if not os.path.exists(RELEASE_EVIDENCE):
        return out
    with open(RELEASE_EVIDENCE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                with contextlib.suppress(Exception):
                    out.append(json.loads(line))
    return out[-limit:]
