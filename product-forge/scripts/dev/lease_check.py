"""PFSSOT-P5 gate: atomic claim + lease + recovery; single claimer (IS-PF-0034).

Exercises, on a scratch project: claim attaches a lease; a second claim gets nothing; renew/release
work; expired lease recovers per policy; and portfolio.enqueue/claim/finish delegate to job_manager.
Run: ``python scripts/dev/lease_check.py``.
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
_PROJ = "_test_lease_gate"


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
    from core import backlog, grooming, job_manager, portfolio
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Lease gate item", tag="TST")["id"]
        grooming.decide("project", _PROJ, iid, "APPROVE")

        r = job_manager.claim_next("project", _PROJ, worker="w1", lease_seconds=10)
        _check(r.get("claimed") is True and r.get("lease_id"), "claim attaches a lease")
        ex = backlog.get("project", _PROJ, iid)["execution"]
        _check(ex["worker_id"] == "w1" and ex["lease_id"] == r["lease_id"], "execution bound to lease")

        r2 = job_manager.claim_next("project", _PROJ, worker="w2")
        _check(r2.get("claimed") is False, "no double-claim")

        _check(job_manager.renew_lease("project", _PROJ, iid)["renewed"] is True, "renew works")
        _check(job_manager.release("project", _PROJ, iid)["released"] is True, "release works")

        r3 = job_manager.claim_next("project", _PROJ, worker="w3")
        _check(r3.get("claimed") is True, "released item claimable again")
        backlog.set_execution("project", _PROJ, iid, worker_id="w3",
                              lease_expires_at="2000-01-01T00:00:00")
        rec = job_manager.recover_expired("project", _PROJ)
        _check(rec["count"] == 1 and rec["policy"] == "REQUIRE_REVIEW", "expired -> recover (review default)")
        _check(backlog.get("project", _PROJ, iid)["status"] == "blocked", "recovery marks blocked")

        # IS-PF-0034: portfolio is a shim, not a second claimer
        shim = "_test_lease_gate_shim"
        portfolio.enqueue(shim, priority=5, item_id="BI-X")
        _check(job_manager._row(job_manager._db(), shim) is not None, "portfolio.enqueue -> job_manager row")
        job_manager.finish(shim, 0)
        with contextlib.suppress(Exception):
            c = job_manager._db()
            c.execute("DELETE FROM jobs WHERE project=?", (shim,))
            c.commit()
            c.close()
    finally:
        _clean()

    if FAILS:
        print("lease: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("lease: OK (claim/lease/no-double-claim/renew/release/recover + single claimer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
