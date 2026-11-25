"""Precheck fingerprint must ignore shared allocation/lease refs (not worktree mutations)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
from git_env import worktree_fingerprint  # noqa: E402


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, encoding="utf-8")


def test_authority_refs_do_not_change_worktree_fingerprint(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    (repo / "tracked.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "seed")

    before = worktree_fingerprint(repo)
    _git(repo, "update-ref", "refs/heads/pf-id-counter", "HEAD")
    _git(repo, "update-ref", "refs/heads/pf-leases", "HEAD")
    assert worktree_fingerprint(repo) == before

    _git(repo, "update-ref", "refs/heads/topic", "HEAD")
    assert worktree_fingerprint(repo) != before
