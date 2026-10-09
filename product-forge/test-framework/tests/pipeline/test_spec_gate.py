"""BI-PF-1167 (E6): spec gate requires testable AC + concrete NFR targets + edge/error cases."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import spec_review as sr  # noqa: E402


def _blocking_testability(fs):
    return any(f["class"] == "BLOCKING" and f["category"] == "testability" for f in fs)


def test_untestable_requirements_block():
    thin = ("FR-1 login. NFR-1 performance. Acceptance: it works. " + "detail " * 60)
    fs, _ = sr._review_one("docs/requirements.md", "design", thin, 0)
    assert _blocking_testability(fs)                      # no concrete thresholds -> not testable
    assert any(f["class"] == "OPTIONAL" for f in fs)      # no edge/error cases -> advisory


def test_testable_requirements_pass():
    good = ("FR-1 login. NFR-1 p95 latency < 200 ms at 99.9% availability. "
            "Acceptance: returns 200 within 200 ms. Edge case: empty password. Error handling: 401. "
            + "detail " * 60)
    fs, _ = sr._review_one("docs/requirements.md", "design", good, 0)
    assert not _blocking_testability(fs)
    assert not any(f["class"] == "OPTIONAL" for f in fs)
