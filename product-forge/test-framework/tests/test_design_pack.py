"""Design pack check/render (BI-PF-1484)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import design_pack as d  # noqa: E402


def _item():
    return {"id": "BI-PF-9999", "title": "T", "status": "in_progress",
            "acceptance_criteria": ["a", "b"],
            "design_pack": {"version": 1, "requirements": ["a"], "invariants": ["i"],
                            "contracts": {"api": [], "db": [], "files": [], "config": []},
                            "failure_matrix": [{"case": "x", "expected": "block", "code": "E"}],
                            "dependencies": ["d"], "test_matrix": [
                                {"ac": "AC-1", "kind": "unit", "test": "t1"},
                                {"ac": "AC-2", "kind": "api", "test": "t2"}],
                            "rollout": "warn", "rollback": "revert", "decisions": []}}


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
