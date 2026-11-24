"""Shared terminal-status policy for design/spec gate enforcement."""

TERMINAL_SKIP = frozenset({"rejected", "cancelled", "won't_do", "wont_do"})


def should_skip(status) -> bool:
    return str(status or "").strip().lower() in TERMINAL_SKIP
