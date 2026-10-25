"""Delta review: latest reviewed HEAD + prior context (BI-PF-1485)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import architect_review as ar  # noqa: E402
import architect_review_check as arc  # noqa: E402
from review_sig import digest  # noqa: E402


def test_latest_review_head_and_prior_context(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "ROOT", tmp_path)
    d = tmp_path / "engineering" / "reviews"
    d.mkdir(parents=True)
    finding = "evidence base is self-referential"
    (d / f"BI-PF-9000-{1}.json").write_text(json.dumps({
        "item": "BI-PF-9000", "mode": "diff", "at": "2026-01-01T00:00:00+00:00",
        "head_sha": "aaa", "sha": "old", "findings": {"BLOCKER": [], "MAJOR": [],
                                                       "MINOR": [], "NIT": [], "SUMMARY": []}}), encoding="utf-8")
    (d / f"BI-PF-9000-{2}.json").write_text(json.dumps({
        "item": "BI-PF-9000", "mode": "diff", "at": "2026-01-02T00:00:00+00:00",
        "head_sha": "bbb", "sha": "new", "findings": {"BLOCKER": [], "MAJOR": [finding],
                                                       "MINOR": [], "NIT": [], "SUMMARY": []}}), encoding="utf-8")
    assert ar._latest_review_sha("BI-PF-9000", "diff") == "bbb"
    item = {"id": "BI-PF-9000", "review_dispositions": {"diff": {
        "sig:" + digest(finding): {"status": "ACTIONED", "note": "fixed"}}}}
    ctx = ar._prior_context(item, "BI-PF-9000", "diff")
    assert "Prior review" in ctx and "self-referential" in ctx and "ACTIONED" in ctx

def test_valid_base_rejects_self_and_cross_item(monkeypatch):
    monkeypatch.setattr(arc, "_is_ancestor", lambda b, h: True)
    assert not arc.valid_base("abc", "abc", {"abc"}, "mb")
    assert not arc.valid_base("zzz", "head", {"aaa"}, "mb")
    assert arc.valid_base("aaa", "head", {"aaa"}, "mb")


def test_valid_base_requires_ancestry(monkeypatch):
    monkeypatch.setattr(arc, "_is_ancestor", lambda b, h: False)
    assert not arc.valid_base("aaa", "head", {"aaa"}, "mb")

def test_parse_review_ignores_none_placeholders():
    text = "### BLOCKER\n- none\n### MAJOR\n- real\n### MINOR\n- none\n### NIT\n- none\n### SUMMARY\n- ok\n"
    out = ar.parse_review(text)
    assert out["BLOCKER"] == [] and out["MAJOR"] == ["real"] and out["MINOR"] == []
