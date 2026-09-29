"""F0-3 (PF-031): compliance evidence must be run-bound."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import close_loop as cl  # noqa: E402


def _compliance(tmp_path, run_id, agent="design"):
    d = tmp_path / "compliance"
    d.mkdir(parents=True, exist_ok=True)
    payload = {"status": "pass"}
    if run_id:
        payload["run_id"] = run_id
    (d / f"{agent}-1-latest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_compliance_matches_current_run(tmp_path):
    _compliance(tmp_path, "run-A")
    assert cl._compliance_passed(str(tmp_path), run_id="run-A") is True


def test_compliance_from_other_run_is_not_evidence(tmp_path):
    _compliance(tmp_path, "run-A")
    assert cl._compliance_passed(str(tmp_path), run_id="run-B") is False


def test_compliance_legacy_path_without_run_id(tmp_path):
    _compliance(tmp_path, "run-A")
    # No run id requested -> legacy behaviour preserved.
    assert cl._compliance_passed(str(tmp_path)) is True
