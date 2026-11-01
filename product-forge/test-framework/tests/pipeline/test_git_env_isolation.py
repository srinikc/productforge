"""Regression: ambient Git selectors must not retarget test repositories or precheck."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.dev import git_env  # noqa: E402
from scripts.dev import precheck  # noqa: E402


def _init_repo(path: Path) -> None:
    git_env.run_git(path, "init", "-q", check=True)
    git_env.run_git(path, "config", "user.email", "t@local", check=True)
    git_env.run_git(path, "config", "user.name", "t", check=True)


def _commit_file(path: Path, name: str, text: str) -> None:
    (path / name).write_text(text, encoding="utf-8")
    git_env.run_git(path, "add", name, check=True)
    git_env.run_git(path, "commit", "-q", "-m", "init", check=True)


def test_sanitized_git_ignores_leaked_parent_selectors(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    child = tmp_path / "child"
    parent.mkdir()
    child.mkdir()
    _init_repo(parent)
    _commit_file(parent, "README.md", "parent\n")
    before = git_env.worktree_fingerprint(parent)

    monkeypatch.setenv("GIT_DIR", str(parent / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(parent))
    monkeypatch.setenv("GIT_INDEX_FILE", str(parent / ".git" / "index"))
    monkeypatch.setenv("GIT_COMMON_DIR", str(parent / ".git"))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(parent))

    _init_repo(child)
    _commit_file(child, "note.txt", "caf\u00e9 \u2014 \u2192\n")

    assert git_env.worktree_fingerprint(parent) == before
    assert (child / ".git").is_dir()
    assert git_env.run_git(child, "show", "HEAD:note.txt").stdout == "caf\u00e9 \u2014 \u2192\n"
    assert not (parent / "note.txt").exists()


def test_precheck_aborts_when_head_changes_during_run(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _commit_file(repo, "README.md", "x\n")

    monkeypatch.setattr(precheck, "_ROOT", str(repo))

    def mutate(_argv=None):
        git_env.run_git(repo, "commit", "--allow-empty", "-q", "-m", "poison", check=True)
        return 0

    monkeypatch.setattr(precheck, "_main", mutate)
    assert precheck.main([]) == 1
