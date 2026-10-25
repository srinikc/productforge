"""One review per mode; HIL material-change exception (BI-PF-1485)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import review_budget as rb  # noqa: E402


def _setup(tmp_path, monkeypatch, n=2):
    monkeypatch.setattr(rb, "REVIEWS", tmp_path)
    for i in range(n):
        (tmp_path / f"BI-PF-9000-{i}.json").write_text(json.dumps({
            "item": "BI-PF-9000", "mode": "diff", "at": "2026-10-25T01:00:00+00:00", "sha": str(i)}), encoding="utf-8")


def test_budget_and_material_change(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, 2)
    cfg = tmp_path / "budget.json"
    cfg.write_text(json.dumps({"enforce_from": "2026-10-25", "max_reviews_per_mode": 1,
                               "allow_hil_material_change": True, "grandfather": []}), encoding="utf-8")
    monkeypatch.setattr(rb, "CFG", cfg)
    item = {"id": "BI-PF-9000", "decisions": []}
    assert rb.problems(item)
    item["decisions"] = [{"decision": "MATERIAL_CHANGE", "hil_confirmed": True, "mode": "diff"}]
    assert rb.problems(item) == []
