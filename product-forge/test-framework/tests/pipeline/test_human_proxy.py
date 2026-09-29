"""BI-PF-0245: HIL proxy is bounded to one decision per gate (cache) and surfaced."""
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
