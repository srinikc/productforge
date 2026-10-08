"""Pre-commit branch guard (BI-PF-0430): block a DIRECT commit of FEATURE work on a protected branch.

EOS / AGENTS: feature work is never committed directly to `develop`/`main`; it lands via a `--no-ff` merge.
This runs FIRST in the pre-commit hook. Allowed on a protected branch:
  - merge-resolution commits (``MERGE_HEAD`` present), and
  - **bookkeeping-only** commits: every staged path is delivery/derived state (``data/backlog/**`` + the
    generated backlog docs) - i.e. the post-merge ``set_delivery`` provenance write, not feature work.
Anything else on ``develop``/``main``/``master`` is blocked. Emergency override: ``PF_ALLOW_DIRECT_COMMIT=1``.

Exit 0 = allow, 1 = block.
"""
import os
import subprocess
import sys

PROTECTED = ("develop", "main", "master")
BOOKKEEPING = (
    "product-forge/data/backlog/",
    "product-forge/docs/BACKLOG-SUMMARY.md",
    "product-forge/docs/documentation-index.html",
)


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def current_branch() -> str:
    return _git("symbolic-ref", "--short", "-q", "HEAD")


def is_merge_in_progress() -> bool:
    return bool(_git("rev-parse", "-q", "--verify", "MERGE_HEAD"))


def staged_paths() -> list:
    return [p for p in _git("diff", "--cached", "--name-only").splitlines() if p.strip()]


def _is_bookkeeping(path: str) -> bool:
    return any(path.replace("\\", "/").startswith(p) for p in BOOKKEEPING)


def evaluate(branch: str, merge: bool, allow: bool, staged=None) -> tuple:
    """Pure decision table: (ok, reason). ``staged`` = list of staged paths (or None if unknown)."""
    if allow:
        return True, "PF_ALLOW_DIRECT_COMMIT override (direct commit allowed)"
    if not branch:
        return True, "detached HEAD (rebase/cherry-pick/merge ok)"
    if branch in PROTECTED:
        if merge:
            return True, f"merge commit on {branch!r} (allowed)"
        if staged and all(_is_bookkeeping(p) for p in staged):
            return True, f"bookkeeping-only commit on {branch!r} (allowed)"
        return False, (f"direct commit on protected branch {branch!r} is forbidden - "
                       "create a feature branch: git checkout -b feature/<name> "
                       "(bookkeeping-only commits under data/backlog/ are allowed)")
    return True, f"feature branch {branch!r}"


def main(argv=None) -> int:
    allow = str(os.environ.get("PF_ALLOW_DIRECT_COMMIT", "")).strip().lower() in ("1", "true", "yes")
    ok, reason = evaluate(current_branch(), is_merge_in_progress(), allow, staged=staged_paths())
    print(f"branch-guard: {'OK' if ok else 'BLOCK'} - {reason}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
