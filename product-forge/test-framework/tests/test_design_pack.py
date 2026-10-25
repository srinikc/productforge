"""Design pack check/render (BI-PF-1484)."""
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import design_pack as d  # noqa: E402


def _item():
    return {"id": "BI-PF-9999", "title": "T", "status": "in_progress",
            "acceptance_criteria": ["a", "b"],
            "design_pack": {"version": 1, "requirements": ["a"], "invariants": ["i"],
                            "contracts": {"api": [], "db": [], "files": [], "config": []},
                            "failure_matrix": [{"case": "x", "expected": "block", "code": "E"}],
                            "dependencies": ["d"], "security": ["s"], "observability": ["o"],
                            "performance": ["p"], "test_matrix": [
                                {"ac": "AC-1", "kind": "unit", "test": "t1"},
                                {"ac": "AC-2", "kind": "api", "test": "t2"}],
                            "rollout": "warn", "rollback": "revert", "decisions": ["use design pack"]}}


def test_check_ok():
    assert d.check(_item()) == []


def test_missing_pack_and_ac_mapping():
    it = _item(); it["design_pack"] = {}
    assert "design_pack missing" in d.check(it)
    it = _item(); it["design_pack"]["test_matrix"] = []
    assert any("AC-1" in x for x in d.check(it))


def test_render_contains_sections(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "DESIGN_DIR", tmp_path)
    out = tmp_path / "BI-PF-9999.md"
    out.write_text(d.render(_item()), encoding="utf-8")
    s = out.read_text(encoding="utf-8")
    assert "## 3. Logic invariants" in s and "| AC-1" in s and "BI-PF-9999" in s


def test_should_enforce_by_item_and_date():
    cfg = {"enforce_from": "2026-10-26", "enforce_items": ["BI-PF-1484"]}
    assert d.should_enforce({"id": "BI-PF-1484", "created_at": "2026-10-01"}, cfg)
    assert d.should_enforce({"id": "BI-PF-9", "created_at": "2026-10-27"}, cfg)
    assert not d.should_enforce({"id": "BI-PF-9", "created_at": "2026-10-01"}, cfg)


def test_all_with_item_is_rejected():
    assert d.main(["--all", "--item", "BI-PF-9999", "--check"]) == 2


def test_evaluate_unknown_item_fails_closed(monkeypatch):
    monkeypatch.setattr(d.backlog, "get_epic", lambda *a, **k: None)
    assert d.evaluate("BI-PF-NOPE") == ["item not found: BI-PF-NOPE"]


def test_evaluate_flags_invalid_and_missing_created_at(monkeypatch):
    item = {"id": "BI-PF-9999", "status": "in_progress", "created_at": "2026/10/05"}
    monkeypatch.setattr(d.backlog, "get_epic", lambda *a, **k: item)
    assert any("created_at invalid" in p for p in d.evaluate("BI-PF-9999"))
    item["created_at"] = ""
    assert "created_at missing" in d.evaluate("BI-PF-9999")
    item["created_at"] = "2026-10-05T25"
    assert any("created_at invalid" in p for p in d.evaluate("BI-PF-9999"))
    item["created_at"] = "2026-10-05 "
    assert any("created_at invalid" in p for p in d.evaluate("BI-PF-9999"))


def test_evaluate_validates_config_once(monkeypatch, tmp_path):
    cfg = tmp_path / f"cfg-{uuid4().hex}.json"
    cfg.write_text('{"enforce_items": []}', encoding="utf-8")
    monkeypatch.setattr(d, "CFG", cfg)
    monkeypatch.setattr(d.backlog, "get_epic", lambda *a, **k: {"id": "BI-PF-9", "status": "new"})
    assert "enforce_from missing" in d.evaluate("BI-PF-9")


def test_parse_date_accepts_date_and_datetime():
    assert d._parse_date("2026-10-05").isoformat() == "2026-10-05"
    assert d._parse_date("2026-10-05T10:20:30").isoformat() == "2026-10-05"
