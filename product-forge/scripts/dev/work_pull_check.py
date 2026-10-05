"""PFSSOT-P8 gate: manual work pull - register -> pull -> assignment package -> no double-pull -> start.

Composes registry (P6) + eligibility (P4) + claim/lease (P5) + adapter (P7). Offline (command adapter).
Run: ``python scripts/dev/work_pull_check.py``.
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
_PROJ = "_test_work_pull_gate"


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
    from core import backlog, grooming, work_pull
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Gate work item", tag="TST")["id"]
        grooming.decide("project", _PROJ, iid, "APPROVE")

        r = work_pull.pull("project", _PROJ, runtime="command")
        _check(r["assigned"] is True, "pull assigns an eligible item")
        pkg = r.get("package") or {}
        _check(pkg.get("worker_id") and pkg.get("lease_id"), "assignment carries worker + lease")
        _check((pkg.get("task") or {}).get("item_id") == iid, "package carries the canonical item id")
        _check((pkg.get("task") or {}).get("analysis", {}).get("status") == "COMPLETE",
               "stored analysis travels (pickup = execute)")
        _check(pkg.get("contract_status") == "OK", "contract valid")

        _check(work_pull.pull("project", _PROJ, runtime="command")["assigned"] is False,
               "no double-pull")

        wt = os.path.join(str(_PRODUCTS), _PROJ, "wt")
        os.makedirs(wt, exist_ok=True)
        st = work_pull.start("project", _PROJ, iid, worktree=wt,
                             command=[sys.executable, "-c", "print('ok')"])
        _check(st["ok"] and st["result"]["status"] == "pr_ready", "start via command adapter -> pr_ready")
    finally:
        _clean()

    if FAILS:
        print("work-pull: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("work-pull: OK (pull/package/no-double-pull/start; composes registry+eligibility+claim+adapter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
