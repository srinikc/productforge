"""BI-PF-1253: detect a long-lived process running stale code (fail-closed freshness contract).

A process (the API server) imports its modules ONCE at start; every PR merged to ``develop`` leaves it
executing the startup snapshot - including the in-process delivery/worker code. That silent staleness made
the delivery lane run pre-fix gate code (repeated false BLOCKs). This module stamps the commit the process
loaded at import time and compares it with the working tree's current HEAD, so a stale runtime is detectable
and the lane can refuse instead of running outdated logic.

Owner: this module (pure read helper; writes nothing).
"""
import subprocess

from core.paths import ROOT

_ROOT = str(ROOT)


def _git_sha(cwd: str) -> str:
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


_STAMP = _git_sha(_ROOT)  # captured when this module is imported (approximately process start)


def stamp() -> str:
    """The commit this process loaded its code from (empty if not a git checkout)."""
    return _STAMP


def current() -> str:
    """The working tree's current commit (empty if unavailable)."""
    return _git_sha(_ROOT)


def status() -> dict:
    """``{loaded_sha, current_sha, stale}`` - stale when both are known and differ."""
    cur = current()
    return {"loaded_sha": _STAMP, "current_sha": cur,
            "stale": bool(_STAMP and cur and _STAMP != cur)}
