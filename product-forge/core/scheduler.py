"""ENG-2: work planner & parallel scheduler over ENG-1 task contracts.

Pure planning capability — no execution and no store writes (execution is ENG-4). This module decides
*what runs on what*: task discovery, dependency graph (+ cycle detection), prioritization, capability
matching, file-overlap detection, and elastic assignment of ready tasks to declared worker slots
(``K <= N``, never a fixed worker count).

Scheduling is a read-only derivation from the task-contract store (owner: ``core/task_contract.py``) plus
the declared worker pool (``config/engineering-workers.json``). It creates no second queue and owns no state.
"""
import fnmatch
import json
import os
from typing import Any, Dict, List, Optional

from core.paths import ROOT

FILENAME = "engineering-workers.json"
_PATH = os.path.join(ROOT, "config", FILENAME)
TERMINAL = ("done", "cancelled")
SCHEDULABLE = ("ready",)
_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
_RISK_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def workers() -> Dict[str, Any]:
    """The declared worker pool registry (config)."""
    try:
        with open(_PATH, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def worker_slots(reg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Expand the pool into concrete worker slots (enabled types x count)."""
    reg = reg if reg is not None else workers()
    default_conc = int((reg.get("defaults") or {}).get("max_concurrency") or 1)
    slots: List[Dict[str, Any]] = []
    for w in (reg.get("workers") or []):
        if not w.get("enabled", True):
            continue
        n = max(1, int(w.get("count") or 1))
        for i in range(1, n + 1):
            slots.append({"slot_id": f"{w.get('id')}-{i}", "worker_id": w.get("id"),
                          "type": str(w.get("type") or w.get("id") or ""),
                          "capabilities": [str(c) for c in (w.get("capabilities") or [])],
                          "max_concurrency": max(1, int(w.get("max_concurrency") or default_conc))})
    return slots


def _paths(task: Dict[str, Any]) -> List[str]:
    return ([str(p) for p in (task.get("allowed_paths") or [])]
            + [str(p) for p in (task.get("affected_files") or [])])


def path_overlap(a: List[str], b: List[str]) -> bool:
    """True if two path lists share a file, a directory prefix, or a glob match."""
    for x in a:
        for y in b:
            x2, y2 = x.rstrip("/"), y.rstrip("/")
            if not x2 or not y2:
                continue
            if x2 == y2 or x2.startswith(y2 + "/") or y2.startswith(x2 + "/"):
                return True
            if fnmatch.fnmatch(x2, y2) or fnmatch.fnmatch(y2, x2):
                return True
    return False


def capability_match(task: Dict[str, Any], slot: Dict[str, Any]) -> bool:
    """A task can run on a slot only if its required capabilities/type are all satisfied."""
    caps = [str(c) for c in (slot.get("capabilities") or [])]
    wildcard = "*" in caps
    req = [str(c) for c in (task.get("required_capabilities") or [])]
    if req and not wildcard:
        for c in req:
            if not any(cap == c or fnmatch.fnmatch(c, cap) for cap in caps):
                return False
    wt = str(task.get("required_worker_type") or "")
    if wt and not wildcard and wt not in (slot.get("type"), slot.get("worker_id")):
        return False
    return True


def dependency_graph(tasks: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    g: Dict[str, List[str]] = {}
    for t in tasks:
        deps = [str(d) for d in (t.get("dependencies") or [])] + [str(d) for d in (t.get("blocked_by") or [])]
        g[str(t.get("task_id") or "")] = sorted({d for d in deps if d})
    return g


def find_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
    """DFS cycle detection over the dependency graph (edges = depends-on)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    cycles: List[List[str]] = []
    stack: List[str] = []

    def dfs(n: str) -> None:
        color[n] = GRAY
        stack.append(n)
        for m in graph.get(n, []):
            if m not in color:
                continue  # external/unknown ref: not a cycle
            if color[m] == GRAY:
                i = stack.index(m)
                cycles.append(stack[i:] + [m])
            elif color[m] == WHITE:
                dfs(m)
        stack.pop()
        color[n] = BLACK

    for n in list(graph):
        if color[n] == WHITE:
            dfs(n)
    return cycles


def _unmet_deps(task: Dict[str, Any], by_id: Dict[str, Dict[str, Any]]) -> List[str]:
    """Dependencies not yet terminal. Unknown refs block (fail-closed)."""
    deps = [str(d) for d in (task.get("dependencies") or [])] + [str(d) for d in (task.get("blocked_by") or [])]
    out: List[str] = []
    for d in deps:
        if not d:
            continue
        dep = by_id.get(d)
        if dep is None or str(dep.get("status")) not in TERMINAL:
            out.append(d)
    return out


def _rank(task: Dict[str, Any]):
    return (_PRIORITY_RANK.get(str(task.get("priority") or "P2"), 2),
            _RISK_RANK.get(str(task.get("risk") or "medium"), 2),
            str(task.get("created_at") or ""))


def plan(scope: str = "product_forge", project: Optional[str] = None,
         tasks: Optional[List[Dict[str, Any]]] = None,
         slots: Optional[List[Dict[str, Any]]] = None,
         schedulable: tuple = SCHEDULABLE) -> Dict[str, Any]:
    """Elastic wave plan: assign ready, capability-matched, non-overlapping tasks to free slots."""
    if tasks is None:
        from core import task_contract
        tasks = task_contract.list_tasks(scope, project)
    if slots is None:
        slots = worker_slots()

    by_id = {str(t.get("task_id")): t for t in tasks}
    graph = dependency_graph(tasks)
    cycles = find_cycles(graph)
    cyc_nodes = {n for c in cycles for n in c}

    slot_tasks: Dict[str, List[str]] = {s["slot_id"]: [] for s in slots}
    assignments: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    occupied: List[tuple] = []

    candidates = [t for t in tasks
                  if str(t.get("status")) in schedulable and str(t.get("task_id")) not in cyc_nodes]
    candidates.sort(key=_rank)

    for t in candidates:
        tid = str(t.get("task_id"))
        unmet = _unmet_deps(t, by_id)
        if unmet:
            blocked.append({"task_id": tid, "blocked_by": unmet})
            continue
        paths = _paths(t)
        chosen = next((s for s in slots
                       if len(slot_tasks[s["slot_id"]]) < int(s.get("max_concurrency") or 1)
                       and capability_match(t, s)), None)
        if chosen is None:
            deferred.append({"task_id": tid, "reason": "no matching worker"})
            continue
        clash = next((o for o in occupied if path_overlap(paths, o[1])), None)
        if clash is not None:
            deferred.append({"task_id": tid, "reason": f"file overlap with {clash[0]}"})
            continue
        slot_tasks[chosen["slot_id"]].append(tid)
        occupied.append((tid, paths))
        assignments.append({"task_id": tid, "slot_id": chosen["slot_id"],
                            "worker_id": chosen["worker_id"], "priority": t.get("priority"),
                            "risk": t.get("risk"), "paths": paths})

    utilized = sum(1 for s in slots if slot_tasks[s["slot_id"]])
    return {
        "scope": scope, "project": project or "",
        "workers": [{"slot_id": s["slot_id"], "worker_id": s["worker_id"], "type": s["type"],
                     "capabilities": s["capabilities"], "max_concurrency": s["max_concurrency"]}
                    for s in slots],
        "assignments": assignments, "deferred": deferred, "blocked": blocked,
        "cycles": cycles, "graph": graph,
        "counts": {"tasks": len(tasks), "candidates": len(candidates), "assigned": len(assignments),
                   "deferred": len(deferred), "blocked": len(blocked),
                   "slots": len(slots), "utilized": utilized,
                   "capacity": sum(int(s.get("max_concurrency") or 1) for s in slots)},
    }


def report(scope: str = "product_forge", project: Optional[str] = None) -> Dict[str, Any]:
    """Task-contract status roll-up (planning input / progress)."""
    from core import task_contract
    tasks = task_contract.list_tasks(scope, project)
    by_status: Dict[str, int] = {}
    for t in tasks:
        s = str(t.get("status") or "?")
        by_status[s] = by_status.get(s, 0) + 1
    return {"scope": scope, "project": project or "", "total": len(tasks), "by_status": by_status}
