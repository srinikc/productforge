"""BI-PF-0463: backlog context gate rejects auto-draft placeholders (authorship, not just presence)."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

_spec = importlib.util.spec_from_file_location("bcc", ROOT / "scripts" / "dev" / "backlog_context_check.py")
bcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bcc)

from core import backlog as B  # noqa: E402


def _item(**kw):
    base = {"id": "BI-X", "type": "feature",
            "brief": {"problem": "p", "what_adds": "w", "source": "authored"},
            "objective": "o", "acceptance_criteria": ["a"], "in_scope": ["s"], "out_of_scope": ["n"],
            "affected_components": ["c"], "affected_files": ["f"], "approach": "a", "verification": ["v"],
            "risks": ["r"], "rollback": "rb", "evidence": ["e"], "owner": "agent", "requester": "user",
            "due": "2026", "target_release": "v1", "review": {"reconciliation": {}}}
    base.update(kw)
    return base


def test_clean_item_passes():
    it = _item()
    assert bcc._problems_for("product_forge", None, [it], [it]) == []


def test_placeholder_approach_rejected():
    it = _item(approach="(derived) TBD")
    probs = bcc._problems_for("product_forge", None, [it], [it])
    assert any("auto-draft placeholder" in p for p in probs)


def test_placeholder_verification_rejected():
    it = _item(verification=["(derived) objective met: x"])
    probs = bcc._problems_for("product_forge", None, [it], [it])
    assert any("auto-draft placeholder" in p for p in probs)


def test_real_backlog_has_no_residue():
    items = B.list_open("product_forge", None)
    allitems = items + B.list_closed("product_forge", None)
    assert bcc._problems_for("product_forge", None, items, allitems) == []
