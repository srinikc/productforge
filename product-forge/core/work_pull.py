"""PFSSOT-P8 (BI-PF-0369): manual work pull - the first end-to-end milestone.

A worker (or operator) asks for work; the scheduler picks the highest eligible backlog item, claims it with
a lease, and returns a canonical **assignment package**. This composes the already-built owners - it adds
NO engine and NO store:

    worker_registry (P6) -> scheduler.next_eligible (P4) -> job_manager.claim_next (P5)
      -> worker_adapters.accept_assignment (P7) -> assignment package (+ execution_contract shape)

The worker receives a **minimal, canonical** task package (doc §34): identity/revision, requirement,
priority, deps, the STORED analysis/design (so pickup is execution, not re-architecture), relevant
components/APIs, constraints, and validation requirements. Not the whole knowledge base.

Workers only - PF agents are never routed here (doc §23).
"""
import contextlib
from typing import Any


def _task_package(scope: str, project: str | None, item_id: str) -> dict[str, Any]:
    """Build the minimal worker task package from the canonical backlog item (doc §34)."""
    from core import backlog
    it = backlog.get_epic(scope, project, item_id) or {}
    an = it.get("analysis") or {}
    return {
        "item_id": it.get("id"), "revision": int(it.get("revision") or 0),
        "title": it.get("title"), "requirement": it.get("body") or "",
        "priority": it.get("priority"), "priority_rank": it.get("priority_rank"),
        "moscow": it.get("moscow"), "type": it.get("type"),
        "dependencies": it.get("dependencies") or [], "deps": it.get("deps") or [],
        "analysis": {  # stored design/architecture context (P1/P3) - no re-architecting at pickup
            "status": an.get("status"), "architecture_fit": an.get("architecture_fit"),
            "implementation_strategy": an.get("implementation_strategy"),
            "existing_components": an.get("existing_components") or [],
            "existing_apis": an.get("existing_apis") or [],
            "drift": an.get("drift"), "risks": an.get("risks") or [],
            "acceptance_criteria": it.get("acceptance_criteria") or [],
            "test_requirements": it.get("test_requirements") or [],
        },
        "constraints": {"allowed_paths": it.get("allowed_paths") or [],
                        "restricted_paths": it.get("restricted_paths") or []},
    }


def _package(scope: str, project: str | None, item_id: str, worker_id: str, runtime: str,
             claim: dict[str, Any]) -> dict[str, Any]:
    """Canonical assignment package handed to the worker (doc §34/§13/§38)."""
    from core import execution_contract
    tp = _task_package(scope, project, item_id)
    # deliverables: test requirements, else acceptance criteria, else the item title (never empty ->
    # the contract is valid for a real assignment; a genuinely empty task is a data problem, not a block here)
    deliverables = (list(tp["analysis"].get("test_requirements") or [])
                    or list(tp["analysis"].get("acceptance_criteria") or [])
                    or [str(tp.get("title") or item_id)])
    # reuse the contract shape for the enforceable envelope (permissions/limits/verification/recovery)
    contract = execution_contract.build(
        project=str(project or scope), run_id=str(claim.get("project") or item_id),
        stage_id="work", agent_id=str(worker_id),
        objective=str(tp.get("requirement") or tp.get("title") or item_id),
        deliverables=deliverables,
        permissions={"workspace": "isolated-worktree"},
        limits={}, verification={"acceptance": tp["analysis"].get("acceptance_criteria") or []},
        recovery={"idempotency_key": str(claim.get("assignment_id") or "")})
    # PIDL-4 (BI-PF-0379): pre-dispatch evaluation - attach the relevant context + execution policy
    # (advisory; read-only). This is the doc's "what the worker actually receives" (pidl_context +
    # execution_policy) - never the whole personality.
    pidl_pkg: dict[str, Any] = {}
    try:
        from core import pidl
        pd = pidl.pre_dispatch(scope, project,
                               item={"id": item_id, "title": tp.get("title"), "body": tp.get("requirement")},
                               action=str(tp.get("requirement") or tp.get("title") or ""),
                               components=tp["analysis"].get("existing_components") or [])
        pidl_pkg = {"pidl_context": pd["pidl_context"], "execution_policy": pd["execution_policy"]}
    except Exception:
        pidl_pkg = {}
    return {
        "assignment_id": claim.get("assignment_id"), "lease_id": claim.get("lease_id"),
        "lease_expires_at": claim.get("lease_expires_at"), "attempt": claim.get("attempt"),
        "worker_id": worker_id, "runtime": runtime,
        "task": tp, "contract": contract, "contract_status": execution_contract.validate(contract)["status"],
        **pidl_pkg,
    }


def pull(scope: str = "product_forge", project: str | None = None, *, worker_id: str = "",
         runtime: str = "", product: str = "") -> dict[str, Any]:
    """Manual pull: claim the next eligible item for a worker and return the assignment package.

    Worker must be registered (P6) OR pass runtime + auto-register. Returns
    ``{assigned, package|reason}``. Does NOT execute the work.
    """
    from core import job_manager, worker_adapters, worker_registry
    if not worker_registry.integration_enabled():
        return {"assigned": False, "reason": "worker integration disabled (WORKER_INTEGRATION_ENABLED=0)"}
    wid = str(worker_id or "")
    rt = str(runtime or "")
    reg = worker_registry.get(scope, project, wid) if wid else None
    if reg is None and rt:
        rec = worker_adapters.resolve(rt)
        if rec is None:
            return {"assigned": False, "reason": f"unknown runtime {rt!r}"}
        reg = rec.register(scope, project, capabilities=[], role="")
        wid = reg["worker_id"]
    if not reg:
        return {"assigned": False, "reason": "worker not registered (pass worker_id or runtime)"}
    rt = str(reg.get("runtime") or rt or "")

    # eligibility (P4) is consulted inside claim_next; atomic claim + lease (P5)
    claim = job_manager.claim_next(scope, project, worker=wid)
    if not claim.get("claimed"):
        return {"assigned": False, "reason": claim.get("reason", "no eligible item")}

    item_id = str(claim["item"])
    ad = worker_adapters.resolve(rt)
    if ad is not None:
        with contextlib.suppress(Exception):
            ad.accept_assignment(scope, project, wid, str(claim.get("assignment_id") or ""))
    return {"assigned": True, "package": _package(scope, project, item_id, wid, rt, claim)}


def start(scope: str, project: str | None, item_id: str, *, worktree: str = "",
          command: Any = None) -> dict[str, Any]:
    """Optionally invoke the assigned worker's adapter ``start`` (closes the loop e2e)."""
    from core import backlog, worker_adapters, worker_registry
    if not worker_registry.integration_enabled():
        return {"ok": False, "reason": "worker integration disabled"}
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"ok": False, "reason": "item not found"}
    ex = it.get("execution") or {}
    wid = str(ex.get("worker_id") or "")
    if not wid:
        return {"ok": False, "reason": "item is not assigned"}
    reg = worker_registry.get(scope, project, wid) or {}
    ad = worker_adapters.resolve(str(reg.get("runtime") or ""))
    if ad is None:
        return {"ok": False, "reason": "no adapter for worker runtime"}
    tp = _task_package(scope, project, item_id)
    objective = str(tp.get("requirement") or "")
    if ad.runtime == "command":
        result = ad.start(scope, project, wid, objective=objective, worktree=worktree, command=command)
    else:
        result = ad.start(scope, project, wid, objective=objective, worktree=worktree)
    return {"ok": True, "adapter": ad.runtime, "result": result}
