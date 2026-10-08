"""BI-PF-0452 (ADR-0004): Feature <-> Epic <-> children bridge."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, backlog_link  # noqa: E402

PROJ = "_test_feature_epic"
_DIR = ROOT / "products" / PROJ


def _clean():
    shutil.rmtree(_DIR, ignore_errors=True)


def test_feature_becomes_epic_with_children():
    _clean()
    try:
        ep = backlog_link.ensure_feature_item(PROJ, {"id": "F-1", "name": "User login"})
        assert ep and ep["type"] == "epic"
        assert (ep.get("links") or {}).get("feature_id") == "F-1"
        ch = backlog_link.ensure_feature_child(PROJ, "F-1", "wire the login form")
        assert ch and ch["epic"] == ep["id"]
        e2 = backlog.get("project", PROJ, ep["id"])
        assert ch["id"] in (e2.get("children") or [])
        assert (ch.get("links") or {}).get("feature_id") == "F-1"
        m = backlog_link.mirror_feature_status(PROJ, "F-1", "in-progress", title="User login")
        assert m and m["id"] == ep["id"]
    finally:
        _clean()
