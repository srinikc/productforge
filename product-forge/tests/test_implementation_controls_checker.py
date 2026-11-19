import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import implementation_readiness_check as irc


def _row(**kw):
    row = {"id": "C-1", "ac": "AC-1", "kind": "happy", "control": "append event",
           "symbol": "scripts/dev/implementation_readiness_check.py:problems",
           "positive_test": "tests/test_implementation_controls_checker.py",
           "negative_test": "tests/test_implementation_controls_checker.py",
           "tenant_test": "N/A: process tooling",
           "concurrency_test": "N/A: stateless",
           "observability": "JSON problems", "evidence": "pytest -q tests/test_implementation_controls_checker.py"}
    row.update(kw)
    return row


def _full_rows():
    rows = [_row()]
    for kind in ("security", "failure", "config", "observability"):
        rows.append(_row(id="C-" + kind, kind=kind))
    return rows


def _item(rows):
    return {"acceptance_criteria": ["AC-1"], "design_pack": {"tooling": True, "implementation_controls": rows,
            "tech_stack_evidence": [c["id"] for c in json.loads((ROOT / "config" / "implementation-controls.json").read_text(encoding="utf-8"))["checks"]]}}


def test_checker_accepts_complete_matrix():
    assert irc.problems(_item(_full_rows())) == []


def test_checker_rejects_missing_matrix():
    assert "design_pack.implementation_controls missing or empty" in irc.problems(
        {"acceptance_criteria": ["AC-1"], "design_pack": {"tooling": True}})


def test_all_problems_rejects_missing_design_pack():
    bad, checked = irc.all_problems([{"id": "x", "created_at": "2026-11-18T00:00:00"}], cutoff="2026-11-16")
    assert checked == 0 and any("no enforced items" in p for p in bad)


def test_all_problems_requires_tooling_controls():
    item = {"id": "x", "created_at": "2026-11-18T00:00:00", "design_pack": {"tooling": True}}
    bad, checked = irc.all_problems([item], cutoff="2026-11-16")
    assert checked == 1 and any("implementation_controls missing" in p for p in bad)


def test_tech_stack_evidence_keys_resolve():
    cfg = json.loads((ROOT / "config" / "implementation-controls.json").read_text(encoding="utf-8"))
    assert cfg["checks"]
