"""BI-PF-0420: parallel-safe validation - run-scoped records + isolation + concurrency cap."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import capacity, run_quality_gate as qg, validation_engine as ve  # noqa: E402

_QG = "quality-gate" + ".json"


def test_run_scoped_quality_gate_record(tmp_path):
    pd = str(tmp_path)
    qg.record_run(pd, "r1", {"passed": True, "mode": "item", "reasons": []})
    qg.record_run(pd, "r2", {"passed": False, "mode": "item", "reasons": ["compileall"]})
    assert qg.latest_run(pd, "r1")["passed"] is True
    assert qg.latest_run(pd, "r2")["passed"] is False
    assert (tmp_path / "validation" / "r1" / _QG).exists()
    assert qg.latest_run(pd, "missing") is None


def test_check_quality_gate_prefers_run_scoped(tmp_path):
    pd = str(tmp_path)
    qg.record(pd, {"passed": False, "mode": "item", "reasons": ["compileall"]})   # stale "latest"
    qg.record_run(pd, "r9", {"passed": True, "mode": "item", "reasons": []})       # this run passed
    assert ve._check_quality_gate(pd, "r9")["status"] == "pass"    # run-scoped wins
    assert ve._check_quality_gate(pd)["status"] == "fail"          # back-compat: falls back to latest


def test_validation_capacity_cap(monkeypatch):
    monkeypatch.setattr(capacity, "max_parallel_validations", lambda: 2)
    assert capacity.can_validate(1)["ok"] is True
    assert capacity.can_validate(2)["ok"] is False
    assert "validation slot" in capacity.can_validate(2)["reason"]


def test_active_validations_counts_only_validation_worktrees():
    class _V:
        def list_worktrees(self):
            return [{"branch": "validation/r1"}, {"branch": "wg/x"}, {"branch": "validation/r2"}]
    assert ve._active_validations(_V()) == 2
