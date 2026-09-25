"""Dashboard + API blueprint (BI-0092).

A reusable, instantiable blueprint for the Product Forge dashboard/api, instantiated
for Product Forge ITSELF and for every pipeline-created project. Single source of truth
for the blueprint: config/dashboard-blueprint.json. Instantiation writes a per-target
blueprint descriptor the dashboard/api can consume.
"""
from __future__ import annotations
import json, os
from datetime import datetime
from typing import Any, Dict, List

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
