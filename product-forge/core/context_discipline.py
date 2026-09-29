"""Context discipline (BI-0226).

Bound the assembled context so per-section calls stop growing across a stage: after each
section the pack is capped to a fixed budget (configurable), keeping the most relevant
head + tail. Prevents the 19k -> 29k char growth the review observed.
"""
import os
from typing import Optional

_ENV = "PIPELINE_SECTION_CONTEXT_CHARS"
_DEFAULT = 4000


def max_chars() -> int:
    try:
        return int(os.getenv(_ENV, str(_DEFAULT)) or _DEFAULT)
    except Exception:
        return _DEFAULT


def cap(text: str, limit: Optional[int] = None) -> str:
    """Head+tail truncate `text` to `limit` chars (default from env). 0 = unlimited."""
    limit = max_chars() if limit is None else int(limit)
    t = text or ""
    if limit <= 0 or len(t) <= limit:
        return t
    half = max(1, limit // 2)
    return (t[:half] + f"\n...[context trimmed: {len(t) - limit} chars]...\n" + t[-half:])
