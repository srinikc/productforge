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
from datetime import datetime
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


_PLACEHOLDER_PATHS = {"", "not specified", "not specified.", "tbd", "n/a", "na", "none", "-", "unknown"}


def _real_paths(raw) -> list:
    """Drop placeholder/non-path values (e.g. '(derived) TBD', 'Not specified.') so they never cause false
    path-overlap contention (BI-PF-0454/0966)."""
    out = []
    for p in raw:
        s = str(p).strip()
        if not s or s.startswith("(derived)") or s.lower() in _PLACEHOLDER_PATHS:
            continue
        out.append(s)
    return out


def _paths(task: dict[str, Any]) -> list[str]:
    return _real_paths([str(p) for p in (task.get("allowed_paths") or [])]
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


_AGING_HOURS = float(os.getenv("PIPELINE_PRIORITY_AGING_HOURS", "24") or "24")


def _age_boost(task: dict[str, Any]) -> int:
    """Anti-starvation: a long-waiting item gains priority (bounded to 3 levels), so a low-priority item
    eventually runs even under sustained higher-priority load. ``PIPELINE_PRIORITY_AGING_HOURS=0`` disables."""
    if _AGING_HOURS <= 0:
        return 0
    try:
        c = task.get("created_at")
        if not c:
            return 0
        age_h = (datetime.now() - datetime.fromisoformat(str(c))).total_seconds() / 3600.0
        return min(3, max(0, int(age_h // _AGING_HOURS)))
    except Exception:
        return 0


def _rank(task: dict[str, Any]):
    pr = _PRIORITY_RANK.get(str(task.get("priority") or "P2"), 2)
    return (max(0, pr - _age_boost(task)),
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
    return _real_paths([str(p) for p in (item.get("allowed_paths") or [])]
                       + [str(p) for p in (item.get("affected_files") or [])]
                       + [str(p) for p in (item.get("affected_components") or [])])


def _requires(item: dict[str, Any]) -> list[str]:
    """The blocking prerequisites of an item (A6.4 direction).

    Structured ``dependencies[]`` first (only ``REQUIRES`` blocks; ``BLOCKS``/``RELATED`` do not), else flat
    ``deps[]``; ``blocked_by[]`` always blocks. Deduped, order-free. Single source for ``eligible`` + waves.
    """
    structured = item.get("dependencies") or []
    if structured:
        deps = [str(d.get("task_id")) for d in structured
                if isinstance(d, dict) and str(d.get("type") or "REQUIRES").upper() == "REQUIRES"]
    else:
        deps = [str(d) for d in (item.get("deps") or [])]
    deps += [str(d) for d in (item.get("blocked_by") or [])]
    return list(dict.fromkeys(d for d in deps if d))


def _epic_children(items: list[dict[str, Any]], epic_id: str | None) -> list[dict[str, Any]]:
    """Items that belong to an epic (``epic``/``parent`` == epic_id); all items when no epic is given."""
    e = str(epic_id or "")
    if not e:
        return items
    return [i for i in items if str(i.get("epic") or i.get("parent") or "") == e]


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
    # BI-PF-0446: an Epic is a container (children carry the work) - never directly executable
    if backlog.is_epic(item):
        reasons.append("epic container (children carry the work; not directly executable)")
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

    # dependencies (structured first, then flat deps); unknown refs block (fail-closed).
    # Direction (A6.4): REQUIRES X = THIS item waits on X (blocks it if X isn't terminal).
    # BLOCKS X = this item is a prerequisite for X (X waits on THIS) -> it does NOT block this item.
    # RELATED = advisory association -> never blocks.
    deps = _requires(item)
    if by_id is not None:
        for d in deps:
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
                     stage: str | None = None, epic: str | None = None) -> dict[str, Any]:
    """Eligibility view over the canonical backlog (read-only).

    ``epic=<id>`` scopes the view to that epic's children (the work carriers); dependencies still resolve
    against the FULL item set, so a child whose prerequisite lives outside the epic is judged correctly.
    """
    from core import backlog
    items = backlog.list_open(scope, project, order=False)
    # Include CLOSED items so dependencies on completed items are recognized as satisfied (see next_eligible).
    by_id = {str(i.get("id")): i for i in items}
    with contextlib.suppress(Exception):
        by_id.update({str(i.get("id")): i for i in backlog.list_closed(scope, project)})
    # active = items already assigned/executing (for contention)
    active = [i for i in items if str((i.get("execution") or {}).get("worker_id") or "")]
    view = _epic_children(items, epic)
    rows = []
    for it in view:
        e = eligible(it, by_id=by_id, worker=worker, active=active, stage=stage)
        e["title"] = it.get("title")
        e["priority_rank"] = it.get("priority_rank")
        rows.append(e)
    ready = [r for r in rows if r["ok"]]
    return {"scope": scope, "project": project or "", "epic": str(epic or ""), "total": len(rows),
            "eligible": len(ready), "blocked": len(rows) - len(ready), "items": rows}


def _dedup_threshold() -> float:
    """Near-duplicate Jaccard threshold for the claim-time dedup guard (BI-PF-0422)."""
    try:
        from core import env_flags
        return float(env_flags.get("PF_DEDUP_THRESHOLD", "0.6") or 0.6)
    except Exception:
        return 0.6


def _near_duplicate(item: dict[str, Any], others: list[dict[str, Any]]) -> bool:
    """True if ``item`` near-duplicates any item in ``others`` (Jaccard >= threshold). BI-PF-0422."""
    from core import backlog
    try:
        toks = backlog._tokens(backlog._item_text(item))
    except Exception:
        return False
    th = _dedup_threshold()
    for o in others:
        if str(o.get("id")) == str(item.get("id")):
            continue
        with contextlib.suppress(Exception):
            if backlog._similarity(toks, backlog._tokens(backlog._item_text(o))) >= th:
                return True
    return False


def next_eligible(scope: str = "product_forge", project: str | None = None,
                  worker: dict[str, Any] | None = None,
                  stage: str | None = None, epic: str | None = None) -> dict[str, Any]:
    """Highest-priority eligible item + the pickup contract (the PF-side claim handoff).

    WorkerGrid (ADR-0002) owns registry/lease, so a claim now passes through HERE: stale analyses
    are refreshed first (BI-PF-0389) so pickup never serves a stale design, then the PIDL
    pre-dispatch context (BI-PF-0379, read-only) the worker carries is attached. The caller
    (WorkerGrid ``POST /work``) takes the lease on its side and hands ``pidl_context`` +
    ``execution_policy`` to the worker.

    ``stage="execute"`` (BI-PF-0416) excludes already-executed items (``implemented``/``verifying``)
    so the worker claim path cannot re-run executed work.

    ``epic=<id>`` restricts selection to that epic's children (deps still resolve against the full set).
    """
    from core import backlog
    # BI-PF-0389: re-analyze stale items against the current architecture before pickup
    # (bounded, offline-safe; stale items are otherwise ineligible).
    with contextlib.suppress(Exception):
        from core import grooming
        grooming.refresh_stale(scope, project or None, limit=5)
    items = backlog.list_open(scope, project, order=False)
    # Include CLOSED items in the dependency map so a dependency on a completed item is recognized as
    # satisfied; building it from open items only made every completed dependency read as unmet (fail-closed).
    by_id = {str(i.get("id")): i for i in items}
    with contextlib.suppress(Exception):
        by_id.update({str(i.get("id")): i for i in backlog.list_closed(scope, project)})
    active = [i for i in items if str((i.get("execution") or {}).get("worker_id") or "")]
    candidates = _epic_children(items, epic)
    ok = [i for i in candidates
          if eligible(i, by_id=by_id, worker=worker, active=active, stage=stage)["ok"]]
    if not ok:
        return {"scope": scope, "project": project or "", "epic": str(epic or ""),
                "found": False, "item": None}
    ordered = backlog.order_by_priority(ok)
    top = ordered[0]
    if stage == "execute":
        # BI-PF-0422: skip a near-duplicate candidate so at most one of a duplicate set RUNS.
        # An item is skipped when it near-duplicates an ACTIVE item or a HIGHER-RANKED open item.
        blockers = list(active)
        top = None
        for cand in ordered:
            if _near_duplicate(cand, blockers):
                blockers.append(cand)
                continue
            top = cand
            break
        if top is None:
            return {"scope": scope, "project": project or "", "epic": str(epic or ""),
                    "found": False, "item": None}
    out: dict[str, Any] = {"scope": scope, "project": project or "", "epic": str(epic or ""),
                           "found": True, "item": top.get("id"), "title": top.get("title"),
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


def _waves(children: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Dependency wave per child: 0 = no unmet prerequisite, else 1 + max(prereq wave) within the set.

    A prereq that is already terminal is satisfied and does not push the wave out; a prereq outside the epic
    set that is still unmet counts as an external blocker (wave >= 1) so the child is shown waiting.
    """
    from core import backlog
    ids = {str(c.get("id")): c for c in children}
    memo: dict[str, int] = {}

    def wave(cid: str, stack: frozenset) -> int:
        if cid in memo:
            return memo[cid]
        if cid in stack or cid not in ids:
            return 0
        w = 0
        for d in _requires(ids[cid]):
            dep = by_id.get(d)
            if dep is not None and backlog._normalize_status(str(dep.get("status") or "")) in _TERMINAL_STATUSES:
                continue
            w = max(w, 1 + wave(d, stack | {cid})) if d in ids else max(w, 1)
        memo[cid] = w
        return w

    return {cid: wave(cid, frozenset()) for cid in ids}


def epic_order(scope: str = "product_forge", project: str | None = None,
               epic: str = "", stage: str | None = None, save: bool = False) -> dict[str, Any]:
    """Execution order of an epic's OPEN children: dependency wave -> priority, with READY/wait status.

    Read-only by default. Wave 0 items have no unmet prerequisite and come first; each further wave unlocks
    after the prior one. ``status`` is READY when the child is eligible now (``eligible()``), else ``wait``
    with the blocking reasons. Dependencies resolve against the FULL backlog (open + closed), so prerequisites
    outside the epic are still honored (an unmet external prereq shows the child waiting).

    ``save=True`` persists the computed order onto the epic as ``execution_order[]`` (delegated to
    ``core.backlog.set_execution_order`` - the single writer; scheduler itself owns no state). ``children[]``
    (membership) is never touched.
    """
    from core import backlog
    op = backlog.list_open(scope, project, order=False)
    cl = backlog.list_closed(scope, project)
    by_id = {str(i.get("id")): i for i in op}
    by_id.update({str(i.get("id")): i for i in cl})
    children = _epic_children(op, epic)
    active = [i for i in op if str((i.get("execution") or {}).get("worker_id") or "")]
    waves = _waves(children, by_id)
    rows = []
    for c in backlog.order_by_priority(children):
        cid = str(c.get("id"))
        e = eligible(c, by_id=by_id, active=active, stage=stage)
        rows.append({"id": cid, "title": c.get("title"), "wave": waves.get(cid, 0),
                     "status": "READY" if e["ok"] else "wait", "reasons": e["reasons"],
                     "priority": c.get("priority"), "priority_rank": c.get("priority_rank")})
    rows.sort(key=lambda r: r["wave"])  # stable: priority order preserved within each wave
    epic_item = backlog.get_epic(scope, project, str(epic)) if epic else None
    ready = sum(1 for r in rows if r["status"] == "READY")
    out: dict[str, Any] = {"scope": scope, "project": project or "", "epic": str(epic or ""),
                           "title": (epic_item or {}).get("title", ""),
                           "counts": {"total": len(rows), "ready": ready, "wait": len(rows) - ready,
                                      "waves": (max(r["wave"] for r in rows) + 1) if rows else 0},
                           "saved": False, "items": rows}
    if save and epic:
        with contextlib.suppress(Exception):
            out["saved"] = backlog.set_execution_order(scope, project, str(epic), rows) is not None
    return out


def _is_closed_item(item: dict[str, Any]) -> bool:
    from core import backlog
    return backlog._normalize_status(str(item.get("status") or "")) in _TERMINAL_STATUSES


def _analysis_state(item: dict[str, Any]) -> tuple[str, bool, bool]:
    """(analysis_status, groomed, needs_reanalysis): ``groomed`` == COMPLETE and not stale."""
    from core import backlog
    a = str((item.get("analysis") or {}).get("status") or "NOT_ANALYZED")
    try:
        stale = bool(backlog.analysis_is_stale(item))
    except Exception:
        stale = False
    groomed = a == "COMPLETE" and not stale
    return a, groomed, (not groomed)


def _child_row(c: dict[str, Any], *, state: str, wave, order_rank, order_status,
               reasons: list, normal_status: str) -> dict[str, Any]:
    an, groomed, needs = _analysis_state(c)
    return {"id": str(c.get("id")), "title": c.get("title"), "state": state,
            "status": normal_status, "analysis_status": an, "groomed": groomed,
            "needs_reanalysis": needs, "ready": bool((c.get("readiness") or {}).get("ready")),
            "worker_id": str((c.get("execution") or {}).get("worker_id") or ""),
            "priority": c.get("priority"), "priority_rank": c.get("priority_rank"),
            "wave": wave, "order_rank": order_rank, "order_status": order_status, "reasons": reasons}


def _time_rollup(items: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate recorded run durations (``execution.duration_seconds``) over items. BI-PF-1237."""
    durs = [int((i.get("execution") or {}).get("duration_seconds") or 0) for i in items]
    durs = [d for d in durs if d > 0]
    return {"tracked": len(durs), "total_seconds": sum(durs),
            "avg_seconds": round(sum(durs) / len(durs)) if durs else 0,
            "max_seconds": max(durs) if durs else 0}


def epic_status(scope: str = "product_forge", project: str | None = None,
                epic: str = "", stage: str | None = None) -> dict[str, Any]:
    """Full lifecycle status of an epic: ALL children (open + closed) + an epic rollup (read-only).

    Each child carries: ``state`` (open|closed), normalized ``status``, ``groomed`` (analysis COMPLETE and not
    stale), ``needs_reanalysis``, ``ready``, assigned ``worker_id``, dependency ``wave``, execution
    ``order_rank`` and ``order_status`` (READY/wait/closed) + eligibility ``reasons``. ``order`` lists the open
    children in execution order; ``execution_order`` echoes the last saved order on the epic (BI-PF-1222).
    """
    from core import backlog
    op = backlog.list_open(scope, project, order=False)
    cl = backlog.list_closed(scope, project)
    by_id = {str(i.get("id")): i for i in op}
    by_id.update({str(i.get("id")): i for i in cl})
    children = backlog._children_of(op, cl, str(epic))
    active = [i for i in op if str((i.get("execution") or {}).get("worker_id") or "")]
    open_kids = [c for c in children if not _is_closed_item(c)]
    closed_kids = [c for c in children if _is_closed_item(c)]
    waves = _waves(open_kids, by_id)
    ordered = backlog.order_by_priority(open_kids)
    ordered.sort(key=lambda c: waves.get(str(c.get("id")), 0))  # stable within a wave
    rank = {str(c.get("id")): i + 1 for i, c in enumerate(ordered)}
    rows: list[dict[str, Any]] = []
    for c in ordered:
        cid = str(c.get("id"))
        e = eligible(c, by_id=by_id, active=active, stage=stage)
        rows.append(_child_row(c, state="open", wave=waves.get(cid, 0), order_rank=rank.get(cid),
                               order_status="READY" if e["ok"] else "wait", reasons=e["reasons"],
                               normal_status=backlog._normalize_status(str(c.get("status") or ""))))
    for c in backlog.order_by_priority(closed_kids):
        rows.append(_child_row(c, state="closed", wave=None, order_rank=None, order_status="closed",
                               reasons=[], normal_status=backlog._normalize_status(str(c.get("status") or ""))))
    epic_item = backlog.get_epic(scope, project, str(epic)) if epic else None
    groomed = sum(1 for r in rows if r["state"] == "open" and r["groomed"])
    needs = sum(1 for r in rows if r["state"] == "open" and r["needs_reanalysis"])
    ready = sum(1 for r in rows if r["order_status"] == "READY")
    open_n = len(open_kids)
    return {"scope": scope, "project": project or "", "epic": str(epic or ""),
            "title": (epic_item or {}).get("title", ""),
            "rollup": {"total": len(rows), "open": open_n, "closed": len(closed_kids),
                       "groomed": groomed, "need_reanalysis": needs, "ready": ready,
                       "wait": open_n - ready, "done": bool(rows) and open_n == 0,
                       "time": _time_rollup(children)},
            "order": [r["id"] for r in rows if r["state"] == "open"],
            "execution_order": (epic_item or {}).get("execution_order") or [],
            "children": rows}


def _standalone_row(it: dict[str, Any], *, by_id, active, stage) -> dict[str, Any]:
    from core import backlog
    an, groomed, needs = _analysis_state(it)
    e = eligible(it, by_id=by_id, active=active, stage=stage)
    return {"id": str(it.get("id")), "title": it.get("title"), "state": "open",
            "status": backlog._normalize_status(str(it.get("status") or "")),
            "analysis_status": an, "groomed": groomed, "needs_reanalysis": needs,
            "ready": bool((it.get("readiness") or {}).get("ready")),
            "worker_id": str((it.get("execution") or {}).get("worker_id") or ""),
            "priority": it.get("priority"), "priority_rank": it.get("priority_rank"),
            "order_status": "READY" if e["ok"] else "wait", "reasons": e["reasons"]}


def backlog_status(scope: str = "product_forge", project: str | None = None,
                   stage: str | None = None) -> dict[str, Any]:
    """Scope-level status: every epic with a rollup + open standalone items (read-only).

    Rollup keys: items/open/closed, epics/epics_open, children_open/children_closed, groomed,
    need_reanalysis, ready, wait, standalone_open, standalone_ready.
    """
    from core import backlog
    op = backlog.list_open(scope, project, order=False)
    cl = backlog.list_closed(scope, project)
    epics = [it for it in (op + cl) if backlog.is_epic(it)]
    by_id = {str(i.get("id")): i for i in op}
    by_id.update({str(i.get("id")): i for i in cl})
    active = [i for i in op if str((i.get("execution") or {}).get("worker_id") or "")]
    agg = {"items": len(op) + len(cl), "open": len(op), "closed": len(cl),
           "epics": len(epics), "epics_open": 0, "children_open": 0, "children_closed": 0,
           "groomed": 0, "need_reanalysis": 0, "ready": 0, "wait": 0,
           "standalone_open": 0, "standalone_ready": 0}
    epic_rows = []
    for e in backlog.order_by_priority(epics):
        st = epic_status(scope, project, str(e.get("id")), stage=stage)
        r = st["rollup"]
        if r["open"] > 0:
            agg["epics_open"] += 1
        for k, src in (("children_open", "open"), ("children_closed", "closed"), ("groomed", "groomed"),
                       ("need_reanalysis", "need_reanalysis"), ("ready", "ready"), ("wait", "wait")):
            agg[k] += r[src]
        epic_rows.append({"id": str(e.get("id")), "title": e.get("title"), "rollup": r})
    standalone = [it for it in op if not str(it.get("epic") or it.get("parent") or "")]
    arows = [_standalone_row(it, by_id=by_id, active=active, stage=stage)
             for it in backlog.order_by_priority(standalone)]
    agg["standalone_open"] = len(standalone)
    agg["standalone_ready"] = sum(1 for r in arows if r["order_status"] == "READY")
    agg["time"] = _time_rollup(op + cl)
    return {"scope": scope, "project": project or "", "rollup": agg,
            "epics": epic_rows, "standalone": arows}


def backlog_status_all(stage: str | None = None) -> dict[str, Any]:
    """Status across ALL backlogs/scopes (product_forge + every project); read-only (BI-PF-1222)."""
    from core import backlog
    scopes = []
    for sc, pr in backlog._all_scopes():
        with contextlib.suppress(Exception):
            st = backlog_status(sc, pr, stage=stage)
            scopes.append({"scope": sc, "project": pr or "", "rollup": st["rollup"], "epics": st["epics"]})
    return {"count": len(scopes), "scopes": scopes}
