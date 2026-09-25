"""Per-feature sectioned generation + validation gate (BI-0098).

Guards:
  * feature_outline() reads products/<p>/product-plan.json -> ["F-1: <name>", ...]
  * decide_strategy() forces "sectioned" for a per-feature agent with an outline
  * output_checklist fails a flat design doc (no per-feature sections)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core import agent_requirements as ar  # noqa: E402
from core.output_checklist import check as checklist_check  # noqa: E402


def _write_plan(products: Path, project: str, features):
    d = products / project
    d.mkdir(parents=True, exist_ok=True)
    (d / "product-plan.json").write_text(
        json.dumps({"modules": [{"id": "M-1", "name": "Core", "features": features}]}),
        encoding="utf-8")


def test_feature_outline_reads_product_plan(tmp_path):
    products = tmp_path / "products"
    _write_plan(products, "demo", [{"id": "F-1", "name": "Alpha"},
                                   {"id": "F-2", "name": "Beta"}])
    assert ar.feature_outline(str(products), "demo") == ["F-1: Alpha", "F-2: Beta"]


def test_feature_outline_empty_without_plan(tmp_path):
    assert ar.feature_outline(str(tmp_path / "products"), "missing") == []


def test_decide_strategy_sectioned_for_per_feature_agent(tmp_path):
    products = tmp_path / "products"
    _write_plan(products, "demo", [{"id": "F-1", "name": "Alpha"},
                                   {"id": "F-2", "name": "Beta"}])
    outline = ar.feature_outline(str(products), "demo")
    assert "design" in ar.per_feature_agents()
    assert ar.decide_strategy("design", feature_outline=outline) == "sectioned"


def test_flat_design_doc_fails_per_feature_gate(tmp_path):
    flat = tmp_path / "flat.md"
    flat.write_text("# Design\n## Functional Requirements\nFR-1 ...\n", encoding="utf-8")
    res = checklist_check("design", [str(flat)])
    assert "per_feature" in res["essential_missing"]
    assert res["ok"] is False


def test_per_feature_design_doc_passes_gate(tmp_path):
    doc = tmp_path / "pf.md"
    doc.write_text(
        "# Design\n## F-1: Alpha\n### Behaviour\n### Validation\n### Acceptance criteria\n"
        "## F-2: Beta\n### Behaviour\n### Validation\n### Acceptance criteria\n"
        "## Functional Requirements\nFR-1\n## Non-Functional Requirements\nNFR-1\n"
        "## User Stories\nUS-1\n## API Contracts\n", encoding="utf-8")
    res = checklist_check("design", [str(doc)])
    assert "per_feature" not in res["essential_missing"]
