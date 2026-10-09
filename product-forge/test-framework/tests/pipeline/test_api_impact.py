"""BI-PF-1066 (E9): api_impact decision validator."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

P = "_test_api_impact"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), P), ignore_errors=True)


def test_api_impact_decision():
    _clean()
    try:
        iid = backlog.add_epic("project", P, title="an item needing an api surface here")["id"]
        assert any("no api_impact" in x for x in backlog.api_impact_warnings("project", P))
        backlog.update("project", P, iid, api_impact={"needs_api": True, "routes": [], "reason": "x"})
        assert any("needs_api=true but no routes" in x for x in backlog.api_impact_warnings("project", P))
        backlog.update("project", P, iid,
                       api_impact={"needs_api": True, "routes": ["/api/v1/x"], "reason": "y"})
        assert not any(iid in x for x in backlog.api_impact_warnings("project", P))
    finally:
        _clean()
