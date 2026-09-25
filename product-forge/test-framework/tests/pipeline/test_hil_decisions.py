"""
Regression for BI-0093: the full HIL approval decision model.

_check_approval_status must surface every decision status, and the back-compat
_wait_for_approval() must return True ONLY for approved / approved_with_conditions.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.pipeline_executor import PipelineExecutor  # noqa: E402


ALL_DECISIONS = [
    "approved", "approved_with_conditions", "changes", "regenerate",
    "skip", "rejected", "abort", "expired",
]


def _make_executor(tmp_path):
    ex = PipelineExecutor.__new__(PipelineExecutor)  # bypass __init__
    ex.project_dir = str(tmp_path)
    ex.project = "TestProj"
    ex.approval_mode = "interactive"
    ex.auto_approve = False
    ex.execution = None
    ex.pipeline_start_time = 0
    ex.decision_log = []
    ex.pending_approvals = []
    # Keep the pre-written approval file: do not overwrite it with a fresh pending request.
    ex._create_approval_request = lambda *a, **k: {"review_instructions": "n/a"}
    return ex


def _write_request(tmp_path, stage_id, agent_id, payload):
    d = tmp_path / "approvals" / stage_id
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{agent_id}-approval.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")


def test_check_approval_status_returns_each_status(tmp_path):
    ex = _make_executor(tmp_path)
    for status in ALL_DECISIONS:
        _write_request(tmp_path, "1", "design", {"status": status})
        assert ex._check_approval_status("design", "1") == status


def test_check_approval_status_missing_request(tmp_path):
    ex = _make_executor(tmp_path)
    assert ex._check_approval_status("design", "1") == "no_request"


def test_wait_for_approval_true_only_for_approved_states(tmp_path):
    for status in ALL_DECISIONS:
        ex = _make_executor(tmp_path)
        _write_request(tmp_path, "1", "design",
                       {"status": status, "notes": "n", "conditions": "c"})
        result = ex._wait_for_approval("design", "1", [])
        if status in ("approved", "approved_with_conditions"):
            assert result is True, status
        else:
            assert result is False, status


def test_wait_for_approval_ex_returns_decision_notes_conditions(tmp_path):
    ex = _make_executor(tmp_path)
    _write_request(tmp_path, "1", "design", {
        "status": "approved_with_conditions",
        "notes": "tweak X",
        "conditions": "no Prometheus /metrics",
    })
    res = ex._wait_for_approval_ex("design", "1", [])
    assert res["decision"] == "approved_with_conditions"
    assert res["conditions"] == "no Prometheus /metrics"
    assert res["notes"] == "tweak X"

    ex2 = _make_executor(tmp_path)
    _write_request(tmp_path, "1", "design", {"status": "changes", "notes": "drop voice"})
    res2 = ex2._wait_for_approval_ex("design", "1", [])
    assert res2["decision"] == "changes"
    assert res2["notes"] == "drop voice"
    assert res2["conditions"] == ""


def test_auto_approve_short_circuits_without_request(tmp_path):
    ex = _make_executor(tmp_path)
    ex.auto_approve = True
    assert ex._wait_for_approval("design", "1", []) is True
