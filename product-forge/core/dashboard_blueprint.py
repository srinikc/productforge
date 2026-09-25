"""Dashboard + API blueprint (BI-0092).

A reusable, instantiable blueprint for the Product Forge dashboard/api, instantiated
for Product Forge ITSELF and for every pipeline-created project. Single source of truth
for the blueprint: config/dashboard-blueprint.json. Instantiation writes a per-target
blueprint descriptor the dashboard/api can consume.
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

import json, os
from datetime import datetime
from typing import Any, Dict, List

REPO = str(_PF_ROOT)
BP = os.path.join(REPO, "config", "dashboard-blueprint.json")

DEFAULT = {
    "_doc": "Reusable dashboard+API blueprint (BI-0092). Instantiated for Product Forge and every pipeline project.",
    "version": 1,
    "surfaces": [
        "portfolio", "project-overview", "run-monitor", "agent-registry", "config-editor",
        "backlog", "model-tiers", "hil-console", "discovery-panel", "reports",
        "licensing", "analytics", "knowledge-skills",
    ],
    "api_base": "/api/v1",
    "auth": "bearer",
    "theme_tokens": "docs/uiux-theme.md",
}


def load_blueprint() -> Dict:
    try:
        with open(BP, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        os.makedirs(os.path.dirname(BP), exist_ok=True)
        with open(BP, "w", encoding="utf-8", newline="\n") as f:
            json.dump(DEFAULT, f, indent=2, ensure_ascii=False)
        return DEFAULT


def instantiate(target: str, kind: str = "project", project_dir: str = "") -> Dict:
    """Instantiate the blueprint for a target (Product Forge itself, or a project)."""
    bp = load_blueprint()
    inst = {"target": target, "kind": kind, "instantiated_at": datetime.now().isoformat(),
            "blueprint_version": bp.get("version"), "surfaces": bp.get("surfaces"),
            "api_base": bp.get("api_base"), "auth": bp.get("auth")}
    if project_dir:
        os.makedirs(project_dir, exist_ok=True)
        p = os.path.join(project_dir, "dashboard-blueprint.json")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(inst, f, indent=2, ensure_ascii=False)
        inst["path"] = p
    return inst


def surfaces() -> List[str]:
    return load_blueprint().get("surfaces", [])


if __name__ == "__main__":
    print(json.dumps(load_blueprint(), indent=2))
