"""BI-PF-1468: grooming auto-applies the design guardrails (prompt injection + idempotent marker)."""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_grooming_guardrails"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_single_prompt_injects_design_guardrails():
    item = {"id": "BI-X", "title": "Drop old partitions", "body": "needs a verified backup"}
    prompt = grooming._ai_prompt(item, {"deps": [], "similar": []})
    assert "DESIGN GUARDRAILS" in prompt
    assert "CORRECTION-LEDGER" in prompt


def test_batch_prompt_injects_design_guardrails():
    items = [({"id": "BI-X", "title": "Drop old partitions", "body": "backup"}, {})]
    prompt = grooming._ai_prompt_batch(items)
    assert "DESIGN GUARDRAILS" in prompt
    assert "Apply this checklist to EACH item" in prompt


def test_groom_records_guardrails_marker_once():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Add login API", body="x", tag="TST")["id"]
        grooming.groom("project", _PROJ, iid, mode="deterministic")

        def marks():
            ev = backlog.get("project", _PROJ, iid).get("evidence") or []
            return [e for e in ev if str(e).startswith(f"Design guardrails applied ({iid}):")]

        assert len(marks()) == 1
        grooming.groom("project", _PROJ, iid, mode="deterministic")
        assert len(marks()) == 1
    finally:
        _clean()


def test_design_and_coding_are_separate_blocks():
    from core import design_guardrails as dg
    d = dg.render({"title": "x"}, "BI-X", stage="design")
    c = dg.render({"title": "x"}, "BI-X", stage="diff")
    assert "DESIGN GUARDRAILS" in d and "BI-PF" not in d.splitlines()[0]
    assert "CODING GUARDRAILS" in c
    assert dg.marker("BI-X", "implementation") != dg.marker("BI-X", "design")


def test_stage_filter_keeps_legacy_and_matching_modes(monkeypatch, tmp_path):
    from core import design_guardrails as dg
    p = tmp_path / "review-findings.json"
    p.write_text(json.dumps({"recurring": [
        {"sig": "a", "count": 2, "severity": "MAJOR", "text": "design-only", "modes": ["design"]},
        {"sig": "b", "count": 2, "severity": "MAJOR", "text": "code-only", "modes": ["diff"]},
        {"sig": "c", "count": 2, "severity": "MAJOR", "text": "legacy-no-modes"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(dg, "LEARNINGS", p)
    assert [r["text"] for r in dg.recurring(stage="design")] == ["design-only", "legacy-no-modes"]
    assert [r["text"] for r in dg.recurring(stage="diff")] == ["code-only", "legacy-no-modes"]


def test_worker_objective_gets_coding_guardrails():
    from core import worker
    task = {"task_id": "T-1", "title": "Drop old partitions", "objective": "Implement the change",
            "acceptance_criteria": ["verified backup before drop"]}
    objective, sig = worker.coding_guardrails_objective(task, "Implement the change")
    assert "CODING GUARDRAILS" in objective and objective.startswith("Implement the change")
    assert len(sig) == 16

