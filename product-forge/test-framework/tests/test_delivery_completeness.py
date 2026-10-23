"""Delivery-completeness gate tests (BI-PF-1409)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import delivery_completeness_check as d  # noqa: E402


def _item(acs, ver, **over):
    it = {"id": "BI-TEST", "title": "A title", "objective": "An objective",
          "acceptance_criteria": acs, "verification": ver}
    it.update(over)
    return it


def test_placeholder_detection():
    it = _item(["Objective achieved: An objective"], ["An objective"])
    assert all(d.placeholder(a, it) for a in it["acceptance_criteria"])
    assert d.placeholder("Not specified.", it)
    assert not d.placeholder("Concrete acceptance criterion with detail", it)


def test_good_item_passes():
    it = _item(["Concrete acceptance criterion with detail"], ["Verified by an independent test run"])
    assert d.transition_problems(it) == []


def test_placeholder_item_fails():
    it = _item(["An objective"], ["An objective"])
    assert len(d.transition_problems(it)) == 2


def test_rcca_required_and_validated():
    item = _item(["Concrete acceptance criterion with detail"], ["Verified by an independent test run"],
                 title="RCCA incident")
    assert "rcca.root_cause missing/short" in " ".join(d.transition_problems(item))
    good = {"rcca": {"root_cause": "x" * 20, "corrective": "y" * 20, "preventive": "z" * 20,
                     "fixed_where": "scripts/dev/delivery_completeness_check.py"}}
    assert d.rcca_problems(good) == []


def test_baseline_shape():
    items, bad = d.load_baseline()
    assert isinstance(items, list) and isinstance(bad, list)


def test_audit_returns_lists():
    remaining, bad = d.audit()
    assert isinstance(remaining, list) and isinstance(bad, list)
