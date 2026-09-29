"""M0 acceptance suite (BI-PF-0243): the 11 execution-integrity scenarios.

Each test asserts the invariant that must hold for safe unattended execution.
These compose the controls built in F0-1..F0-7.
"""
import json
import shutil
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.human_proxy as hp  # noqa: E402
import core.lock_manager as lm  # noqa: E402
from core import budget as B  # noqa: E402
from core import run_manifest as rm  # noqa: E402
from core import close_loop as cl  # noqa: E402
from core import backlog as bl  # noqa: E402
from core.compliance_check import tests_pass  # noqa: E402
from core.pipeline_executor import PipelineExecutor, _HIL_DECISION_MAP  # noqa: E402
from core.output_checklist import check as checklist_check  # noqa: E402


# 1. Happy path: verified, run-bound artifacts present.
def test_01_happy_path_verified_run_bound(tmp_path):
    p = tmp_path / "design-output.md"
    p.write_text("# Design\ncontent", encoding="utf-8")
    rm.record_artifact(str(tmp_path), "run-1", "1", "design", str(p))
    assert rm.verify_any_artifact(str(tmp_path), "run-1") is True


# 2. Output exists but a required deliverable is missing -> never COMPLETED.
def test_02_missing_deliverable_not_complete(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text("# Design\n## F-1: Alpha\n- FR-1: a\n", encoding="utf-8")
    res = checklist_check("design", [str(p)])
    assert res["ok"] is False and res["essential_missing"]


# 3. Tests not executed / absent -> UNKNOWN, never PASS.
def test_03_tests_not_executed_is_unknown(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    assert tests_pass(tmp_path)["status"] == "unknown"


# 4. Human reject / malformed proxy -> never approval.
def test_04_approval_fails_closed(tmp_path, monkeypatch):
    assert hp._parse("not json")["decision"] == "blocked"
    assert _HIL_DECISION_MAP.get("reject") == "rejected"
    ex = PipelineExecutor.__new__(PipelineExecutor)
    ex.project_dir = str(tmp_path); ex.approval_mode = "interactive"
    ex.auto_approve = False; ex.execution = None; ex.decision_log = []
    ex._log_decision = lambda *a, **k: None
    monkeypatch.setattr(hp, "is_auto", lambda *a, **k: True)
    monkeypatch.setattr(hp, "decide", lambda *a, **k: {"decision": "reject"})
    assert ex._wait_for_approval("design", "1", []) is False


# 5. Tool outside the allowlist / missing spec -> denied before side effects.
def test_05_tool_allowlist_denied():
    ex = PipelineExecutor.__new__(PipelineExecutor)
    ex.agent_specs = {}; ex.project_dir = "."; ex.tool_cache = None
    ex.tool_registry = types.SimpleNamespace(execute=lambda *a, **k: None, schemas=lambda *a, **k: [])
    r = ex.execute_agent_tool("ghost", "run_command", {})
    assert r["ok"] is False and "denied" in r["error"].lower()


# 6. Repeated no-progress -> bounded (delegation budget caps).
def test_06_bounded_delegation():
    from core.delegation import DelegationBudget
    b = DelegationBudget(max_invocations_per_stage=1, max_total_invocations=2)
    assert b.can_invoke("1") is True
    b.record("1")
    assert b.can_invoke("1") is False  # per-stage cap reached -> stop, no unbounded fan-out


# 7. Race for the last budget / the same lock -> at most one wins.
def test_07_race_one_winner(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "_pid_alive", lambda pid: True)
    a, b = lm.LockManager(str(tmp_path)), lm.LockManager(str(tmp_path))
    assert a.acquire_lock("p", holder="run-1", run_id="r1") is not None
    assert b.acquire_lock("p", holder="run-2", run_id="r2") is None
    pd = str(tmp_path)
    B.update_section(None, "limits", {"per_run_cap_usd": 10.0}, products_dir=pd)
    assert B.reserve(None, 8.0, key="x", products_dir=pd)["ok"] is True
    assert B.reserve(None, 5.0, key="y", products_dir=pd)["ok"] is False


# 8. Crash after write: hash mismatch means the artifact is not trusted.
def test_08_tampered_artifact_not_trusted(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("ok", encoding="utf-8")
    rm.record_artifact(str(tmp_path), "run-1", "1", "design", str(p))
    p.write_text("tampered", encoding="utf-8")
    assert rm.verify_artifact(str(tmp_path), "run-1", str(p)) is False


# 9. Prior-run evidence present -> stale is rejected.
def test_09_stale_prior_run_rejected(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("ok", encoding="utf-8")
    rm.record_artifact(str(tmp_path), "run-A", "1", "design", str(p))
    assert rm.verify_artifact(str(tmp_path), "run-B", str(p)) is False
    d = tmp_path / "compliance"; d.mkdir()
    _agent = "design"
    (d / f"{_agent}-1-latest.json").write_text(json.dumps({"status": "pass", "run_id": "run-A"}), encoding="utf-8")
    assert cl._compliance_passed(str(tmp_path), run_id="run-B") is False


# 10. Budget/limit exceeded mid-run -> not completion (stop, resumable).
def test_10_over_budget_stops():
    ex = PipelineExecutor.__new__(PipelineExecutor)
    ex.pipeline_start_time = 1.0  # long ago
    ex.max_total_time = 1          # 1s budget
    ex.min_remaining_time = 0
    ex._human_wait_total = lambda: 0.0
    ex.stage_durations = []
    ex.dag_executor = types.SimpleNamespace(get_ready_stages=lambda: ["1"], states={})
    should_continue, reason = ex._check_time_budget()
    assert should_continue is False and reason


# 11. Duplicate dispatch -> deduplicated by idempotency key (external_id).
def test_11_duplicate_dispatch_deduped():
    proj = "_test_m0_acceptance"
    base = Path(__file__).parent.parent.parent.parent / "products" / proj
    try:
        a = bl.ensure_item("project", proj, "conv:dup-1", title="Do a thing", type_="feature")
        b = bl.ensure_item("project", proj, "conv:dup-1", title="Do a thing", type_="feature")
        assert a["id"] == b["id"]
    finally:
        if base.is_dir():
            shutil.rmtree(base, ignore_errors=True)
