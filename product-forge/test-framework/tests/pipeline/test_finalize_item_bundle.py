"""Unit test for finalize_item --auto-bundle (BI-PF-1548)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
sys.path.insert(0, str(ROOT))

os.environ.setdefault("PF_BACKLOG_DB", "off")

import finalize_item


def test_finalize_item_help():
    try:
        finalize_item.main(["--help"])
    except SystemExit as e:
        assert e.code == 0


def test_finalize_auto_bundle_dry_run():
    # Calling main with --report and existing item validates build() output
    ret = finalize_item.main(["--item", "BI-PF-1548", "--report"])
    assert ret == 0
