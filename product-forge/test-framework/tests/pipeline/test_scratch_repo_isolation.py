"""Dev-safety: scratch git repos must be isolated (never resolve to the parent repo).

Regression guard for the worktree-wipe defect: a scratch `git init`/commit must operate inside its own
`<ROOT>/products/_test_<name>` dir and NEVER walk up to the parent repo, even if GIT_DIR leaks in.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.dev import scratch_repo as sr  # noqa: E402


def test_make_is_under_products_test():
    p = sr.make("scratch_repo_iso_probe")
    try:
        assert os.path.basename(p) == "_test_scratch_repo_iso_probe"
        assert "products" in p.replace("\\", "/")
    finally:
        sr.cleanup(p)


def test_init_isolated_and_guarded():
    p = sr.make("scratch_repo_iso_guard")
    try:
        sr.init(p)
        assert os.path.isdir(os.path.join(p, ".git")), "scratch must have its own .git"
        top = sr.run(p, "rev-parse", "--show-toplevel").stdout.strip()
        assert os.path.normcase(os.path.abspath(top)) == os.path.normcase(os.path.abspath(p)), "not isolated"
    finally:
        sr.cleanup(p)


def test_init_is_isolated_even_with_leaked_git_dir(tmp_path, monkeypatch):
    """A leaked GIT_DIR in the environment must NOT let scratch git escape to the parent repo."""
    leaked = str(tmp_path / ".git")  # points somewhere else entirely
    monkeypatch.setenv("GIT_DIR", leaked)
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path))
    p = sr.make("scratch_repo_iso_leak")
    try:
        sr.init(p)
        top = sr.run(p, "rev-parse", "--show-toplevel").stdout.strip()
        assert os.path.normcase(os.path.abspath(top)) == os.path.normcase(os.path.abspath(p))
    finally:
        sr.cleanup(p)


def test_cleanup_refuses_non_scratch():
    import pytest
    with pytest.raises(sr.ScratchIsolationError):
        sr.cleanup(str(Path(sr._ROOT) / "core"))
