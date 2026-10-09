"""BI-PF-0460 gate: dogfood schedule (due logic) + tick idempotency + trends/regression.

Exercises ``core.dogfood_schedule`` and ``core.dogfood_run.trends``. No daemon/network.
Run: ``python scripts/dev/dogfood_schedule_check.py``.
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

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
    from core import dogfood_run, dogfood_schedule as ds

    now = datetime.now()
    data = {"entries": [
        {"project": "p1", "enabled": True, "interval_hours": 24, "last_run": ""},
        {"project": "p2", "enabled": True, "interval_hours": 24, "last_run": now.isoformat()},
        {"project": "p3", "enabled": False, "interval_hours": 1, "last_run": ""},
        {"project": "p4", "enabled": True, "interval_hours": 1,
         "last_run": (now - timedelta(hours=2)).isoformat()},
    ]}
    due = ds.due(now, data)
    _check([e["project"] for e in due] == ["p1", "p4"], f"due = enabled+elapsed only (got {[e['project'] for e in due]})")

    # tick enqueues only due entries (patched load/save/start)
    orig_load, orig_save, orig_start = ds.load, ds.save, dogfood_run.start
    started = []
    try:
        ds.load = lambda: data
        ds.save = lambda d: d
        dogfood_run.start = lambda idea, project, **k: (started.append(project) or {"run_id": "r-" + project})
        r = ds.run_due()
        _check(sorted(started) == ["p1", "p4"], f"tick enqueues due only (got {started})")
        _check(data["entries"][0]["last_run"] != "", "last_run updated for due entry")
        _check(data["entries"][1]["last_run"] == now.isoformat(), "not-due entry last_run unchanged")
    finally:
        ds.load, ds.save, dogfood_run.start = orig_load, orig_save, orig_start

    # trends/regression over recorded DOGFOOD runs (patched list_runs)
    from core import validation_engine as ve
    orig_lr = ve.list_runs
    try:
        ve.list_runs = lambda scope, project=None, profile="": [
            {"result": "PASS", "run_id": "a"}, {"result": "PASS", "run_id": "b"}, {"result": "FAIL", "run_id": "c"}]
        t = dogfood_run.trends("p")
        _check(t["regression"] is True, "regression True after PASS then non-PASS")
        _check(t["counts"].get("PASS") == 2 and t["counts"].get("FAIL") == 1, "counts")
        ve.list_runs = lambda scope, project=None, profile="": [
            {"result": "FAIL", "run_id": "a"}, {"result": "PASS", "run_id": "b"}]
        _check(dogfood_run.trends("p")["regression"] is False, "no regression when latest is PASS")
    finally:
        ve.list_runs = orig_lr

    if FAILS:
        print("dogfood-schedule: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("dogfood-schedule: OK (due logic, tick idempotent, trends/regression)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
