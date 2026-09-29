"""BU-C02/BZ-C02 backlog integrity: items/ truth vs derived indexes."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog as bl  # noqa: E402
from core.paths import ROOT  # noqa: E402

NAME = "_test_bkverify"
BASE = os.path.join(str(ROOT), "products", NAME)


def _cleanup():
    shutil.rmtree(BASE, ignore_errors=True)


def test_verify_ok_when_no_items_store():
    _cleanup()
    assert bl.verify("project", NAME)["ok"] is True


def test_verify_detects_status_mismatch_and_unindexed():
    _cleanup()
    d = bl._dir("project", NAME)
    bl._save_item(d, {"id": "BI-X-001", "status": "done", "title": "t"})
    bl._save_item(d, {"id": "BI-X-002", "status": "new", "title": "u"})
    bl._write_indexes("project", NAME,
                      [{"id": "BI-X-001", "status": "open", "title": "t"}], [])
    r = bl.verify("project", NAME)
    kinds = {x["kind"] for x in r["drift"]}
    assert r["ok"] is False
    assert "status_mismatch" in kinds and "unindexed_item" in kinds
    _cleanup()
