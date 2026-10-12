"""BI-PF-1253: stale-runtime detection (loaded commit vs working tree HEAD)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import runtime_freshness as rf  # noqa: E402


def test_status_shape():
    s = rf.status()
    assert set(s) >= {"loaded_sha", "current_sha", "stale"}
    assert isinstance(s["stale"], bool)


def test_fresh_process_is_not_stale():
    # This process imported rf just now -> its stamp matches the tree HEAD (or both are empty).
    assert rf.stamp() == rf.current() or not rf.stamp()
    assert rf.status()["stale"] is False


def test_stale_detected_when_loaded_differs(monkeypatch):
    monkeypatch.setattr(rf, "_STAMP", "aaa111")
    monkeypatch.setattr(rf, "current", lambda: "bbb222")
    s = rf.status()
    assert s["stale"] is True and s["loaded_sha"] == "aaa111" and s["current_sha"] == "bbb222"


def test_no_false_stale_when_unknown(monkeypatch):
    monkeypatch.setattr(rf, "_STAMP", "")
    monkeypatch.setattr(rf, "current", lambda: "bbb222")
    assert rf.status()["stale"] is False
