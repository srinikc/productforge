"""BI-PF-0441: core.backlog.update() rejects wrong-typed structured fields fail-closed (no write)."""
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog  # noqa: E402

PROJ = "_test_bguard"
_DIR = ROOT / "products" / PROJ


def _item_file(eid: str) -> Path:
    return _DIR / "backlog" / "items" / f"{eid}.json"


@pytest.fixture(autouse=True)
def _clean():
    shutil.rmtree(_DIR, ignore_errors=True)
    yield
    shutil.rmtree(_DIR, ignore_errors=True)


def test_wrong_typed_fields_rejected_without_writing():
    it = backlog.add_epic("project", PROJ, title="guard probe", source="test", origin="review")
    eid = it["id"]
    f = _item_file(eid)
    before = f.read_bytes()
    for bad in ({"analysis": "oops"}, {"dashboard_impact": "oops"},
                {"links": ["nope"]}, {"decisions": "nope"}, {"deps": "nope"}):
        with pytest.raises(ValueError):
            backlog.update("project", PROJ, eid, **bad)
    assert f.read_bytes() == before, "a rejected update must not touch the item file"
    # valid types still work
    backlog.update("project", PROJ, eid, analysis={"status": "NOT_ANALYZED"},
                   dashboard_impact={"needs_dashboard": False, "reason": "test"})
    got = backlog.get("project", PROJ, eid)
    assert got["analysis"]["status"] == "NOT_ANALYZED"
    assert got["dashboard_impact"]["needs_dashboard"] is False
    # None clears
    backlog.update("project", PROJ, eid, analysis=None)
    assert backlog.get("project", PROJ, eid)["analysis"] is None
