"""PFSSOT-P7 gate: runtime-neutral worker adapter contract (OpenCode first; native declared).

Exercises the contract on the Command adapter (offline), asserts the verb set, that OpenCode is one of
several adapters (not a dependency), and that the native path is declared (not routed through workers).
Run: ``python scripts/dev/adapters_check.py``.
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
_PROJ = "_test_adapters_gate"


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _clean():
    shutil.rmtree(os.path.join(str(_PRODUCTS), _PROJ), ignore_errors=True)


def main() -> int:
    from core import worker_adapters as wa
    _clean()
    try:
        _check(set(wa.ADAPTER_OPS) == {"register", "heartbeat", "get_status", "accept_assignment",
                                       "start", "pause", "cancel", "report_result", "disconnect"},
               "contract verb set (doc section 18)")
        runtimes = {a["runtime"] for a in wa.list_adapters()}
        _check({"opencode", "command", "native"} <= runtimes, "opencode is one adapter, not the only one")
        _check({"claude-code", "remote"} <= runtimes, "P11 additional adapters present (claude-code, remote)")
        _check(wa.contract()["runtimes"] == [a["runtime"] for a in wa.list_adapters()],
               "contract runtimes match the adapter set")

        ad = wa.resolve("command")
        wid = ad.register("project", _PROJ, capabilities=["python"])["worker_id"]
        _check(bool(wid), "adapter register -> worker_id")
        _check(ad.accept_assignment("project", _PROJ, wid, "ASG-1")["status"] == "BUSY", "accept -> BUSY")
        wt = os.path.join(str(_PRODUCTS), _PROJ, "wt")
        os.makedirs(wt, exist_ok=True)
        out = ad.start("project", _PROJ, wid, worktree=wt, command=[sys.executable, "-c", "print('ok')"])
        _check(out["ok"] and out["status"] == "pr_ready", "start -> pr_ready")
        _check(ad.report_result("project", _PROJ, wid, {"task_id": "BI-X"})["status"] == "IDLE", "report -> IDLE")

        nat = wa.resolve("native").start("project", _PROJ, "w", "", "")
        _check(nat["status"] == "native", "native declared (agents not routed through workers)")

        # P11: remote worker is pull-based - start dispatches, never spawns a local process
        rw = wa.resolve("remote")
        rwid = rw.register("project", _PROJ, capabilities=["python"])["worker_id"]
        _check(rw.available() is True, "remote adapter is endpoint-based (available)")
        d = rw.start("project", _PROJ, rwid, objective="do work", assignment_id="ASG-2")
        _check(d["ok"] and d["status"] == "dispatched", "remote start -> dispatched")
        _check(rw.get_status("project", _PROJ, rwid).get("status") == "BUSY",
               "remote dispatch marks the worker BUSY")

        # P11: claude-code is an optional client - it degrades to BLOCKED when the CLI is absent
        cc = wa.resolve("claude-code")
        _check(isinstance(cc.available(), bool), "claude-code availability is a bool")
        if not cc.available():
            cc_out = cc.start("project", _PROJ, "w", objective="x", worktree=wt)
            _check(cc_out["status"] == "blocked", "claude-code degrades to BLOCKED when absent")
    finally:
        _clean()

    if FAILS:
        print("adapters: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("adapters: OK (contract verbs, opencode-first, command cycle, native declared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
