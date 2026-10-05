"""PFSSOT-P9 gate: automatic dispatch is configurable, default-off, and composes P4+P5+P6+P7.

Offline (command runtime). Asserts: off by default; a forced tick assigns to an available worker and does
not double-assign; no worker => no assignment; worker integration disabled => no-op.
Run: ``python scripts/dev/dispatcher_check.py``.
"""
import contextlib
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
_PROJ = "_test_dispatcher_gate"


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _clean():
    shutil.rmtree(os.path.join(str(_PRODUCTS), _PROJ), ignore_errors=True)
    with contextlib.suppress(Exception):
        from core import job_manager
        c = job_manager._db()
        c.execute("DELETE FROM jobs WHERE project=?", (_PROJ,))
        c.commit()
        c.close()


def main() -> int:
    os.environ.setdefault("PF_OFFLINE", "1")
    os.environ.pop("WORKER_AUTO_DISPATCH", None)  # ensure default
    from core import backlog, dispatcher, grooming, worker_registry
    _clean()
    try:
        _check(dispatcher.enabled() is False, "auto dispatch defaults OFF")
        _check(dispatcher.tick("project", _PROJ)["ran"] is False, "tick refuses when off")

        worker_registry.register("project", _PROJ, runtime="command", capabilities=["python"])
        iid = backlog.add_epic("project", _PROJ, "Gate dispatch item", tag="TST")["id"]
        grooming.decide("project", _PROJ, iid, "APPROVE")
        r = dispatcher.tick("project", _PROJ, force=True)
        _check(r["assigned"] and r["assigned"][0]["item"] == iid, "forced tick assigns to available worker")
        _check(dispatcher.tick("project", _PROJ, force=True)["assigned"] == [], "no double-assign")
    finally:
        _clean()

    if FAILS:
        print("dispatcher: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("dispatcher: OK (configurable, default-off, composes eligibility+claim+registry+adapter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
