"""PFSSOT-P8A.1 (BI-PF-0381): auto delivery + evidence write-back on completion."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, close_loop  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p8a1"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _git_repo():
    d = os.path.join(str(PRODUCTS_DIR), _PROJ)
    os.makedirs(d, exist_ok=True)
    for a in (["git", "init", "-q"], ["git", "config", "user.email", "t@l"],
              ["git", "config", "user.name", "t"]):
        subprocess.run(a, cwd=d, capture_output=True, text=True)
    with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
        f.write("x\n")
    subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=d, capture_output=True, text=True)
    return d


def test_finalize_writes_delivery_and_evidence():
    _clean()
    try:
        d = _git_repo()
        iid = backlog.add_epic("project", _PROJ, "Feature X", tag="TST")["id"]
        r = close_loop._finalize(d, "project", _PROJ, iid, "run-abc", _PROJ)
        assert r["item"] == iid and r["merge_sha"]
        links = backlog.get("project", _PROJ, iid).get("links") or {}
        assert links["delivery"]["merge_sha"] == r["merge_sha"]
        assert links["delivery"]["branch"] and links["delivery"]["commits"]
        assert links["evidence"]["run_id"] == "run-abc"
    finally:
        _clean()


def test_set_delivery_is_the_writer():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "F", tag="TST")["id"]
        backlog.set_delivery("project", _PROJ, iid, branch="feature/x", merge_sha="abc123",
                             commits=["abc123"], pr="42", pr_url="http://pr/42")
        d = (backlog.get("project", _PROJ, iid).get("links") or {}).get("delivery") or {}
        assert d["branch"] == "feature/x" and d["merge_sha"] == "abc123" and d["pr"] == "42"
    finally:
        _clean()
