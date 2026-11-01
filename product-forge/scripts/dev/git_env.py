"""Central Git subprocess-environment policy (test-isolation containment).

Git commands must never inherit an ambient GIT_DIR/GIT_WORK_TREE from a hook or parent
test process.  Always run test/scratch Git commands through this module (or pass
``sanitized_env`` to subprocess.run).  ``cwd`` alone is not isolation.
"""
from __future__ import annotations

import hashlib
import os
import subprocess

_DENY = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_CEILING_DIRECTORIES",
)


def sanitized_env(base: dict | None = None, ceiling: str | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    for key in _DENY:
        env.pop(key, None)
    if ceiling is not None:
        env["GIT_CEILING_DIRECTORIES"] = str(ceiling)
    return env


def sanitize_process_env() -> None:
    """Strip leaked Git selectors from the current process and all children."""
    for key in _DENY:
        os.environ.pop(key, None)


def run_git(cwd, *args: str, check: bool = False, capture_output=True,
            text: bool = True, input: str | None = None, timeout: int | None = None,
            ceiling: str | None = None):
    """Run git in ``cwd`` with a sanitized environment.

    Pass ``ceiling`` only for a disposable scratch repo whose parent must not be
    searched.  Normal repo/subdirectory commands must be allowed to walk up to
    their repository root.
    """
    target = os.path.abspath(str(cwd))
    return subprocess.run(
        ["git", *args],
        cwd=target,
        env=sanitized_env(ceiling=ceiling),
        check=check,
        capture_output=capture_output,
        text=text,
        encoding="utf-8",
        errors="replace",
        input=input,
        timeout=timeout,
    )


def worktree_fingerprint(root) -> str:
    """Stable fingerprint of HEAD, symbolic HEAD, local refs, and index entries.

    Used by precheck to abort when a test/check mutates the active worktree.
    """
    target = os.path.abspath(str(root))

    def _out(*args: str) -> str:
        return (run_git(target, *args).stdout or "").strip()

    head = _out("rev-parse", "--verify", "HEAD")
    symbolic = _out("symbolic-ref", "-q", "HEAD")
    # Shared allocation/lease authority refs are external coordination state, not worktree
    # mutations: id_allocator/CAS intentionally fetches them into refs/heads during a run.
    authority_refs = {"refs/heads/pf-id-counter", "refs/heads/pf-leases"}
    refs = "\n".join(
        line for line in _out("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads").splitlines()
        if line.split(" ", 1)[0] not in authority_refs
    )
    index = _out("ls-files", "-s")
    payload = "\0".join((head, symbolic, refs, index)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
