"""F0-3 (M0.3): run-bound provenance — manifest + stale-approval rejection."""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import run_manifest as rm  # noqa: E402
from core.pipeline_executor import PipelineExecutor  # noqa: E402


def test_run_manifest_artifact_roundtrip(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("hello", encoding="utf-8")
    rm.record_artifact(str(tmp_path), "run-1", "1", "design", str(p))
    assert rm.has(str(tmp_path), "run-1")
    assert rm.verify_artifact(str(tmp_path), "run-1", str(p)) is True
    assert rm.verify_any_artifact(str(tmp_path), "run-1") is True
    # tamper -> hash no longer matches -> not verified
    p.write_text("tampered", encoding="utf-8")
    assert rm.verify_artifact(str(tmp_path), "run-1", str(p)) is False


def test_run_manifest_approval_roundtrip(tmp_path):
    rm.record_approval(str(tmp_path), "run-1", "1", "design", "approved", notes="ok")
    rec = rm.approval_for(str(tmp_path), "run-1", "1", "design")
    assert rec and rec["decision"] == "approved" and rec["run_id"] == "run-1"


def test_approval_request_carries_run_id(tmp_path):
    ex = PipelineExecutor.__new__(PipelineExecutor)
    ex.project_dir = str(tmp_path)
    ex.execution = types.SimpleNamespace(pipeline_id="run-A")
    ex.pending_approvals = []
    ex._get_review_instructions = lambda *a, **k: "n/a"
    req = ex._create_approval_request("design", "1", [])
    assert req["run_id"] == "run-A"


def test_stale_approval_rejected_and_recreated(tmp_path):
    ex = PipelineExecutor.__new__(PipelineExecutor)
    ex.project_dir = str(tmp_path)
    ex.execution = types.SimpleNamespace(pipeline_id="run-A")
    ex.approval_mode = "interactive"
    ex.auto_approve = False
    ex.decision_log = []
    ex.pending_approvals = []
    ex._log_decision = lambda *a, **k: None
    ex._stage_human_wait = {}

    calls = {"n": 0}

    def fake_create(agent, stage, arts, gate_id=None):
        calls["n"] += 1
        d = tmp_path / "approvals" / stage
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{agent}-approval.json").write_text(
            json.dumps({"status": "approved", "run_id": "run-A"}), encoding="utf-8")
        return {"review_instructions": "n/a"}

    ex._create_approval_request = fake_create

    # Pre-write a STALE approval from a DIFFERENT run.
    d = tmp_path / "approvals" / "1"
    d.mkdir(parents=True, exist_ok=True)
    stale_agent = "design"
    (d / f"{stale_agent}-approval.json").write_text(
        json.dumps({"status": "approved", "run_id": "run-B"}), encoding="utf-8")

    res = ex._wait_for_approval_ex("design", "1", [])
    assert res["decision"] == "approved"
    assert calls["n"] >= 1  # stale decision was rejected and the request recreated
