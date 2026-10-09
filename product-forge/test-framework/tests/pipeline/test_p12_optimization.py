"""P12a/P12b: provider rate budgeting (non-blocking) + scheduler fairness (aging)."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

from core import capacity as cap  # noqa: E402
from core import scheduler as sc  # noqa: E402


# ── P12a: provider rate budgeting (never blocks the agent) ───────────────────
def test_unknown_provider_no_wait():
    assert cap.rate_wait("__nope__") == 0.0


def test_rpm_pacing_bounded(monkeypatch):
    monkeypatch.setattr(cap, "provider_limits", lambda p: {"rpm": 2, "tpm": 0})
    cap._RATE.pop("t", None)
    cap.record_request("t")
    cap.record_request("t")
    w = cap.rate_wait("t")
    assert 0.0 < w <= 30.0
    assert cap.rate_wait("t", max_wait=0.0) == 0.0


def test_pace_fail_open(monkeypatch):
    from core.orchestrator import llm_client
    monkeypatch.setattr(cap, "provider_limits", lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    llm_client._pace("x")  # must not raise


def test_record_request_ok():
    cap.record_request("t2", tokens=10)
    assert cap.provider_limits("t2") == {"rpm": 0, "tpm": 0}


# ── P12b: scheduler fairness (anti-starvation aging) ─────────────────────────
def test_age_boost_bounds():
    fresh = {"priority": "P3", "created_at": datetime.now().isoformat()}
    old = {"priority": "P3", "created_at": (datetime.now() - timedelta(hours=sc._AGING_HOURS * 5)).isoformat()}
    assert sc._age_boost(fresh) == 0
    assert sc._age_boost(old) == 3  # capped


def test_aged_low_priority_not_starved():
    fresh = {"priority": "P3", "created_at": datetime.now().isoformat()}
    aged = {"priority": "P3", "created_at": (datetime.now() - timedelta(hours=sc._AGING_HOURS * 3 + 1)).isoformat()}
    assert sc._rank(aged)[0] <= sc._rank(fresh)[0]


def test_high_priority_still_wins_fresh():
    p0 = {"priority": "P0", "created_at": datetime.now().isoformat()}
    p3 = {"priority": "P3", "created_at": datetime.now().isoformat()}
    assert sc._rank(p0)[0] < sc._rank(p3)[0]
