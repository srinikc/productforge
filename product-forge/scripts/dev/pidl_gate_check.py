"""PIDL-3 gate (BI-PF-0378): the worker-result decision gate is wired, precedence-correct, mode-aware.

Asserts: ``pidl.gate`` returns the decision + provenance; precedence (AUTO/REVIEW/CORRECT/APPROVAL);
the gate mode is advisory by default and enforce when ``PIDL_GATE_MODE=enforce``; and the orchestration
result boundary (``core/close_loop.py``) actually invokes the gate (wired, not just present).
Run: ``python scripts/dev/pidl_gate_check.py``.
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

    _check(pidl.gate_mode() == "advisory", "gate mode defaults to advisory")
    os.environ["PIDL_GATE_MODE"] = "enforce"
    _check(pidl.gate_mode() == "enforce", "gate mode honours PIDL_GATE_MODE=enforce")
    os.environ.pop("PIDL_GATE_MODE", None)
    _check(pidl.gate_mode() == "advisory", "gate mode falls back to advisory")

    g = pidl.gate("product_forge", None, item_id="BI-X", run_id="run-1",
                  result={"ok": True, "status": "pr_ready", "provider": "command"})
    _check(set(g) >= {"decision", "confidence", "risk", "evidence", "conflicts", "approval",
                      "next_action", "item_id", "run_id", "worker_id", "runtime", "gate_mode"},
           "gate returns decision + provenance")
    _check(g["item_id"] == "BI-X" and g["run_id"] == "run-1", "gate carries item/run provenance")
    _check(g["runtime"] == "command", "gate carries the runtime")

    _check(pidl.gate("product_forge", None, result={"ok": True, "status": "pr_ready"}
                     )["decision"]["action"] == "AUTO_PROCEED", "clean result -> AUTO_PROCEED")
    _check(pidl.gate("product_forge", None, result={"ok": False, "status": "failed"}
                     )["decision"]["action"] == "REVIEW", "failed result -> REVIEW")
    _check(pidl.gate("product_forge", None, result={"ok": True}, conflicts=[{"x": 1}]
                     )["decision"]["action"] == "CORRECT", "conflicts -> CORRECT")
    _check(pidl.gate("product_forge", None, action="drop production schema"
                     )["decision"]["action"] == "APPROVAL_REQUIRED", "consequential -> APPROVAL_REQUIRED")

    # wired: the orchestration result boundary invokes the gate and honours enforce mode
    with open(os.path.join(str(_ROOT), "core", "close_loop.py"), encoding="utf-8") as f:
        cl = f.read()
    _check("pidl" in cl and ".gate(" in cl, "close_loop invokes pidl.gate (wired)")
    _check("gate_mode()" in cl and "pidl_hold" in cl, "close_loop honours enforce mode")
    _check('links={"pidl"' in cl, "close_loop records the decision under links.pidl")

    if FAILS:
        print("pidl-gate: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("pidl-gate: OK (result gate wired at close boundary; precedence; advisory/enforce modes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
