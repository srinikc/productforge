"""BI-PF-1066 (E3): non-LLM high-risk-pattern scan."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from scripts.dev import review_static_check as r  # noqa: E402


def test_detects_high_risk_patterns():
    txt = ('cur.execute(f"SELECT * FROM users WHERE id={uid}")\n'
           'subprocess.run(cmd, shell=True)\n'
           'eval(user_input)\n'
           'os.system(cmd)\n'
           'pickle.loads(blob)\n')
    names = {h[0] for h in r.scan_text(txt)}
    assert {"sqli_fstring", "shell_true", "eval_exec", "os_system", "pickle_load"} <= names


def test_clean_text_has_no_findings():
    assert r.scan_text("def add(a, b):\n    return a + b\n") == []
