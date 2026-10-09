"""P12a/P12b gate: provider rate budgeting (non-blocking) + scheduler fairness (aging).

P12a: ``core.capacity.rate_wait`` paces within ``provider_limits`` and is FAIL-OPEN (never blocks the agent).
P12b: ``core.scheduler._age_boost``/``_rank`` give a bounded anti-starvation boost.
Run: ``python scripts/dev/rate_budget_check.py``.
"""
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main() -> int:
    from core import capacity as cap

    # P12a: config limits are read; unknown provider fails open.
    lim = cap.provider_limits("opencode-go")
    _check(lim["rpm"] > 0 or lim["tpm"] > 0, "provider_limits read from config")
    _check(cap.rate_wait("__no_such_provider__") == 0.0, "unknown provider -> no wait (fail-open)")

    # P12a: pacing respects rpm (stubbed limit) and is bounded (<= max_wait).
    orig = cap.provider_limits
    cap.provider_limits = lambda p: {"rpm": 2, "tpm": 0}
    try:
        cap._RATE.pop("stub", None)
        cap.record_request("stub")
        cap.record_request("stub")
        w = cap.rate_wait("stub")
        _check(0.0 < w <= 30.0, f"rate_wait bounded after rpm hit (got {w!r})")
        _check(cap.rate_wait("stub", max_wait=0.0) == 0.0, "max_wait floor honoured")
    finally:
        cap.provider_limits = orig

    # P12a: _pace never raises (fail-open) even with a broken budget layer.
    try:
        from core.orchestrator import llm_client
        llm_client._pace("__whatever__")
        _check(True, "pace ok")
    except Exception as e:  # noqa: BLE001
        _check(False, f"_pace raised {type(e).__name__}")

    # P12b: aging is bounded and anti-starvation works.
    from datetime import datetime, timedelta
    from core import scheduler as sc
    fresh = {"priority": "P3", "created_at": datetime.now().isoformat()}
    old = {"priority": "P3", "created_at": (datetime.now() - timedelta(hours=sc._AGING_HOURS * 3 + 1)).isoformat()}
    _check(sc._age_boost(fresh) == 0, "fresh item: no aging boost")
    _check(sc._age_boost(old) == 3, "old item: boost capped at 3")
    _check(sc._rank(old)[0] <= sc._rank(fresh)[0], "aged P3 reaches a better rank than fresh P3")
    p0f = {"priority": "P0", "created_at": datetime.now().isoformat()}
    _check(sc._rank(p0f)[0] == 0, "fresh P0 rank 0")

    if FAILS:
        print("rate-budget: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("rate-budget: OK (provider_limits read, fail-open + bounded pacing, scheduler aging)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
