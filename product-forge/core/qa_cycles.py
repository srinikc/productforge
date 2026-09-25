"""
QA-owned suite & cycle definitions.

QA (validate) defines the product's test suites (smoke/sanity/feature/nfr/packaging)
from the test-matrix categories for the product kind, and maps pipeline stages to
test cycles. Persists suites/cycles via the framework SuiteManager.
"""
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

_REPO = str(_PF_ROOT)


def _suite_manager():
    from core.test_framework_integration import _load
    return _load("suite_manager", "core/suite_manager.py").SuiteManager()


# stage id -> suite/cycle name
STAGE_CYCLES: Dict[str, str] = {
    "4-0": "feature", "4a": "feature", "4b": "feature", "4c": "feature",
    "4d": "feature", "4e": "feature", "4f": "feature",
    "5": "nfr", "6": "nfr", "7": "full",
    "9": "packaging", "11": "smoke",
}


def default_suites(kind: str) -> Dict[str, Any]:
    """Standard suites derived from the test-matrix for a product kind."""
    from core.test_matrix import load, categories_for_kind
    cats = categories_for_kind(kind, load())

    def pick(names):
        return [c for c in cats if c in names]

    return {
        "smoke": {"description": "Critical paths", "categories": pick({"unit", "api", "smoke"}) or ["unit"],
                  "tags": ["quick", "critical"]},
        "sanity": {"description": "Core functionality", "categories": pick({"unit", "api", "integration"}) or ["unit"],
                   "tags": ["core"]},
        "feature": {"description": "Feature suites for the phase", "categories": cats or ["unit"],
                    "tags": ["phase"]},
        "nfr": {"description": "Non-functional", "categories": pick(
            {"performance", "security", "accessibility", "reliability", "scalability", "compliance"}),
            "tags": ["nfr"]},
        "packaging": {"description": "Build/install/deploy", "categories": pick(
            {"install", "packaging", "cloud_infra"}), "tags": ["release"]},
    }


def ensure_suites(project: str, project_dir: str,
                  tech_stack: Optional[Dict] = None) -> Dict[str, Any]:
    """Ensure the project has QA-defined suites + cycle map (idempotent)."""
    from core.test_matrix import product_kind
    kind = product_kind(tech_stack or {})
    suites = default_suites(kind)
    try:
        sm = _suite_manager()
        sm.set_project_suites(project, suites)
    except Exception as e:
        print(f"[QACycles] suites: {e}")

    cycles = {name: {"suite": name, "stage_map": [s for s, c in STAGE_CYCLES.items() if c == name]}
              for name in suites}
    try:
        out_dir = os.path.join(_REPO, "test-framework", "results", project)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "cycles.json"), "w", encoding="utf-8") as f:
            json.dump({"project": project, "product_kind": kind, "suites": suites,
                       "cycles": cycles, "defined_at": datetime.now().isoformat()},
                      f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[QACycles] cycles: {e}")
    return {"product_kind": kind, "suites": suites, "cycles": cycles}


def cycle_for_stage(stage_id: str) -> str:
    return STAGE_CYCLES.get(str(stage_id), "feature")


def categories_for_suite(suite: str) -> List[str]:
    """Categories for a suite from the framework config (fallback: matrix)."""
    try:
        sm = _suite_manager()
        s = sm.get_suite(suite)
        if s and s.get("categories"):
            return list(s["categories"])
    except Exception:
        pass
    return []
