"""BI-PF-1290: per-worker sync - merge origin/develop into the current branch (never rebase/reset)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.dev import sync_develop as sd  # noqa: E402


def _g(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    """A work repo with a bare origin; local ``develop`` advanced past ``feature/x``."""
    bare = tmp_path / "o.git"
    subprocess.run(["git", "init", "--bare", "-b", "develop", str(bare)], check=True, capture_output=True)
    w = tmp_path / "w"
    w.mkdir()
    _g(w, "init", "-b", "develop")
    _g(w, "config", "user.email", "t@t")
    _g(w, "config", "user.name", "t")
    (w / "a.txt").write_text("base\n")
    _g(w, "add", "-A")
    _g(w, "commit", "-m", "base")
    _g(w, "remote", "add", "origin", str(bare))
    _g(w, "push", "-u", "origin", "develop")
    _g(w, "checkout", "-b", "feature/x")
    (w / "b.txt").write_text("feat\n")
    _g(w, "add", "-A")
    _g(w, "commit", "-m", "feat")
    _g(w, "checkout", "develop")
    (w / "c.txt").write_text("dev\n")
    _g(w, "add", "-A")
    _g(w, "commit", "-m", "dev work")
    _g(w, "push", "origin", "develop")
    _g(w, "checkout", "feature/x")
    return w


def test_check_reports_behind_without_writing(tmp_path, monkeypatch):
    w = _repo(tmp_path)
    monkeypatch.chdir(w)
    assert sd.main(["--check"]) == 1          # behind -> exit 1
    assert not (w / "c.txt").exists()         # --check wrote nothing


def test_sync_merges_develop_into_branch(tmp_path, monkeypatch):
    w = _repo(tmp_path)
    monkeypatch.chdir(w)
    assert sd.main([]) == 0
    assert (w / "c.txt").exists()             # develop's commit is now in the branch
    assert sd.main([]) == 0                   # idempotent: already up to date


def test_pre_push_returns_1_after_merge(tmp_path, monkeypatch):
    w = _repo(tmp_path)
    monkeypatch.chdir(w)
    assert sd.main(["--pre-push"]) == 1       # merged -> tell the caller to re-run push
    assert (w / "c.txt").exists()
    assert sd.main(["--pre-push"]) == 0       # now up to date -> push may proceed


def test_source_conflict_aborts_clean(tmp_path, monkeypatch):
    w = _repo(tmp_path)
    _g(w, "checkout", "develop")
    (w / "a.txt").write_text("develop-edit\n")
    _g(w, "add", "-A")
    _g(w, "commit", "-m", "develop edits a.txt")
    _g(w, "push", "origin", "develop")
    _g(w, "checkout", "feature/x")
    (w / "a.txt").write_text("feature-edit\n")
    _g(w, "add", "-A")
    _g(w, "commit", "-m", "feature edits a.txt")
    monkeypatch.chdir(w)
    assert sd.main([]) == 2                   # SOURCE conflict -> abort
    assert not (w / ".git" / "MERGE_HEAD").exists()   # merge aborted, tree intact
    assert (w / "a.txt").read_text() == "feature-edit\n"
