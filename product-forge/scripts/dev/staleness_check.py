"""BI-PF-0389 gate: architecture-version-aware analysis staleness + revalidation at pickup.

Asserts: the architecture fingerprint is stable/non-empty; a COMPLETE analysis records it; a changed
fingerprint makes the analysis STALE -> the item is ineligible; grooming.refresh_stale re-analyzes and
re-fingerprints so it becomes eligible again; and the seams are wired (scheduler checks staleness,
next_eligible refreshes stale before serving the pickup - the WorkerGrid claim handoff after
ADR-0002 moved registry/lease out of PF). Uses a scratch project scope (cleaned).
Run: ``python scripts/dev/staleness_check.py``.
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
_PROJ = "_test_staleness"


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _clean():
    shutil.rmtree(os.path.join(str(_PRODUCTS), _PROJ), ignore_errors=True)


def main() -> int:
    from core import backlog, grooming, scheduler
    _clean()
    try:
        fp = backlog.arch_fingerprint()
        _check(bool(fp), "arch fingerprint is non-empty")
        _check(fp == backlog.arch_fingerprint(), "arch fingerprint is stable")

        it = backlog.ensure_item("project", _PROJ, "stale-1", "staleness test item",
                                 type_="feature", origin="pipeline", tag="TEST")
        eid = it["id"]
        backlog.set_analysis("project", _PROJ, eid, status="COMPLETE", analyzed_by="test")
        item = backlog.get_epic("project", _PROJ, eid)
        _check(str((item.get("analysis") or {}).get("arch_fingerprint") or "") == fp,
               "COMPLETE analysis records the arch fingerprint")
        _check(backlog.analysis_is_stale(item) is False, "fresh analysis is not stale")

        # simulate an architecture change by corrupting the recorded fingerprint
        a = dict(item.get("analysis") or {})
        a["arch_fingerprint"] = "deadbeefdeadbeef"
        backlog.update("project", _PROJ, eid, analysis=a)
        item = backlog.get_epic("project", _PROJ, eid)
        _check(backlog.analysis_is_stale(item) is True, "changed fingerprint => stale")

        e = scheduler.eligible(item, by_id={eid: item}, worker=None, active=[])
        _check(e["ok"] is False and any("stale" in r for r in e["reasons"]),
               "stale analysis => not eligible (reason mentions stale)")

        # refresh re-analyzes + re-fingerprints -> eligible again
        r = grooming.refresh_stale("project", _PROJ, limit=5)
        _check(eid in r.get("refreshed", []), "refresh_stale re-analyzed the stale item")
        item = backlog.get_epic("project", _PROJ, eid)
        _check(backlog.analysis_is_stale(item) is False, "refreshed analysis is fresh again")
        e2 = scheduler.eligible(item, by_id={eid: item}, worker=None, active=[])
        _check(e2["ok"] is True, f"refreshed item is eligible again ({e2['reasons']})")

        # wiring
        with open(os.path.join(str(_ROOT), "core", "scheduler.py"), encoding="utf-8") as f:
            sched = f.read()
        _check("analysis_is_stale" in sched, "scheduler checks analysis staleness (wired)")
        _check("refresh_stale" in sched,
               "next_eligible refreshes stale before pickup (wired)")
    finally:
        _clean()

    if FAILS:
        print("staleness: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("staleness: OK (fingerprint, stale->ineligible, refresh->eligible, wired)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
