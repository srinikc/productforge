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
    assert drv.main(["pf_merge_driver.py", "", str(a), str(b), str(a)]) == 0
    assert json.loads(a.read_text(encoding="utf-8"))["next_label"] == 20


def test_git_merge_invokes_driver_and_resolves_counters(tmp_path):
    """Integration (BI-PF-1290): a real `git merge` must resolve counters.json via the driver (no conflict).

    Guards the BI-PF-1176 bug: git passes TEMP files for %O/%A/%B, so the driver MUST use %P (the real
    pathname). Without %P the driver cannot know the path and every derived file conflicts.
    """
    import subprocess
    drv = str(ROOT / "scripts" / "dev" / "pf_merge_driver.py")

    def g(*a):
        return subprocess.run(["git", "-C", str(tmp_path), *a], capture_output=True, text=True, check=True)

    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    g("config", "merge.pf-derived.driver", f'python "{drv}" %O %A %B %P')
    (tmp_path / "data" / "backlog").mkdir(parents=True)
    (tmp_path / ".gitattributes").write_text("data/backlog/counters.json merge=pf-derived\n")
    cp = tmp_path / "data" / "backlog" / "counters.json"

    def setc(v):
        cp.write_text(json.dumps({"next_label": v}))

    setc(10)
    g("add", "-A")
    g("commit", "-qm", "base")
    g("checkout", "-q", "-b", "other")
    setc(20)
    g("add", "-A")
    g("commit", "-qm", "other")
    g("checkout", "-q", "main")
    setc(12)
    g("add", "-A")
    g("commit", "-qm", "main")
    r = subprocess.run(["git", "-C", str(tmp_path), "merge", "other"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr          # driver resolved -> NO conflict
    assert json.loads(cp.read_text(encoding="utf-8"))["next_label"] == 20   # max-merged


def test_driver_regenerates_index_from_items():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), P), ignore_errors=True)
    try:
        iid = backlog.add_epic("project", P, title="a traced item here")["id"]
        d, of, cf, h, c = backlog._paths("project", P)
        with open(of, "w", encoding="utf-8") as f:
            f.write("[ <<<<<<< garbage conflict >>>>>>> ]")   # drift the derived file
        rc = drv.main(["pf_merge_driver.py", "", of, "", of])   # %A==%P (real path) for the unit test
        assert rc == 0
        rows = json.load(open(of, encoding="utf-8"))
        assert any(r.get("id") == iid for r in rows)              # regenerated from items/
    finally:
        shutil.rmtree(os.path.join(str(PRODUCTS_DIR), P), ignore_errors=True)
