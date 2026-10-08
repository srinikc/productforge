"""Pre-commit branch guard (BI-PF-0430): block a DIRECT commit on a protected integration branch.

EOS / AGENTS: feature work is never committed directly to `develop`/`main`; it lands via a `--no-ff` merge.
This runs FIRST in the pre-commit hook. Merge-resolution commits are allowed (``MERGE_HEAD`` present), so a
normal merge flow is never blocked. Emergency override: ``PF_ALLOW_DIRECT_COMMIT=1``.

Exit 0 = allow, 1 = block.
"""
import os
import subprocess
import sys

PROTECTED = ("develop", "main", "master")


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def current_branch() -> str:
    return _git("symbolic-ref", "--short", "-q", "HEAD")


def is_merge_in_progress() -> bool:
    return bool(_git("rev-parse", "-q", "--verify", "MERGE_HEAD"))


def evaluate(branch: str, merge: bool, allow: bool) -> tuple[bool, str]:
    """Pure decision table: (ok, reason)."""
    if allow:
        return True, "PF_ALLOW_DIRECT_COMMIT override (direct commit allowed)"
    if not branch:
        return True, "detached HEAD (rebase/cherry-pick/merge ok)"
    if branch in PROTECTED:
        if merge:
            return True, f"merge commit on {branch!r} (allowed)"
        return False, (f"direct commit on protected branch {branch!r} is forbidden - "
                       "create a feature branch: git checkout -b feature/<name>")
    return True, f"feature branch {branch!r}"


def main(argv=None) -> int:
    allow = str(os.environ.get("PF_ALLOW_DIRECT_COMMIT", "")).strip().lower() in ("1", "true", "yes")
    ok, reason = evaluate(current_branch(), is_merge_in_progress(), allow)
    print(f"branch-guard: {'OK' if ok else 'BLOCK'} - {reason}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
