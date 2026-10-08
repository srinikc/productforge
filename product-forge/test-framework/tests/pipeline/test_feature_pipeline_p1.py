"""BI-PF-0453 (P1): adding a plan feature materializes an Epic + child work items."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, backlog_link  # noqa: E402
from core.product_plan import ProductPlan  # noqa: E402

PROJ = "_test_p1_plan"
_DIR = ROOT / "products" / PROJ


def test_add_feature_creates_epic_and_children():
    shutil.rmtree(_DIR, ignore_errors=True)
    try:
        plan = ProductPlan(PROJ)
        plan.add_feature("F-1", "User login", "m1", "must-have", 1,
                         description="users can log in", requirements=["R-1", "R-2"])
        ep = backlog_link.ensure_feature_item(PROJ, {"id": "F-1", "name": "User login"})
        assert ep and ep["type"] == "epic"
        e = backlog.get("project", PROJ, ep["id"])
        assert len(e.get("children") or []) == 2, e.get("children")
        kids = [backlog.get("project", PROJ, c) for c in e["children"]]
        assert all(k and k["epic"] == ep["id"] for k in kids)
    finally:
        shutil.rmtree(_DIR, ignore_errors=True)
