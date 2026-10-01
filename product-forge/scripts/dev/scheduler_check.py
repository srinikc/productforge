"""ENG-2 gate: the planner/scheduler is exercised deterministically (no store writes).

Scenarios: dependency blocking, capability matching (incl. wildcard), file-overlap exclusion, cycle
detection, and the elastic invariant ``K <= N``. Run: ``python scripts/dev/scheduler_check.py`` (in precheck).
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


def _task(tid, status="ready", pri="P2", risk="low", deps=None, paths=None, caps=None, wt=""):
    return {"task_id": tid, "status": status, "priority": pri, "risk": risk,
            "dependencies": deps or [], "blocked_by": [], "allowed_paths": paths or [],
            "affected_files": [], "required_capabilities": caps or [], "required_worker_type": wt}


def main() -> int:
    from core import scheduler
    py = {"slot_id": "py-1", "worker_id": "py", "type": "local-agent",
          "capabilities": ["python"], "max_concurrency": 1}
    py2 = {"slot_id": "py-2", "worker_id": "py", "type": "local-agent",
           "capabilities": ["python"], "max_concurrency": 1}
    human = {"slot_id": "h-1", "worker_id": "human", "type": "human",
             "capabilities": ["*"], "max_concurrency": 2}

    # 1) dependency blocking + capability mismatch
    p = scheduler.plan(tasks=[_task("T1", pri="P1", paths=["src/a.py"], caps=["python"]),
                              _task("T2", pri="P0", deps=["T1"], paths=["src/b.py"], caps=["python"]),
                              _task("T3", pri="P2", paths=["src/c.rs"], caps=["rust"])],
                       slots=[py])
    _check({a["task_id"] for a in p["assignments"]} == {"T1"}, "dep/cap: expected only T1 assigned")
    _check(any(b["task_id"] == "T2" and b["blocked_by"] == ["T1"] for b in p["blocked"]), "T2 blocked by T1")
    _check(any(d["task_id"] == "T3" and "worker" in d["reason"] for d in p["deferred"]),
           "T3 deferred (no matching worker)")
    _check(p["counts"]["assigned"] <= p["counts"]["capacity"], "K <= capacity (case 1)")

    # 2) file-overlap exclusion
    p = scheduler.plan(tasks=[_task("O1", paths=["src/x.py"], caps=["python"]),
                              _task("O2", paths=["src/x.py"], caps=["python"])],
                       slots=[py, py2])
    _check(len(p["assignments"]) == 1, "overlap: only one of O1/O2 assigned")
    _check(any("overlap" in d["reason"] for d in p["deferred"]), "overlap deferred reason")

    # 3) cycle detection
    p = scheduler.plan(tasks=[_task("C1", deps=["C2"]), _task("C2", deps=["C1"])], slots=[py])
    _check(bool(p["cycles"]), "cycle detected")
    _check(not p["assignments"], "cyclic tasks not scheduled")

    # 4) wildcard worker + non-ready exclusion
    p = scheduler.plan(tasks=[_task("W1", caps=["rust"], wt="human")], slots=[human])
    _check({a["task_id"] for a in p["assignments"]} == {"W1"}, "wildcard worker matches required capability")
    p = scheduler.plan(tasks=[_task("D1", status="draft", caps=["python"])], slots=[py])
    _check(not p["assignments"], "non-ready (draft) task not scheduled")

    if FAILS:
        print("scheduler: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("scheduler: OK (deps, cycles, capability, overlap, K<=N)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
