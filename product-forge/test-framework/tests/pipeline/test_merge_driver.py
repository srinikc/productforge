"""BI-PF-1176: pf-derived merge driver regenerates backlog indexes from items/."""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402
from scripts.dev import pf_merge_driver as drv  # noqa: E402

P = "_test_mergeelim"


def test_scope_from_path():
    assert drv.scope_from_path("product-forge/data/backlog/open.json") == ("product_forge", None)
    assert drv.scope_from_path("product-forge/products/myproj/backlog/closed.json") == ("project", "myproj")
    assert drv.scope_from_path("product-forge/data/backlog/counters.json") == ("product_forge", None)
    assert drv.scope_from_path("product-forge/core/x.py") == (None, None)


def test_is_doc():
    assert drv.is_doc("product-forge/docs/BACKLOG-SUMMARY.md") is True
    assert drv.is_doc("/x/product-forge/docs/documentation-index.html") is True
    assert drv.is_doc("product-forge/core/x.py") is False


def test_max_merge_takes_max_for_numbers(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text('{"next_label": 10, "x": {"n": 5}, "s": "keep"}')
    b = tmp_path / "b.txt"
    b.write_text('{"next_label": 12, "x": {"n": 3}, "new": 1}')
    merged = drv._max_merge([str(a), str(b)])
    assert merged["next_label"] == 12 and merged["x"]["n"] == 5   # max for numeric leaves
    assert merged["s"] == "keep" and merged["new"] == 1           # non-numeric kept


def test_driver_max_merges_counters_file(tmp_path):
    d = tmp_path / "data" / "backlog"
    d.mkdir(parents=True)
    a = d / "counters.json"
    a.write_text('{"next_label": 12}')
    b = tmp_path / "theirs.txt"
    b.write_text('{"next_label": 20}')
    assert drv.main(["pf_merge_driver.py", "", str(a), str(b)]) == 0
    assert json.loads(a.read_text(encoding="utf-8"))["next_label"] == 20


def test_driver_regenerates_index_from_items():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), P), ignore_errors=True)
    try:
        iid = backlog.add_epic("project", P, title="a traced item here")["id"]
        d, of, cf, h, c = backlog._paths("project", P)
        with open(of, "w", encoding="utf-8") as f:
            f.write("[ <<<<<<< garbage conflict >>>>>>> ]")   # drift the derived file
        rc = drv.main(["pf_merge_driver.py", "", of, ""])
        assert rc == 0
        rows = json.load(open(of, encoding="utf-8"))
        assert any(r.get("id") == iid for r in rows)              # regenerated from items/
    finally:
        shutil.rmtree(os.path.join(str(PRODUCTS_DIR), P), ignore_errors=True)
