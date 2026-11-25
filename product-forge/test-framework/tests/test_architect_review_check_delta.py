"""Gate 2.5 accepts a full review followed by a delta fix review."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import architect_review as ar  # noqa: E402
import architect_review_check as c  # noqa: E402


def _review(path: Path, **kw):
    path.with_suffix("." + "json").write_text(json.dumps(kw), encoding="utf-8")


def test_delta_after_full_is_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "EVID", tmp_path)
    monkeypatch.setattr(c, "_baseline_shas", lambda: set())
    monkeypatch.setattr(ar, "changed_files", lambda base="": ["core/x.py"])
    monkeypatch.setattr(ar, "has_review_changes", lambda base="": True)
    monkeypatch.setattr(ar, "diff_sha", lambda base="": "currentsha")
    monkeypatch.setattr(ar, "_merge_base", lambda: "b0")
    monkeypatch.setattr(c, "_is_ancestor", lambda base, head: True)
    monkeypatch.setattr(ar, "_is_ancestor", lambda base, head: True)
    monkeypatch.setattr(ar, "_git_text", lambda args, timeout=30: "h2")
    _review(tmp_path / "BI-PF-X-fullsha", item="BI-PF-X", mode="diff", sha="fullsha",
            review_scope="full_candidate", head_sha="h1", base_sha="",
            findings={"BLOCKER": [], "MAJOR": [], "MINOR": [], "NIT": []})
    _review(tmp_path / "BI-PF-X-deltasha", item="BI-PF-X", mode="diff", sha="deltasha",
            review_scope="delta", base_sha="h1", head_sha="h2",
            findings={"BLOCKER": [], "MAJOR": [], "MINOR": [], "NIT": []})
    assert c.main() == 0


def test_delta_without_full_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "EVID", tmp_path)
    monkeypatch.setattr(c, "_baseline_shas", lambda: set())
    monkeypatch.setattr(ar, "changed_files", lambda base="": ["core/x.py"])
    monkeypatch.setattr(ar, "has_review_changes", lambda base="": True)
    monkeypatch.setattr(ar, "diff_sha", lambda base="": "currentsha")
    monkeypatch.setattr(ar, "_merge_base", lambda: "b0")
    monkeypatch.setattr(c, "_is_ancestor", lambda base, head: True)
    monkeypatch.setattr(ar, "_is_ancestor", lambda base, head: True)
    monkeypatch.setattr(ar, "_git_text", lambda args, timeout=30: "h2")
    _review(tmp_path / "BI-PF-X-deltasha", item="BI-PF-X", mode="diff", sha="deltasha",
            review_scope="delta", base_sha="h1", head_sha="h2",
            findings={"BLOCKER": [], "MAJOR": [], "MINOR": [], "NIT": []})
    assert c.main() == 1
