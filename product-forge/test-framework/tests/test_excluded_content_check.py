"""Excluded paths must contain only generated/evidence content (BI-PF-1485)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import excluded_content_check as ec  # noqa: E402


def test_review_and_trail_schemas(tmp_path, monkeypatch):
    monkeypatch.setattr(ec, "ROOT", tmp_path)
    d = tmp_path / "engineering" / "reviews"
    d.mkdir(parents=True)
    item, good, bad_sha = "BI-PF-1", "a", "b"
    (d / f"{item}-{good}.json").write_text(json.dumps({"item": item, "sha": good, "mode": "diff",
                                                       "findings": {}}), encoding="utf-8")
    assert ec.problems([f"engineering/reviews/{item}-{good}.json"]) == []
    (d / f"{item}-{bad_sha}.json").write_text("not json", encoding="utf-8")
    assert ec.problems([f"engineering/reviews/{item}-{bad_sha}.json"])


def test_design_header_and_hidden_code(tmp_path, monkeypatch):
    monkeypatch.setattr(ec, "ROOT", tmp_path)
    item = "BI-PF-1"
    p = tmp_path / "engineering" / "design" / f"{item}.md"
    p.parent.mkdir(parents=True)
    p.write_text(f"# Design Pack - {item}\n## 1. Requirements\n## 3. Logic invariants\n", encoding="utf-8")
    assert ec.problems([f"engineering/design/{item}.md"]) == []
    p.write_text("def hidden():\n    pass\n", encoding="utf-8")
    assert ec.problems([f"engineering/design/{item}.md"])

def test_derived_docs_reject_injected_script(tmp_path, monkeypatch):
    monkeypatch.setattr(ec, "ROOT", tmp_path)
    d = tmp_path / "docs"; d.mkdir()
    (d / "BACKLOG-SUMMARY.md").write_text("# Backlog Summary\n", encoding="utf-8")
    assert ec.problems(["docs/BACKLOG-SUMMARY.md"]) == []
    (d / "documentation-index.html").write_text("<!DOCTYPE html><html><script>alert(1)</script></html>", encoding="utf-8")
    assert ec.problems(["docs/documentation-index.html"])
