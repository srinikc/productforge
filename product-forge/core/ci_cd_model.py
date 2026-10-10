"""BI-PF-1239: read-only CI/CD + gates model (projection over existing owners).

ONE projection so the orchestrator/UI can render "what gates run when, who owns them, and the last verdict"
for Product Forge and for each generated product. This module defines **no engine and writes nothing** - it
composes existing owners only:

  * ``config/ci-cd-gates.json``      - DERIVED mechanical-gate registry (truth = precheck._GATES; see
                                       scripts/dev/ci_cd_gates_check.py)
  * ``core/pr_gate.CHECKLIST``        - the PR merge gate checklist
  * ``core/validation_engine``        - validation profiles + run-bound runs (last verdict/evidence)
  * ``core/test_matrix``              - test categories
  * ``core/engineering_flow``         - the requirement->deploy flow coverage
  * ``templates/ci/github-actions.yml``- the generated-product CI template

Served by ``api/routers/engineering.py`` (``GET /api/v1/engineering/ci-cd[/{scope}]``, ``/gates``).
"""
import json
import os
import time
from typing import Any, Dict, List, Optional

from core.paths import ROOT

_GATES_CFG = os.path.join(str(ROOT), "config", "ci-cd-gates.json")
_CI_TEMPLATE = os.path.join(str(ROOT), "templates", "ci", "github-actions.yml")
_PRODUCTS = os.path.join(str(ROOT), "products")

# owners of each concern in the model (pointers, not duplicated data)
OWNERS = {
    "mechanical_gates": "scripts/dev/precheck.py::_GATES (registry: config/ci-cd-gates.json)",
    "pr_merge_gate": "core/pr_gate.py::CHECKLIST",
    "validation_profiles": "core/validation_engine.py",
    "test_categories": "core/test_matrix.py",
    "engineering_flow": "core/engineering_flow.py",
    "ci": ".github/workflows/structure.yml",
    "product_ci_template": "templates/ci/github-actions.yml",
}

_CACHE: Dict[str, Any] = {"at": 0.0, "data": None}
_TTL = 10.0


def _rj(path: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def mechanical_gates() -> List[Dict[str, Any]]:
    return list(_rj(_GATES_CFG).get("gates") or [])


def tiers() -> Dict[str, str]:
    return dict(_rj(_GATES_CFG).get("tiers") or {})


def pr_checklist() -> List[str]:
    try:
        from core import pr_gate
        return list(pr_gate.CHECKLIST)
    except Exception:
        return []


def validation_profiles() -> Dict[str, Any]:
    try:
        from core import validation_engine
        return dict(validation_engine.profiles() or {})
    except Exception:
        return {}


def test_categories() -> List[str]:
    try:
        from core import test_matrix
        m = test_matrix.load() or {}
        cats = m.get("categories")
        if isinstance(cats, dict):
            return sorted(cats.keys())
        if isinstance(cats, list):
            return [str(c) for c in cats]
        return []
    except Exception:
        return []


def flow_coverage() -> Dict[str, Any]:
    try:
        from core import engineering_flow
        return dict(engineering_flow.coverage() or {})
    except Exception:
        return {}


def load() -> Dict[str, Any]:
    """The full CI/CD + gates model (catalog). Cached ~10s (read-only; configs rarely change)."""
    now = time.time()
    if _CACHE["data"] is not None and now - _CACHE["at"] < _TTL:
        return _CACHE["data"]
    gates = mechanical_gates()
    by_tier: Dict[str, int] = {}
    for g in gates:
        t = str(g.get("tier") or "?")
        by_tier[t] = by_tier.get(t, 0) + 1
    data = {
        "tiers": tiers(),
        "mechanical_gates": gates,
        "gates_by_tier": by_tier,
        "pr_merge_gate": pr_checklist(),
        "validation_profiles": validation_profiles(),
        "test_categories": test_categories(),
        "engineering_flow": flow_coverage(),
        "owners": OWNERS,
        "counts": {"mechanical_gates": len(gates), "pr_merge_gate": len(pr_checklist()),
                   "validation_profiles": len(validation_profiles())},
    }
    _CACHE["data"] = data
    _CACHE["at"] = now
    return data


def gates(scope: str = "product_forge", project: Optional[str] = None) -> Dict[str, Any]:
    """Gate catalog + the last run-bound verdict/evidence for a scope (read-only)."""
    last: List[Dict[str, Any]] = []
    try:
        from core import validation_engine
        runs = validation_engine.list_runs(scope, project or None)
        for r in (runs or [])[-5:]:
            last.append({"profile": r.get("profile"), "result": r.get("result"),
                         "target": r.get("target"), "at": r.get("at") or r.get("created_at"),
                         "run_id": r.get("run_id")})
    except Exception:
        last = []
    return {"scope": scope, "project": project or "", "catalog": mechanical_gates(),
            "pr_merge_gate": pr_checklist(), "last_runs": last}


def effective(scope: str = "product_forge", project: Optional[str] = None) -> Dict[str, Any]:
    """The effective pipeline for a scope: PF (this repo) or a generated product (its own repo/CI)."""
    s = str(scope or "product_forge").strip()
    p = str(project or "").strip()
    if s == "product_forge":
        return {"scope": "product_forge", "project": "", "effective": True,
                "mechanical_gates": [g.get("id") for g in mechanical_gates()],
                "pr_merge_gate": pr_checklist(),
                "validation_profiles": sorted(validation_profiles().keys()),
                "ci": "github-actions:structure",
                "release_tier": True, "owners": OWNERS}
    if s != "project":
        return {"scope": s, "project": p, "effective": False, "reason": "unknown scope"}
    if not p:
        return {"scope": "project", "project": "", "effective": False, "reason": "project required"}
    proj_dir = os.path.join(_PRODUCTS, p)
    exists = os.path.isdir(proj_dir)
    ci_installed = os.path.isfile(os.path.join(proj_dir, ".github", "workflows", "product-forge.yml"))
    if not exists:
        return {"scope": "project", "project": p, "effective": False, "reason": "not_built"}
    return {"scope": "project", "project": p, "effective": True,
            "repo": f"products/{p}",
            "ci_template": "templates/ci/github-actions.yml",
            "ci_installed": ci_installed,
            "validation_profiles": sorted(validation_profiles().keys()),
            "test_categories": test_categories(),
            "owners": OWNERS}
