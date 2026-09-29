"""BI-0226: bounded context discipline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import context_discipline as cd  # noqa: E402


def test_cap_trims_over_limit():
    t = "a" * 10000
    out = cd.cap(t, limit=1000)
    assert len(out) <= 1000 + 80 and "trimmed" in out


def test_cap_under_limit_unchanged():
    t = "hello"
    assert cd.cap(t, limit=100) == t
