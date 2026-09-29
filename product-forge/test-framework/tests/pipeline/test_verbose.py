"""BI-0229: verbose logging gate."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import env_flags as ef  # noqa: E402


def test_verbose_default_off(monkeypatch):
    monkeypatch.delenv("PIPELINE_VERBOSE", raising=False)
    assert ef.verbose() is False


def test_verbose_on(monkeypatch):
    monkeypatch.setenv("PIPELINE_VERBOSE", "1")
    assert ef.verbose() is True
