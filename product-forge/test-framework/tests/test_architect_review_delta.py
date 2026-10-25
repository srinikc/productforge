"""Delta review: latest reviewed HEAD + prior context (BI-PF-1485)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import architect_review as ar  # noqa: E402
from review_sig import digest  # noqa: E402


def test_latest_review_head_and_prior_context(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "ROOT", tmp_path)
    d = tmp_path / "engineering" / "reviews"
    d.mkdir(parents=True)
    finding = "evidence base is self-referential"
    (d / "BI-PF-9000-old.json").write_text(json.dumps({
        "item": "BI-PF-9000", "mode": "diff", "at": "2026-01-01T00:00:00+00:00",
        "head_sha": "aaa", "sha": "old", "findings": {"BLOCKER": [], "MAJOR": [],
                                                       "MINOR": [], "NIT": [], "SUMMARY": []}}), encoding="utf-8")
    (d / "BI-PF-9000-new.json").write_text(json.dumps({
        "item": "BI-PF-9000", "mode": "diff", "at": "2026-01-02T00:00:00+00:00",
        "head_sha": "bbb", "sha": "new", "findings": {"BLOCKER": [], "MAJOR": [finding],
                                                       "MINOR": [], "NIT": [], "SUMMARY": []}}), encoding="utf-8")
    assert ar._latest_review_sha("BI-PF-9000", "diff") == "bbb"
    item = {"id": "BI-PF-9000", "review_dispositions": {"diff": {
        "sig:" + digest(finding): {"status": "ACTIONED", "note": "fixed"}}}}
    ctx = ar._prior_context(item, "BI-PF-9000", "diff")
    assert "Prior review" in ctx and "self-referential" in ctx and "ACTIONED" in ctx
