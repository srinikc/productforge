"""BI-PF-0764: git-remote CAS reservation - two reserves via the shared remote are disjoint."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import id_allocator as ia  # noqa: E402


def _g(*a, cwd):
    subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True)


def test_git_cas_blocks_are_disjoint(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    _g("init", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    work = tmp_path / "work"
    _g("init", "-b", "main", str(work), cwd=tmp_path)
    _g("remote", "add", "origin", str(origin), cwd=work)
    for k, v in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(ia, "_repo_root", lambda: str(work))
    monkeypatch.setenv("PF_ID_ALLOC_REMOTE", "on")
    monkeypatch.setenv("PF_ID_BLOCK_SIZE", "10")

    a = ia._reserve_git("product_forge", None, 10)
    b = ia._reserve_git("product_forge", None, 10)
    assert a and b, (a, b)
    assert a["end"] < b["start"], (a, b)     # disjoint blocks via the shared remote
    assert a["start"] == 1 and b["start"] == 11


def test_git_cas_disabled(monkeypatch):
    monkeypatch.setenv("PF_ID_ALLOC_REMOTE", "off")
    assert ia._reserve_git("product_forge", None, 10) is None
