"""BI-PF-1467: design-time guardrails - relevance selection + idempotent record."""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import design_guardrails as dg  # noqa: E402


def test_relevant_rules_ranks_by_item_tokens():
    rules = [
        {"id": "CL-001", "rule": "Reversibility and backup before any destructive step", "enforcement": "checklist"},
        {"id": "CL-002", "rule": "Colours and typography are irrelevant here", "enforcement": "docs"},
    ]
    picked = dg.relevant_rules("We drop old partitions and must have a verified backup", rules, limit=1)
    assert picked and picked[0]["id"] == "CL-001"


def test_render_includes_checklist_and_corrections():
    item = {"title": "Partition audit table", "objective": "drop old partitions safely with backup"}
    block = dg.render(item, "BI-X")
    assert "DESIGN GUARDRAILS" in block and "Checklist:" in block
    assert "CORRECTION-LEDGER" in block


def test_record_is_idempotent(monkeypatch):
    calls = []
    fake = types.SimpleNamespace(
        get_item=lambda i: {"evidence": []},
        set_context=lambda i, p: calls.append(p),
    )
    monkeypatch.setitem(sys.modules, "backlog_api", fake)
    assert dg._record("BI-X", "block") is True
    assert calls and any("Design guardrails applied (BI-X):" in e for e in calls[0]["evidence"])

    fake.get_item = lambda i: {"evidence": ["Design guardrails applied (BI-X): sig:abc (1 lines)"]}
    assert dg._record("BI-X", "block") is False
