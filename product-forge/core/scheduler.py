"""ENG-2: work planner & parallel scheduler over ENG-1 task contracts.

Pure planning capability — no execution and no store writes (execution is ENG-4). This module decides
*what runs on what*: task discovery, dependency graph (+ cycle detection), prioritization, capability
matching, file-overlap detection, and elastic assignment of ready tasks to declared worker slots
(``K <= N``, never a fixed worker count).

Scheduling is a read-only derivation from the task-contract store (owner: ``core/task_contract.py``) plus
the declared worker pool (``config/engineering-workers.json``). It creates no second queue and owns no state.
"""
import contextlib
import fnmatch
import json
import os
from typing import Any

from core.paths import ROOT

FILENAME = "engineering-workers.json"
_PATH = os.path.join(ROOT, "config", FILENAME)
TERMINAL = ("done", "cancelled")
SCHEDULABLE = ("ready",)
_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
_RISK_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def workers() -> dict[str, Any]:
    """The declared worker pool registry (config)."""
    try:
        with open(_PATH, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def worker_slots(reg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Expand the pool into concrete worker slots (enabled types x count)."""
    reg = reg if reg is not None else workers()
    default_conc = int((reg.get("defaults") or {}).get("max_concurrency") or 1)
    slots: list[dict[str, Any]] = []
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


def _paths(task: dict[str, Any]) -> list[str]:
    return ([str(p) for p in (task.get("allowed_paths") or [])]
            + [str(p) for p in (task.get("affected_files") or [])])


def path_overlap(a: list[str], b: list[str]) -> bool:
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


def capability_match(task: dict[str, Any], slot: dict[str, Any]) -> bool:
    """A task can run on a slot only if its required capabilities/type are all satisfied."""
    caps = [str(c) for c in (slot.get("capabilities") or [])]
    wildcard = "*" in caps
    req = [str(c) for c in (task.get("required_capabilities") or [])]
    if req and not wildcard:
        for c in req:
            if not any(cap == c or fnmatch.fnmatch(c, cap) for cap in caps):
                return False
    wt = str(task.get("required_worker_type") or "")
    return not (wt and not wildcard and wt not in (slot.get("type"), slot.get("worker_id")))


def dependency_graph(tasks: list[dict[str, Any]]) -> dict[str, list[str]]:
    g: dict[str, list[str]] = {}
    for t in tasks:
        deps = [str(d) for d in (t.get("dependencies") or [])] + [str(d) for d in (t.get("blocked_by") or [])]
        g[str(t.get("task_id") or "")] = sorted({d for d in deps if d})
    return g


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """DFS cycle detection over the dependency graph (edges = depends-on)."""
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(graph, white)
    cycles: list[list[str]] = []
    stack: list[str] = []

    def dfs(n: str) -> None:
        color[n] = gray
        stack.append(n)
        for m in graph.get(n, []):
            if m not in color:
                continue  # external/unknown ref: not a cycle
            if color[m] == gray:
                i = stack.index(m)
                cycles.append(stack[i:] + [m])
            elif color[m] == white:
                dfs(m)
        stack.pop()
        color[n] = black

    for n in list(graph):
        if color[n] == white:
            dfs(n)
    return cycles


def _unmet_deps(task: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Dependencies not yet terminal. Unknown refs block (fail-closed)."""
    deps = [str(d) for d in (task.get("dependencies") or [])] + [str(d) for d in (task.get("blocked_by") or [])]
    out: list[str] = []
    for d in deps:
        if not d:
            continue
        dep = by_id.get(d)
        if dep is None or str(dep.get("status")) not in TERMINAL:
            out.append(d)
    return out


def _rank(task: dict[str, Any]):
    return (_PRIORITY_RANK.get(str(task.get("priority") or "P2"), 2),
            _RISK_RANK.get(str(task.get("risk") or "medium"), 2),
            str(task.get("created_at") or ""))


def plan(scope: str = "product_forge", project: str | None = None,
         tasks: list[dict[str, Any]] | None = None,
         slots: list[dict[str, Any]] | None = None,
         schedulable: tuple = SCHEDULABLE) -> dict[str, Any]:
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

    slot_tasks: dict[str, list[str]] = {s["slot_id"]: [] for s in slots}
    assignments: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    occupied: list[tuple] = []
    shared_in_wave = ""  # ENG-8: task currently holding shared/common code this wave

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
        # ENG-8: shared/common-code serialization (allowlist + active reservations)
        shared, holder = False, None
        try:
            from core import reservations as _resv
            shared = bool(_resv.shared_paths(paths))
            for p in paths:
                h = _resv.holder_of(p)
                if h and str(h.get("holder_task") or "") not in ("", tid):
                    holder = h
                    break
        except Exception:
            shared, holder = False, None
        if holder is not None:
            deferred.append({"task_id": tid, "reason": f"reserved by {holder.get('holder_task')}"})
            continue
        if shared and shared_in_wave:
            deferred.append({"task_id": tid, "reason": f"shared path overlap with {shared_in_wave}"})
            continue
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
        if shared:
            shared_in_wave = tid
        assignments.append({"task_id": tid, "slot_id": chosen["slot_id"],
                            "worker_id": chosen["worker_id"], "priority": t.get("priority"),
                            "risk": t.get("risk"), "paths": paths, "shared": shared})

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


def report(scope: str = "product_forge", project: str | None = None) -> dict[str, Any]:
    """Task-contract status roll-up (planning input / progress)."""
    from core import task_contract
    tasks = task_contract.list_tasks(scope, project)
    by_status: dict[str, int] = {}
    for t in tasks:
        s = str(t.get("status") or "?")
        by_status[s] = by_status.get(s, 0) + 1
    return {"scope": scope, "project": project or "", "total": len(tasks), "by_status": by_status}


# ── PFSSOT-P4 (BI-PF-0365): eligibility over the CANONICAL BACKLOG (read-only) ──
# The scheduler must answer "what can run now?" from the backlog (doc §10-§13/§31-§33), not only from
# task contracts. Eligibility is a PURE function (no writes); claim/lease is P5.
_ELIGIBLE_STATUSES = ("new", "accepted", "queued", "scheduled")  # open, not yet executing
_TERMINAL_STATUSES = ("completed", "done", "rejected", "wontfix", "duplicate", "merged", "archived")


def _item_paths(item: dict[str, Any]) -> list[str]:
    return ([str(p) for p in (item.get("allowed_paths") or [])]
            + [str(p) for p in (item.get("affected_files") or [])]
            + [str(p) for p in (item.get("affected_components") or [])])


def eligible(item: dict[str, Any], *, by_id: dict[str, dict[str, Any]] | None = None,
             worker: dict[str, Any] | None = None,
             active: list[dict[str, Any]] | None = None,
             stage: str | None = None) -> dict[str, Any]:
    """Is this backlog item executable NOW? Returns ``{ok, reasons[]}`` (fail-closed, read-only).

    Order (doc §11): status -> analysis(READY) -> dependencies -> readiness -> revision/stale ->
    contention -> capability. Any unmet reason => not eligible.

    ``stage="execute"`` (BI-PF-0416) restricts the status gate to NOT-yet-executed items
    (``new``/``accepted``/``queued``/``scheduled``); ``implemented``/``verifying`` are rejected so an
    already-executed item cannot be re-claimed and re-executed. Default (``stage=None``) keeps the
    historical gate, which also admits ``implemented``/``verifying`` for a verification stage.
    """
    from core import backlog
    reasons: list[str] = []
    eid = str(item.get("id") or "")
    st = backlog._normalize_status(str(item.get("status") or ""))
    if st in _TERMINAL_STATUSES:
        reasons.append(f"terminal status '{st}'")
    elif stage == "execute":
        if st not in _ELIGIBLE_STATUSES:
            reasons.append(f"status '{st}' not execution-eligible (already executed)")
    elif st not in _ELIGIBLE_STATUSES and st not in ("implemented", "verifying", "blocked"):
        reasons.append(f"status '{st}' not eligible")
    if st == "blocked":
        reasons.append("blocked")

    # analysis gate: READY requires COMPLETE and not STALE (doc §8); defer items are groomed at pickup
    an = item.get("analysis") or {}
    a_status = str(an.get("status") or "NOT_ANALYZED")
    if a_status != "COMPLETE":
        reasons.append(f"analysis {a_status} (needs grooming)")
    else:
        # BI-PF-0389: revalidate a COMPLETE analysis against the current architecture fingerprint
        try:
            if backlog.analysis_is_stale(item):
                reasons.append("analysis stale (architecture changed)")
        except Exception:
            pass

    # dependencies (structured first, then flat deps); unknown refs block (fail-closed)
    deps = [str(d.get("task_id")) if isinstance(d, dict) else str(d)
            for d in (item.get("dependencies") or [])] or [str(d) for d in (item.get("deps") or [])]
    deps += [str(d) for d in (item.get("blocked_by") or [])]
    if by_id is not None:
        for d in {x for x in deps if x}:
            dep = by_id.get(d)
            if dep is None or backlog._normalize_status(str(dep.get("status") or "")) not in _TERMINAL_STATUSES:
                reasons.append(f"unmet dependency {d}")

    # readiness flag
    if (item.get("readiness") or {}).get("ready") is False and (item.get("readiness") or {}).get("reasons"):
        reasons.append("readiness=false")

    # staleness is authoritative via analysis.status: core.backlog marks COMPLETE -> STALE only on a
    # requirement/architecture change (P1). Do NOT re-derive from revision numbers - priority/dep
    # bookkeeping bumps revision without invalidating the analysis.

    # already claimed / leased
    ex = item.get("execution") or {}
    if str(ex.get("worker_id") or "") and str(ex.get("completed_at") or "") == "":
        reasons.append(f"already assigned to {ex.get('worker_id')}")

    # contention vs other active items (path overlap)
    paths = _item_paths(item)
    for a in (active or []):
        if str(a.get("id")) == eid:
            continue
        if paths and path_overlap(paths, _item_paths(a)):
            reasons.append(f"path overlap with {a.get('id')}")

    # capability match against a worker slot (when provided)
    if worker is not None and not capability_match(item, worker):
        reasons.append("worker capability mismatch")

    return {"id": eid, "ok": not reasons, "reasons": reasons}


def eligible_backlog(scope: str = "product_forge", project: str | None = None,
                     worker: dict[str, Any] | None = None,
                     stage: str | None = None) -> dict[str, Any]:
    """Eligibility view over the canonical backlog (read-only)."""
    from core import backlog
    items = backlog.list_open(scope, project, order=False)
    by_id = {str(i.get("id")): i for i in items}
    # active = items already assigned/executing (for contention)
    active = [i for i in items if str((i.get("execution") or {}).get("worker_id") or "")]
    rows = []
    for it in items:
        e = eligible(it, by_id=by_id, worker=worker, active=active, stage=stage)
        e["title"] = it.get("title")
        e["priority_rank"] = it.get("priority_rank")
        rows.append(e)
    ready = [r for r in rows if r["ok"]]
    return {"scope": scope, "project": project or "", "total": len(rows),
            "eligible": len(ready), "blocked": len(rows) - len(ready), "items": rows}


def next_eligible(scope: str = "product_forge", project: str | None = None,
                  worker: dict[str, Any] | None = None,
                  stage: str | None = None) -> dict[str, Any]:
    """Highest-priority eligible item + the pickup contract (the PF-side claim handoff).

    WorkerGrid (ADR-0002) owns registry/lease, so a claim now passes through HERE: stale analyses
    are refreshed first (BI-PF-0389) so pickup never serves a stale design, then the PIDL
    pre-dispatch context (BI-PF-0379, read-only) the worker carries is attached. The caller
    (WorkerGrid ``POST /work``) takes the lease on its side and hands ``pidl_context`` +
    ``execution_policy`` to the worker.

    ``stage="execute"`` (BI-PF-0416) excludes already-executed items (``implemented``/``verifying``)
    so the worker claim path cannot re-run executed work.
    """
    from core import backlog
    # BI-PF-0389: re-analyze stale items against the current architecture before pickup
    # (bounded, offline-safe; stale items are otherwise ineligible).
    with contextlib.suppress(Exception):
        from core import grooming
        grooming.refresh_stale(scope, project or None, limit=5)
    items = backlog.list_open(scope, project, order=False)
    by_id = {str(i.get("id")): i for i in items}
    active = [i for i in items if str((i.get("execution") or {}).get("worker_id") or "")]
    ok = [i for i in items
          if eligible(i, by_id=by_id, worker=worker, active=active, stage=stage)["ok"]]
    if not ok:
        return {"scope": scope, "project": project or "", "found": False, "item": None}
    ordered = backlog.order_by_priority(ok)
    top = ordered[0]
    out: dict[str, Any] = {"scope": scope, "project": project or "", "found": True,
                           "item": top.get("id"), "title": top.get("title"),
                           "priority_rank": top.get("priority_rank")}
    # PIDL-4 (BI-PF-0379): attach the relevant context + execution policy (advisory; read-only).
    with contextlib.suppress(Exception):
        from core import pidl
        an = top.get("analysis") or {}
        pd = pidl.pre_dispatch(scope, project,
                               item={"id": str(top.get("id") or ""), "title": top.get("title"),
                                     "body": top.get("body") or ""},
                               action=str(top.get("title") or ""),
                               components=[str(c) for c in (an.get("existing_components") or [])])
        out["pidl_context"] = pd["pidl_context"]
        out["execution_policy"] = pd["execution_policy"]
    return out
