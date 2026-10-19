"""Shared git subprocess helper for gate/tooling (BI-PF-1464).

One policy for every caller:
- decode stdout as UTF-8 (never the OS locale - Windows cp1252 raises UnicodeDecodeError on
  non-ASCII diffs/paths and produces a different review sha than Linux CI),
- fail closed on a non-zero exit (a broken git must never become an empty diff that makes a
  gate pass on nothing),
- surface undecodable bytes with a warning instead of failing silently.
"""
from __future__ import annotations

import subprocess
import sys


class GitError(RuntimeError):
    """A git invocation failed (non-zero exit) or could not be run."""


def git_text(args: list[str] | tuple[str, ...], cwd, timeout: int = 30) -> str:
    """Return git stdout decoded as UTF-8; raise GitError on failure."""
    argv = list(args)
    try:
        r = subprocess.run(["git", *argv], cwd=str(cwd), capture_output=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise GitError(f"git {' '.join(repr(a) for a in argv)} could not run: {e}") from e
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()
        detail = err[-1] if err else "no stderr"
        raise GitError(f"git {' '.join(repr(a) for a in argv)} failed ({r.returncode}): {detail}")
    out = r.stdout or ""
    if "\ufffd" in out:
        print(f"[git] warning: git {' '.join(argv)} output had undecodable bytes (U+FFFD)",
              file=sys.stderr)
    return out
