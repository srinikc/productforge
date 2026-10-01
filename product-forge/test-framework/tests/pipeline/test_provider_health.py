"""BI-PF-0279: provider health tracking — outcomes, states, health-aware ordering (no regression)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import provider_health as H  # noqa: E402
from core import provider_kinds as PK  # noqa: E402


def setup_function(_):
    H.reset()


def teardown_function(_):
    H.reset()


def test_unknown_provider_is_neutral():
    assert H.state("_never_seen") == "unknown"
    assert H.score("_never_seen") == 0.5
    assert H.cooldown("_never_seen") is False


def test_success_makes_healthy():
    for _ in range(5):
        H.record("_p1", ok=True, status=200, latency_ms=100)
    assert H.state("_p1") == "healthy"
    assert H.score("_p1") >= 0.6
    p = H.snapshot()["_p1"]
    assert p["success"] == 5 and p["latency_ms"] > 0


def test_errors_degrade_then_unavailable():
    for _ in range(6):
        H.record("_p2", ok=False, status=500, error="boom")
    assert H.state("_p2") in ("degraded", "unavailable")
    assert H.snapshot()["_p2"]["errors_by_status"].get("500") == 6


def test_rate_limit_triggers_cooldown_and_unavailable():
    H.record("_p3", ok=False, status=429)
    assert H.cooldown("_p3") is True
    assert H.state("_p3") in ("degraded", "unavailable")


def test_ordering_unchanged_without_health_data():
    cands = [{"provider": "a", "kind": "aggregator"}, {"provider": "b", "kind": "direct"}]
    before = [c["provider"] for c in PK.order_candidates(cands, prefer_kind="direct")]
    assert before == ["b", "a"]  # prefer_kind still primary


def test_degraded_provider_sinks_in_ordering():
    # make provider 'a' unavailable, 'b' healthy; keep equal kinds so health is the tiebreak
    for _ in range(6):
        H.record("a", ok=False, status=500)
    for _ in range(6):
        H.record("b", ok=True, status=200)
    cands = [{"provider": "a", "kind": "aggregator"}, {"provider": "b", "kind": "aggregator"}]
    order = [c["provider"] for c in PK.order_candidates(cands)]
    assert order[0] == "b" and order[-1] == "a"
    assert any(c.get("health_state") for c in PK.order_candidates(cands))


def test_strategy_report_surfaces_provider_health(tmp_path):
    for _ in range(6):
        H.record("opencode-go", ok=False, status=500)
    from core import model_strategy as M
    rep = M.assess(str(tmp_path), phase="b")
    assert "provider_health" in rep
