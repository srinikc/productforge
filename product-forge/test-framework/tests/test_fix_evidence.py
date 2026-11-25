"""Fix evidence and delta re-review guard."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import fix_evidence_check as f  # noqa: E402

def test_fix_evidence_requires_fields_and_pass():
    item={"fix_evidence":[{"finding_sig":"abc","origin_class":"FIX_INCOMPLETE","regression_test":"x","controls_rerun":["CTL-1"],"result":"FAIL","evidence":"README.md"}]}
    bad=f.problems(item)
    assert any("result is not PASS" in x for x in bad)

def test_fix_evidence_rejects_invalid_class():
    item={"fix_evidence":[{"finding_sig":"abc","origin_class":"NOPE","regression_test":"x","controls_rerun":["CTL-1"],"result":"PASS","evidence":"README.md"}]}
    assert any("invalid origin_class" in x for x in f.problems(item))
