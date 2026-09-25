"""Deterministic per-feature validation gate.

`output_checklist.check()` must FAIL a per-feature agent artifact whose headings
carry no per-feature (F-<n>) sections, and must not flag a doc that has them.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.output_checklist import check as checklist_check  # noqa: E402


def test_flat_doc_fails_per_feature_gate(tmp_path):
    flat = tmp_path / "flat.md"
    flat.write_text("# Design\n## Screens\n## Flows\n", encoding="utf-8")
    res = checklist_check("design", [str(flat)])
    assert res["ok"] is False
    assert "per_feature" in res["essential_missing"]


def test_per_feature_doc_has_no_per_feature_missing(tmp_path):
    doc = tmp_path / "pf.md"
    doc.write_text("# Design\n## F-1: X\n## F-2: Y\n", encoding="utf-8")
    res = checklist_check("design", [str(doc)])
    assert "per_feature" not in res["essential_missing"]
