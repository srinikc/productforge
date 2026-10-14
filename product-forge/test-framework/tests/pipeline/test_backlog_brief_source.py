"""BI-PF-1374: the single writer normalizes ``brief.source`` to {authored, extracted, derived}."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog as b  # noqa: E402
from core import grooming  # noqa: E402

_S = "project"
_P = "_test_brief_source"


def _noop(monkeypatch):
    monkeypatch.setattr(grooming, "groom", lambda *a, **k: {"applied": False})
    monkeypatch.setattr(grooming, "decide", lambda *a, **k: {"applied": False})


def test_add_normalizes_explicit_brief_source(monkeypatch):
    _noop(monkeypatch)
    it = b.add_epic(_S, _P, "probe add", type_="task", brief={"problem": "p", "source": "review"})
    try:
        assert (it.get("brief") or {}).get("source") == "authored"
    finally:
        b.delete(_S, _P, it["id"])


def test_update_normalizes_explicit_brief_source(monkeypatch):
    _noop(monkeypatch)
    it = b.add_epic(_S, _P, "probe upd", type_="task")
    try:
        b.update(_S, _P, it["id"], brief={"source": "bogus"})
        got = b.get_epic(_S, _P, it["id"]) or {}
        assert (got.get("brief") or {}).get("source") == "authored"
    finally:
        b.delete(_S, _P, it["id"])
