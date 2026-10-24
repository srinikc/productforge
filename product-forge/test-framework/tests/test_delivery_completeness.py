"""Delivery-completeness gate tests (BI-PF-1409)."""
import sys
from pathlib import Path

import pytest

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


def test_load_resolves_repo_root_relative_paths(tmp_path, monkeypatch):
    item = tmp_path / "product-forge" / "data" / "backlog" / "items" / "BI-TEST-X.json"
    item.parent.mkdir(parents=True)
    item.write_text('{"id": "BI-TEST-X", "status": "completed"}', encoding="utf-8")
    monkeypatch.setattr(d, "_repo_root", lambda: str(tmp_path))
    got = d._load("product-forge/data/backlog/items/BI-TEST-X.json")
    assert got.get("id") == "BI-TEST-X"


def test_load_skips_deleted_and_rejects_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "_repo_root", lambda: str(tmp_path))
    assert d._load("product-forge/data/backlog/items/BI-TEST-MISSING.json") is None
    with pytest.raises(RuntimeError, match="escapes the repo root"):
        d._load("../../BI-TEST-OUTSIDE.json")


def test_load_fails_closed_on_malformed_item(tmp_path, monkeypatch):
    item = tmp_path / "product-forge" / "data" / "backlog" / "items" / "BI-TEST-BAD.json"
    item.parent.mkdir(parents=True)
    item.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(d, "_repo_root", lambda: str(tmp_path))
    with pytest.raises(RuntimeError, match="BI-TEST-BAD.json"):
        d._load("product-forge/data/backlog/items/BI-TEST-BAD.json")


def test_load_fails_closed_on_non_object(tmp_path, monkeypatch):
    item = tmp_path / "product-forge" / "data" / "backlog" / "items" / "BI-TEST-ARR.json"
    item.parent.mkdir(parents=True)
    item.write_text("[1, 2]", encoding="utf-8")
    monkeypatch.setattr(d, "_repo_root", lambda: str(tmp_path))
    with pytest.raises(RuntimeError, match="not a JSON object"):
        d._load("product-forge/data/backlog/items/BI-TEST-ARR.json")


def test_transitions_uses_repo_root(tmp_path, monkeypatch):
    rel = "product-forge/data/backlog/items/BI-TEST-X.json"
    item = tmp_path / rel
    item.parent.mkdir(parents=True)
    item.write_text('{"id": "BI-TEST-X", "status": "completed"}', encoding="utf-8")

    def fake_git(*args, **kwargs):
        if args and args[0] == "diff":
            return rel
        if args and args[0] == "show":
            return '{"id": "BI-TEST-X", "status": "in_progress"}'
        return ""

    monkeypatch.setattr(d, "_repo_root", lambda: str(tmp_path))
    monkeypatch.setattr(d, "_git", fake_git)
    got = d.transitions("base-sha")
    assert [x["id"] for x in got] == ["BI-TEST-X"]
