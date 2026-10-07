"""PIDL-4 gate (BI-PF-0379): pre-dispatch + cross-worker synthesis + consequential-action gate.

Asserts: pre-dispatch returns the execution contract (pidl_context + execution_policy); synthesis detects
conflicts (path overlap / status disagreement) vs consistency; the consequential gate returns
APPROVAL_REQUIRED for consequential actions; and the seams are wired (scheduler.next_eligible attaches
pidl_context at pickup - the WorkerGrid claim handoff after ADR-0002 - and the workergrid service passes
it through; close_loop invokes synthesize for multi-item runs).
Run: ``python scripts/dev/pidl_synthesis_check.py``.
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
    from core import pidl

    # pre-dispatch: the execution contract a worker carries
    pd = pidl.pre_dispatch("product_forge", None, item={"id": "BI-X", "title": "add endpoint"},
                           action="add endpoint", components=["api"])
    _check(set(pd) >= {"pidl_context", "execution_policy", "decision", "consequential"},
           "pre_dispatch returns context + policy + decision")
    _check(set(pd["pidl_context"]) >= {"profile_version", "applicable_rules", "applicable_principles",
                                       "applicable_preferences", "review_lenses"},
           "pidl_context carries the relevant subset")
    _check("approval_required" in pd["execution_policy"], "execution_policy structured")

    # synthesis: consistency vs conflicts
    ok = pidl.synthesize("product_forge", None, results=[
        {"item_id": "A", "ok": True, "paths": ["core/a.py"]},
        {"item_id": "B", "ok": True, "paths": ["core/b.py"]}])
    _check(ok["decision"]["action"] == "AUTO_PROCEED", "consistent results -> AUTO_PROCEED")
    _check(ok["synthesis"]["consistent"] is True, "consistent synthesis flagged")
    clash = pidl.synthesize("product_forge", None, results=[
        {"item_id": "A", "ok": True, "paths": ["core/shared.py"]},
        {"item_id": "B", "ok": True, "paths": ["core/shared.py"]}])
    _check(clash["decision"]["action"] == "CORRECT", "path overlap -> CORRECT")
    _check(clash["synthesis"]["consistent"] is False, "conflict flagged")
    mixed = pidl.synthesize("product_forge", None, results=[
        {"item_id": "A", "ok": True}, {"item_id": "B", "ok": False, "status": "failed"}])
    _check(mixed["decision"]["action"] in ("CORRECT", "REVIEW"), "mixed result -> CORRECT/REVIEW")
    _check(pidl.synthesize("product_forge", None, results=[{"item_id": "A", "ok": True}])
           == pidl.synthesize("product_forge", None, results=[{"item_id": "A", "ok": True}]),
           "synthesis is deterministic")

    # consequential gate
    _check(pidl.consequential_gate("product_forge", None, action="delete production database"
                                   )["decision"]["action"] == "APPROVAL_REQUIRED",
           "consequential -> APPROVAL_REQUIRED")
    _check(pidl.consequential_gate("product_forge", None, action="add a doc line", area="doc"
                                   )["decision"]["action"] == "AUTO_PROCEED",
           "benign -> AUTO_PROCEED")

    # wiring: the seams actually invoke PIDL (pickup handoff after the WorkerGrid decoupling)
    with open(os.path.join(str(_ROOT), "core", "scheduler.py"), encoding="utf-8") as f:
        sch = f.read()
    _check("pre_dispatch" in sch and "pidl_context" in sch,
           "scheduler.next_eligible attaches pidl_context (wired)")
    # pickup passthrough: the coordinator hands pidl_context to the worker.
    # Stage 3a (BI-PF-0412): Python service.py was replaced by the Go
    # coordinator - check whichever source exists (fail-closed if neither).
    wg_dir = os.path.join(os.path.dirname(str(_ROOT)), "workergrid")
    candidates = [
        (os.path.join(wg_dir, "internal", "httpapi", "httpapi.go"), "workergrid/internal/httpapi/httpapi.go"),
        (os.path.join(wg_dir, "service.py"), "workergrid/service.py"),
    ]
    found = None
    for path, label in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                found = (label, "pidl_context" in f.read())
            break
    if found is None:
        FAILS.append("workergrid coordinator source not found (pickup passthrough unverifiable)")
    else:
        _check(found[1], f"{found[0]} passes pidl_context through (wired)")
    with open(os.path.join(str(_ROOT), "core", "close_loop.py"), encoding="utf-8") as f:
        cl = f.read()
    _check(".synthesize(" in cl and "synth_hold" in cl, "close_loop invokes synthesize for multi-item (wired)")

    if FAILS:
        print("pidl-synthesis: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("pidl-synthesis: OK (pre-dispatch contract, synthesis conflicts/consistency, consequential gate, wired)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
