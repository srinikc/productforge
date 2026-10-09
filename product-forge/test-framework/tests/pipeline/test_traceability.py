"""BI-PF-1169 (E8): traceability single-writer merge + flag population + gate."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import traceability as tr  # noqa: E402
from scripts.dev import traceability_check as gate  # noqa: E402


def _project(tmp_path):
    pd = tmp_path / "proj"
    pd.mkdir()
    (pd / "product-plan.json").write_text(json.dumps(
        {"project": "proj", "modules": [{"features": [
            {"id": "F-1", "status": "implemented"}, {"id": "F-2", "status": "planned"}]}]}), encoding="utf-8")
    (pd / "traceability.json").write_text(json.dumps(
        {"project": "proj", "matrix": [
            {"requirement_id": "FR-1", "feature_id": "F-1"},
            {"requirement_id": "FR-2", "feature_id": "F-2"}]}), encoding="utf-8")
    return str(pd)


def test_merge_matrix_is_idempotent(tmp_path):
    pd = _project(tmp_path)
    tr.merge_matrix(pd, [{"requirement_id": "FR-1", "feature_id": "F-1"}])
    tr.merge_matrix(pd, [{"requirement_id": "FR-1", "feature_id": "F-1"}])   # dup
    data = json.loads((Path(pd) / "traceability.json").read_text(encoding="utf-8"))
    assert len(data["matrix"]) == 2                                          # no dup added


def test_populate_flags_from_plan_and_gate(tmp_path):
    pd = _project(tmp_path)
    tr.populate_flags(pd)
    data = json.loads((Path(pd) / "traceability.json").read_text(encoding="utf-8"))
    by_req = {r["requirement_id"]: r for r in data["matrix"]}
    assert by_req["FR-1"]["implemented"] is True          # F-1 implemented
    assert by_req["FR-2"]["implemented"] is False         # F-2 planned
    assert gate.evaluate(pd)["ok"] is False               # FR-2 untraced -> gate fails
