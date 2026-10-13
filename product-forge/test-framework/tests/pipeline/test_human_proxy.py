"""BI-PF-0245: HIL proxy is bounded to one decision per gate (cache) and surfaced.

IS-PF-0048: the gate task must carry the product brief + the artifacts under review so the
auto-mode proxy can judge (instead of failing closed on missing context).
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import human_proxy as hp  # noqa: E402


class _FakeExec:
    def __init__(self, d):
        self.calls = 0
        self.project_dir = d

    def execute_agent(self, agent_id, stage_id, task):
        self.calls += 1

        class _E:
            artifacts = []
            error = '```json {"decision": "approve", "gate": "3", "reasons": []}```'

        return _E()


def test_one_decision_per_gate():
    d = tempfile.mkdtemp()
    try:
        hp.clear_cache(d)
        ex = _FakeExec(d)
        a = hp.decide(ex, "implement", "3")
        b = hp.decide(ex, "implement", "3")
        assert ex.calls == 1, "second ask for the same gate must reuse the decision"
        assert a["decision"] == "approve" == b["decision"]
        hp.decide(ex, "validate", "5")
        assert ex.calls == 2, "a different gate is a distinct decision"
        assert hp.stats()["cache_hits"] >= 1
    finally:
        hp.clear_cache(d)
        shutil.rmtree(d, ignore_errors=True)


def test_gate_task_includes_brief_and_artifacts():
    """IS-PF-0048: the proxy gate receives the brief + the artifacts under review."""
    d = tempfile.mkdtemp()
    try:
        hp.clear_cache(d)
        art = os.path.join(d, "ideation-output.md")
        with open(art, "w", encoding="utf-8") as f:
            f.write("IDEATION CONTENT marker")
        captured = {}

        class _Ex:
            project_dir = d
            project_idea = "small todo app BRIEF marker"

            def execute_agent(self, agent_id, stage_id, task):
                captured["task"] = task

                class _E:
                    artifacts = []
                    error = '```json {"decision": "approve", "gate": "0", "reasons": []}```'

                return _E()

        r = hp.decide(_Ex(), "ideation", "0", [art])
        assert r["decision"] == "approve"
        assert "BRIEF marker" in captured["task"], "brief must be in the gate task"
        assert "IDEATION CONTENT marker" in captured["task"], "artifact must be in the gate task"
    finally:
        hp.clear_cache(d)
        shutil.rmtree(d, ignore_errors=True)
