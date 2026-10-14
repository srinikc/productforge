"""Dev-tooling safety: isolated scratch git repos.

Bug class (found running the fast gate inside a git WORKTREE): a scratch git op resolved to the PARENT
repo (walked up), so `git add -A` + `git commit -m init` ran against the worktree repo and WIPED it
(stray `init` commit; `core.bare` flips). Root cause: the scratch dir had no own `.git` at that moment,
and/or a leaked `GIT_DIR`/`GIT_WORK_TREE`/`GIT_CEILING_DIRECTORIES` let git escape the scratch dir.

Rule for ALL dev checks/tests that create a scratch repo:
- keep the scratch dir INSIDE the worktree (``<ROOT>/products/_test_<name>``), never OS temp;
- create it with an explicit ``git init`` and VERIFY ``<scratch>/.git`` exists and
  ``rev-parse --show-toplevel`` == scratch (fail closed otherwise);
- run every scratch git op with a SANITIZED env (no GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE) and
  ``GIT_CEILING_DIRECTORIES`` pinned to the scratch parent so git can never walk up to the parent repo.

Usage:
    from scripts.dev import scratch_repo as sr
    path = sr.make("validation_engine")          # <ROOT>/products/_test_validation_engine
    sr.init(path)                                # git init + isolation guard (raises on violation)
    sr.run(path, "add", "-A"); sr.run(path, "commit", "-m", "init")
    sr.cleanup(path)                             # remove the scratch dir (own uniquely-named path only)
"""
import os
import shutil
import subprocess

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_DENY = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CEILING_DIRECTORIES", "GIT_COMMON_DIR")


class ScratchIsolationError(RuntimeError):
    pass


def _env_for(scratch: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _DENY}
    env["GIT_CEILING_DIRECTORIES"] = os.path.dirname(os.path.abspath(scratch))
    return env


def make(name: str) -> str:
    """Create (mkdir) a scratch repo dir inside the worktree: <ROOT>/products/_test_<name>."""
    path = os.path.join(str(_ROOT), "products", f"_test_{name}")
    os.makedirs(path, exist_ok=True)
    return path


def run(scratch: str, *args: str) -> subprocess.CompletedProcess:
    """Run git in the scratch dir with a sanitized env (can never escape to the parent repo)."""
    return subprocess.run(["git", *args], cwd=scratch, env=_env_for(scratch),
                          capture_output=True, text=True)


def init(scratch: str) -> None:
    """git init + fail-closed isolation guard: the repo toplevel MUST be the scratch dir."""
    os.makedirs(scratch, exist_ok=True)
    run(scratch, "init", "-q")
    if not os.path.isdir(os.path.join(scratch, ".git")):
        raise ScratchIsolationError(f"scratch repo has no own .git: {scratch}")
    top = run(scratch, "rev-parse", "--show-toplevel").stdout.strip()
    if os.path.normcase(os.path.abspath(top)) != os.path.normcase(os.path.abspath(scratch)):
        raise ScratchIsolationError(
            f"scratch git resolved to the PARENT repo ({top!r}) instead of {scratch!r} - refusing")


def cleanup(scratch: str) -> None:
    """Remove only the scratch dir (must be our own uniquely-named path under products/_test_)."""
    base = os.path.basename(os.path.abspath(scratch))
    if not base.startswith("_test_"):
        raise ScratchIsolationError(f"refusing to remove non-scratch path: {scratch}")
    shutil.rmtree(scratch, ignore_errors=True)
