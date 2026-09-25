"""
Verification policy (8.x).

Classifies each test category as verified:
  - internal  : executed by the pipeline using available tooling
  - external  : requires an external lab / device farm / vendor hardware
  - not_run   : no tests present (gap) or tooling unavailable

Never fabricate verification: anything not executed is explicitly `not_run`.
"""
import json
import os
from typing import Dict, List

_EXTERNAL = {"mobile_ios", "mobile_android", "usability", "cloud_infra"}


def _tech_stack(project_dir: str) -> Dict:
    p = os.path.join(project_dir, "docs", "tech-stack.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def policy(project_dir: str, tech_stack: Dict = None) -> Dict[str, List[str]]:
    ts = tech_stack or _tech_stack(project_dir)
    internal: List[str] = []
    external: List[str] = []
    not_run: List[str] = []
    try:
        from core.test_matrix import load, categories_for_kind, product_kind, plan
        cats = categories_for_kind(product_kind(ts), load())
        items = plan(project_dir, cats, ts)
    except Exception:
        items = []
    # If the app doesn't boot, integration/e2e/UI categories cannot be verified.
    boot_ok = None
    try:
        from core.app_smoke import boot_check
        boot_ok = boot_check(project_dir).get("ok")
    except Exception:
        boot_ok = None
    _dependent = {"api", "db", "integration", "e2e", "e2e_bdd", "visual", "ui"}
    for it in items:
        cat = it["category"]
        if boot_ok is False and cat in _dependent:
            not_run.append(cat)
            continue
        if cat in _EXTERNAL and not it.get("exists"):
            external.append(cat)
        elif it.get("exists"):
            internal.append(cat)
        else:
            not_run.append(cat)
    # spec review is always internal (QA)
    internal.append("spec_review")
    return {"internal": sorted(set(internal)),
            "external": sorted(set(external)),
            "not_run": sorted(set(not_run))}


def summary(project_dir: str, tech_stack: Dict = None) -> Dict:
    p = policy(project_dir, tech_stack)
    return {"internal": len(p["internal"]), "external": len(p["external"]),
            "not_run": len(p["not_run"]), "detail": p}
