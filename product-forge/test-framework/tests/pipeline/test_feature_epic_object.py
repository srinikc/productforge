"""BI-PF-0455: ensure_feature_item must accept a plan Feature OBJECT (not only a dict)."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, backlog_link  # noqa: E402
from core.product_plan import Feature  # noqa: E402

PROJ = "_test_feature_obj"
_DIR = ROOT / "products" / PROJ


def test_ensure_feature_item_accepts_feature_object():
    shutil.rmtree(_DIR, ignore_errors=True)
    try:
        feat = Feature(id="F-9", name="Object feature", status="planned",
                       priority="must-have", module="m", phase=1)
        ep = backlog_link.ensure_feature_item(PROJ, feat)
        assert ep and ep.get("id"), "object path must create/return the epic"
        assert (ep.get("links") or {}).get("feature_id") == "F-9"
        assert ep.get("type") == "epic"
        # dict path still works
        ep2 = backlog_link.ensure_feature_item(PROJ, {"id": "F-9", "name": "Object feature"})
        assert ep2["id"] == ep["id"]
        assert backlog.get("project", PROJ, ep["id"]) is not None
    finally:
        shutil.rmtree(_DIR, ignore_errors=True)
