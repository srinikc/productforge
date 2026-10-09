"""BI-PF-1066 (E9) backfill: derive api_impact from the item's own declared route descriptors."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from scripts.dev import backfill_api_impact as b  # noqa: E402


def test_decide_from_routes():
    assert b.decide({"links": {"backend_capability": ["route:/api/v1/x"]}})["needs_api"] is True
    assert b.decide({"links": {"backend_capability": ["route:/api/v1/x"]}})["routes"] == ["/api/v1/x"]
    assert b.decide({"links": {"backend_capability": ["module:core/x.py"]}})["needs_api"] is False
    assert b.decide({})["needs_api"] is False
