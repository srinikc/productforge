"""
Regression for F0-1 approval truth (M0.1): BV-C01 + PF-001.

* human_proxy must FAIL CLOSED (blocked, never approve) on a parse error or proxy error.
* the auto-mode HIL proxy decision must be PROPAGATED, not discarded as 'approved' (BV-C01).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.human_proxy as hp  # noqa: E402
from core.pipeline_executor import PipelineExecutor, _HIL_DECISION_MAP  # noqa: E402


def _auto_executor(tmp_path):
    ex = PipelineExecutor.__new__(PipelineExecutor)  # bypass __init__
    ex.project_dir = str(tmp_path)
    ex.project = "TestProj"
    ex.approval_mode = "interactive"
    ex.auto_approve = False
    ex.execution = None
    ex.decision_log = []
    ex._log_decision = lambda *a, **k: None
    return ex


def test_parse_fails_closed():
    d = hp._parse("no json here")
    assert d["decision"] == "blocked"
    assert d.get("parse_error") is True


def test_decide_fails_closed_on_proxy_error():
    class Boom:
        def execute_agent(self, *a, **k):
            raise RuntimeError("boom")

    d = hp.decide(Boom(), "design", "1", [])
    assert d["decision"] == "blocked"


def test_decision_map_never_unknown_to_approved():
    assert _HIL_DECISION_MAP["approve"] == "approved"
    assert _HIL_DECISION_MAP["changes"] == "changes"
    assert _HIL_DECISION_MAP.get("weird", "rejected") == "rejected"
    assert _HIL_DECISION_MAP["blocked"] == "rejected"


def test_auto_proxy_decision_is_propagated(tmp_path, monkeypatch):
    ex = _auto_executor(tmp_path)
    monkeypatch.setattr(hp, "is_auto", lambda *a, **k: True)

    # reject must NOT become approved (BV-C01)
    monkeypatch.setattr(hp, "decide", lambda *a, **k: {"decision": "reject", "reasons": ["no"]})
    assert ex._wait_for_approval("design", "1", []) is False

    # approve maps to approved
    monkeypatch.setattr(hp, "decide", lambda *a, **k: {"decision": "approve"})
    assert ex._wait_for_approval("design", "1", []) is True

    # unknown / unparsed -> fail closed
    monkeypatch.setattr(hp, "decide", lambda *a, **k: {"decision": "banana"})
    assert ex._wait_for_approval("design", "1", []) is False
