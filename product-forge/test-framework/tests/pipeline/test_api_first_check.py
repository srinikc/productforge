"""BI-PF-1404: API-first enforcement gate - baseline-aware, single-source decision logic."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.dev import api_first_check as af  # noqa: E402


def test_id_of_extracts_item_id():
    assert af._id_of("BI-PF-1288: no api_impact decision (needs_api + reason)") == "BI-PF-1288"


def test_baseline_grandfathers_existing_items():
    base = af.grandfathered()
    assert isinstance(base, set)
    assert len(base) > 0
