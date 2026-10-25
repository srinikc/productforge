"""Final report persistence (BI-PF-1484)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
sys.path.insert(0, str(ROOT))
import finalize_item as fi  # noqa: E402


def test_build_requires_all_acs_pass(monkeypatch):
    item = {"revision": 1, "status": "in_progress", "ac_verification": [
        {"ac": "one", "result": "PASS", "evidence": ["t1"]},
        {"ac": "two", "result": "PENDING", "evidence": []}],
        "review_dispositions": {}, "decisions": []}
    monkeypatch.setattr(fi.backlog, "get_epic", lambda *a, **k: item)
    monkeypatch.setattr(fi.tr, "events", lambda i: [])
    r = fi.build("BI-PF-1484")
    assert r["ac_problems"] == ["two"]


def test_build_includes_usage_tests_and_dispositions(monkeypatch):
    item = {"revision": 2, "status": "in_progress", "ac_verification": [
        {"ac": "one", "result": "PASS", "evidence": ["t1"]}],
        "review_dispositions": {"diff": {"sig:a": {"status": "ACCEPTED", "note": "why"}}},
        "decisions": [{"decision": "DISPOSITION_APPROVAL", "hil_confirmed": True,
                       "scope": "disposition_approval", "mode": "diff", "sigs": ["sig:a"]}]}
    evs = [{"at": "2026-01-01T00:00:00+00:00", "stage": "tests", "tests": [{"command": "pytest x", "result": "pass",
                                                          "passed": 1, "failed": 0, "duration_ms": 5}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cached_tokens": 0, "model": "deepseek-v4.1-flash"}}]
    monkeypatch.setattr(fi.backlog, "get_epic", lambda *a, **k: item)
    monkeypatch.setattr(fi.tr, "events", lambda i: evs)
    r = fi.build("BI-PF-1484")
    assert r["tests"][0]["command"] == "pytest x"
    assert r["usage"]["input_tokens"] == 10
    assert r["dispositions"]["diff"]["sig:a"]["status"] == "ACCEPTED"
    assert r["ac_problems"] == []
