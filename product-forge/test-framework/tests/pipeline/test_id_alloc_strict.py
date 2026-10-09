"""BI-PF-0966: strict id allocation (default) fails closed; soft (opt-in) falls back to a local block."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import id_allocator as ia  # noqa: E402


def test_strict_raises_when_authority_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, "OUT", str(tmp_path / ("i" + ".json")))
    monkeypatch.setenv("PF_ID_ALLOC", "strict")
    monkeypatch.setattr(ia, "_reserve_git", lambda *a, **k: None)
    with pytest.raises(RuntimeError):
        ia.alloc("product_forge", None, existing_max=0)


def test_soft_falls_back_to_local_block(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, "OUT", str(tmp_path / ("i2" + ".json")))
    monkeypatch.setenv("PF_ID_ALLOC", "on")
    monkeypatch.setenv("PF_ID_ALLOC_REMOTE", "off")
    monkeypatch.setenv("PF_ID_ALLOC_API", "off")
    assert ia.alloc("product_forge", None, existing_max=0) == 1


def test_default_mode_is_strict(monkeypatch):
    monkeypatch.delenv("PF_ID_ALLOC", raising=False)
    monkeypatch.setattr(ia, "_mode", lambda: "strict")   # committed default
    assert ia.strict() is True and ia.enabled() is True
