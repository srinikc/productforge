"""Drift-guard tools: design_review_check flags violations and accepts aligned claims."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
SCRIPT = ROOT / "scripts" / "dev" / "design_review_check.py"


def _force_rmtree(p) -> None:
    p = Path(p)
    if not p.exists():
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o700)
            except Exception:
                pass
    shutil.rmtree(p, ignore_errors=True)


def test_design_review_flags_violation_and_aligned(tmp_path):
    d = ROOT / "products" / "_test_design_review"
    _force_rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    doc = d / "review.md"
    doc.write_text("- Route all engineering work through Intake\n"
                   "- Use core/task_contract.py for engineering tasks\n", encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, str(SCRIPT), str(doc), "--json"],
                           capture_output=True, text=True, cwd=str(ROOT))
        assert r.returncode == 0, r.stderr
        verdicts = {row["claim"]: row["verdict"] for row in json.loads(r.stdout)}
        assert any(v == "violates" for v in verdicts.values()), verdicts
        assert any(v == "aligned" for v in verdicts.values()), verdicts
    finally:
        _force_rmtree(d)


def test_intent_trace_check_runs_clean(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "dev" / "intent_trace_check.py")],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr
    assert "intent-trace:" in r.stdout
