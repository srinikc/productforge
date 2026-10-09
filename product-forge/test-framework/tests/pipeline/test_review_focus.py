"""BI-PF-1066: review-focus checklist config validates + renders."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from scripts.dev import gen_review_focus as g  # noqa: E402


def test_seed_config_is_valid_and_renders():
    reg = g._load()
    assert g.validate(reg) == []
    doc = g.render(reg)
    assert "## Reviewer checks" in doc
    assert "ALWAYS flag" in doc and "IGNORE" in doc
    assert "Shift-left" in doc            # E6/E7 present
    assert "code-review agent, which runs" in doc


def test_validate_catches_bad_stage():
    reg = {"severity": {"critical": "block"}, "categories": [{"id": "x", "stage": "nope", "checks": ["a"]}],
           "always_flag": [], "ignore": []}
    assert any("invalid stage" in p for p in g.validate(reg))
