"""PFSSOT-P6 gate: worker registry is runtime-neutral, heartbeat-driven, and feeds the scheduler.

Exercises register -> slot bridge -> heartbeat -> stale derivation -> revoke/unregister on a scratch scope.
Run: ``python scripts/dev/worker_registry_check.py``.
"""
import os
import shutil
import sys

try:
    from core.paths import PRODUCTS_DIR as _PRODUCTS
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _PRODUCTS = os.path.join(_ROOT, "products")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []
_PROJ = "_test_worker_registry_gate"


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _clean():
    shutil.rmtree(os.path.join(str(_PRODUCTS), _PROJ), ignore_errors=True)


def main() -> int:
    from core import worker_registry as wr
    _clean()
    try:
        r = wr.register("project", _PROJ, runtime="opencode", capabilities=["python", "code"],
                        role="implement")
        _check(bool(r["worker_id"]) and r["status"] == "ONLINE", "register -> ONLINE")
        _check(r["runtime"] == "opencode", "runtime recorded (adapter value, not a dependency)")
        _check(len(wr.available_slots("project", _PROJ)) == 1, "registry feeds scheduler slots")

        _check(wr.heartbeat("project", _PROJ, r["worker_id"], status="IDLE")["ok"], "heartbeat ok")
        # stale derivation
        st = wr._read("project", _PROJ)
        st["workers"][r["worker_id"]]["last_heartbeat"] = "2000-01-01T00:00:00"
        wr._write("project", _PROJ, st)
        _check(wr.get("project", _PROJ, r["worker_id"])["status"] == "STALE", "old heartbeat -> STALE")
        _check(wr.available_slots("project", _PROJ) == [], "STALE worker not offered as a slot")

        _check(wr.unregister("project", _PROJ, r["worker_id"])["removed"] is True, "unregister works")
        r2 = wr.register("project", _PROJ, runtime="cli")
        _check(wr.unregister("project", _PROJ, r2["worker_id"], revoke=True)["revoked"] is True,
               "revoke works")
        _check(wr.get("project", _PROJ, r2["worker_id"])["status"] == "OFFLINE", "revoked -> OFFLINE")
    finally:
        _clean()

    if FAILS:
        print("worker-registry: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("worker-registry: OK (register/heartbeat/lifecycle/stale/slots/revoke)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
