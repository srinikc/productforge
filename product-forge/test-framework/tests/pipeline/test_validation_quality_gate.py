"""BI-PF-1279: the shared validation runner ensures the quality-gate record so the DOGFOOD
profile's ``quality_gate`` check resolves (instead of always unknown -> BLOCKED).

Hermetic: ``core.run_quality_gate.evaluate`` is monkeypatched to record a run-bound result; the test
proves ``core.validation_engine.run`` invokes the ensure step and the check reflects gate pass/fail
(fail-closed preserved). Scratch state is isolated under ``products/_test_bi_pf_1279/`` and removed.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import run_quality_gate, validation_engine as ve  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_bi_pf_1279"


def _git_repo(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=d, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "t@local"], cwd=d, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=d, capture_output=True, text=True)
    (d / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=d, capture_output=True, text=True)


def _fake_evaluate(passed: bool):
    def _eval(project_dir: str = "", mode: str = "item", *, run_dir: str = "", run_id: str = ""):
        p = run_dir or project_dir
        res = {"passed": passed, "mode": mode, "reasons": [] if passed else ["gate failed"]}
        run_quality_gate.record_run(p, run_id, res)
        run_quality_gate.record(p, res)
        return res
    return _eval


def _cleanup():
    shutil.rmtree(Path(PRODUCTS_DIR) / _PROJ, ignore_errors=True)


def test_dogfood_profile_resolves_quality_gate(monkeypatch, tmp_path):
    d = tmp_path / "repo"
    _git_repo(d)
    monkeypatch.setattr(run_quality_gate, "evaluate", _fake_evaluate(True))
    try:
        res = ve.run(_PROJ, str(d), profile_name="DOGFOOD", run_id="dog-pass", scope="project")
        assert res["checks"]["quality_gate"]["status"] == "pass"   # resolved (was unknown before)
    finally:
        _cleanup()


def test_dogfood_quality_gate_failure_is_fail_closed(monkeypatch, tmp_path):
    d = tmp_path / "repo"
    _git_repo(d)
    monkeypatch.setattr(run_quality_gate, "evaluate", _fake_evaluate(False))
    try:
        res = ve.run(_PROJ, str(d), profile_name="DOGFOOD", run_id="dog-fail", scope="project")
        assert res["checks"]["quality_gate"]["status"] == "fail"
        assert res["result"] != "PASS"   # never a false PASS
    finally:
        _cleanup()
