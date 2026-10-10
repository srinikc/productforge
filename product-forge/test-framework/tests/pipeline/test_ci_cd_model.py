"""BI-PF-1239: CI/CD + gates model (read-only projection) + the gate-registry drift guard."""
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_ROOT))

from core import ci_cd_model  # noqa: E402


def _guard_module():
    spec = importlib.util.spec_from_file_location("_ccg", str(_ROOT / "scripts" / "dev" / "ci_cd_gates_check.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_load_has_catalog():
    m = ci_cd_model.load()
    assert m["mechanical_gates"], "mechanical gates present"
    assert m["tiers"], "tiers present"
    assert m["pr_merge_gate"], "PR merge checklist present (from core/pr_gate)"
    assert m["owners"]["pr_merge_gate"].startswith("core/pr_gate")
    # every gate tier is a known tier
    assert set(m["gates_by_tier"]) <= set(m["tiers"])


def test_effective_product_forge():
    e = ci_cd_model.effective("product_forge")
    assert e["effective"] is True
    assert e["ci"] == "github-actions:structure"
    assert e["mechanical_gates"], "PF lists its mechanical gates"


def test_effective_project_not_built():
    e = ci_cd_model.effective("project", "no-such-project-xyz-1239")
    assert e["effective"] is False
    assert e["reason"] == "not_built"


def test_gates_catalog_has_pr_and_mechanical():
    g = ci_cd_model.gates("product_forge")
    assert g["catalog"] and g["pr_merge_gate"]


def test_registry_matches_precheck_gates():
    """Drift guard: config/ci-cd-gates.json must equal the projection of precheck._GATES."""
    mod = _guard_module()
    assert mod._norm(mod._read_config()) == mod._norm(mod.build())
