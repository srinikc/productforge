"""Engineering architecture API (ENG-0): the requirement -> deploy flow over the API-1..API-3 contracts.

Read-model over ``core.engineering_flow`` (``config/engineering-flow.json``): each step with its canonical
owner file, the ``/api/v1`` route that exposes it, and its status (exists | partial | planned). No engine.
"""

import contextlib
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from ..auth import authenticate, require_operator, require_worker
from ..envelope import from_request
from ..errors import ApiError
from ..pagination import paginate
from . import _common

router = APIRouter(prefix="/engineering", tags=["engineering"])


def _scope_project(scope: str, project: str):
    s = str(scope or "product_forge").strip()
    p = str(project or "").strip() or None
    if s not in ("product_forge", "project"):
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project",
                       details={"scope": s})
    if s == "project" and not p:
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


def _worker_scope(scope: str, project: str):
    """BI-PF-0427: the worker/assignment path executes Product Forge's OWN backlog only (product_forge).
    Project-scope changes run through the PF pipeline (intake -> run_entry -> pipeline_executor), not a worker."""
    s, p = _scope_project(scope, project)
    if s != "product_forge":
        raise ApiError("VALIDATION_FAILED",
                       "the worker/assignment path is product_forge-only; "
                       "project changes run through the PF pipeline",
                       details={"scope": s})
    return s, p




@router.get("", dependencies=[Depends(authenticate)])
def engineering(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    return from_request(request, engineering_flow.load(), resource="engineering")


@router.get("/stages", dependencies=[Depends(authenticate)])
def stages(request: Request, phase: str = "", status: str = "",
           ctx: dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    steps: list[dict[str, Any]] = engineering_flow.flow()
    if phase:
        steps = [s for s in steps if str(s.get("phase")) == phase]
    if status:
        steps = [s for s in steps if str(s.get("status")) == status]
    return from_request(request, steps, resource="engineering")


@router.get("/stages/{stage_id}", dependencies=[Depends(authenticate)])
def stage(stage_id: str, request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    s = engineering_flow.stage(stage_id)
    if not s:
        raise ApiError("NOT_FOUND", "engineering stage not found")
    return from_request(request, s, resource="engineering", resource_id=stage_id)


@router.get("/coverage", dependencies=[Depends(authenticate)])
def coverage(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import engineering_flow
    return from_request(request, engineering_flow.coverage(), resource="engineering")


# ── PIDL-1 (BI-PF-0376): personal-intelligence context resolver (read-only; orchestration, not worker) ──

@router.get("/pidl/context", dependencies=[Depends(authenticate)])
def pidl_context(request: Request, scope: str = "product_forge", project: str = "",
                 area: str = "", components: str = "", action: str = "",
                 ctx: dict[str, Any] = Depends(authenticate)):
    """The relevant PIDL context subset for a decision point (rules/principles/preferences/lenses/policy)."""
    from core import pidl
    s, p = _scope_project(scope, project)
    comps = [c.strip() for c in str(components or "").split(",") if c.strip()]
    out = pidl.resolve_context(s, p, action=action, components=comps, area=area)
    return from_request(request, out, resource="engineering")


@router.post("/pidl/decide", dependencies=[Depends(authenticate)])
async def pidl_decide(request: Request, scope: str = "product_forge", project: str = "",
                      ctx: dict[str, Any] = Depends(authenticate)):
    """Evaluate a decision point and return the structured PIDL decision contract (read-only)."""
    from core import pidl
    s, p = _scope_project(scope, project)
    with contextlib.suppress(Exception):
        body = await request.json()
    body = body if isinstance(body, dict) else {}
    out = pidl.decide(s, p, action=str(body.get("action") or ""), area=str(body.get("area") or ""),
                      components=body.get("components") or [], result=body.get("result"),
                      conflicts=body.get("conflicts") or [], failures=int(body.get("failures") or 0),
                      escalated=bool(body.get("escalated")))
    return from_request(request, out, resource="engineering")


@router.post("/pidl/gate", dependencies=[Depends(authenticate)])
async def pidl_gate(request: Request, scope: str = "product_forge", project: str = "",
                    ctx: dict[str, Any] = Depends(authenticate)):
    """Worker-result decision gate: evaluate a finished result -> decision + provenance (read-only)."""
    from core import pidl
    s, p = _scope_project(scope, project)
    with contextlib.suppress(Exception):
        body = await request.json()
    body = body if isinstance(body, dict) else {}
    out = pidl.gate(s, p, item_id=str(body.get("item_id") or ""), run_id=str(body.get("run_id") or ""),
                    action=str(body.get("action") or ""), area=str(body.get("area") or ""),
                    components=body.get("components") or [], result=body.get("result"),
                    conflicts=body.get("conflicts") or [], failures=int(body.get("failures") or 0),
                    escalated=bool(body.get("escalated")))
    return from_request(request, out, resource="engineering")


@router.post("/pidl/pre-dispatch", dependencies=[Depends(authenticate)])
async def pidl_pre_dispatch(request: Request, scope: str = "product_forge", project: str = "",
                            ctx: dict[str, Any] = Depends(authenticate)):
    """Pre-dispatch evaluation: relevant context + execution policy for a task (read-only)."""
    from core import pidl
    s, p = _scope_project(scope, project)
    with contextlib.suppress(Exception):
        body = await request.json()
    body = body if isinstance(body, dict) else {}
    out = pidl.pre_dispatch(s, p, item=body.get("item"), action=str(body.get("action") or ""),
                            components=body.get("components") or [], area=str(body.get("area") or ""))
    return from_request(request, out, resource="engineering")


@router.post("/pidl/synthesize", dependencies=[Depends(authenticate)])
async def pidl_synthesize(request: Request, scope: str = "product_forge", project: str = "",
                          ctx: dict[str, Any] = Depends(authenticate)):
    """Cross-worker synthesis: evaluate combined parallel results for consistency (read-only)."""
    from core import pidl
    s, p = _scope_project(scope, project)
    with contextlib.suppress(Exception):
        body = await request.json()
    body = body if isinstance(body, dict) else {}
    out = pidl.synthesize(s, p, results=body.get("results") or [], item_id=str(body.get("item_id") or ""),
                          action=str(body.get("action") or ""), area=str(body.get("area") or ""))
    return from_request(request, out, resource="engineering")


@router.post("/pidl/consequential", dependencies=[Depends(authenticate)])
async def pidl_consequential(request: Request, scope: str = "product_forge", project: str = "",
                             ctx: dict[str, Any] = Depends(authenticate)):
    """Before-consequential-action gate: APPROVAL_REQUIRED when consequential (read-only)."""
    from core import pidl
    s, p = _scope_project(scope, project)
    with contextlib.suppress(Exception):
        body = await request.json()
    body = body if isinstance(body, dict) else {}
    out = pidl.consequential_gate(s, p, action=str(body.get("action") or ""),
                                  components=body.get("components") or [],
                                  area=str(body.get("area") or ""), item_id=str(body.get("item_id") or ""))
    return from_request(request, out, resource="engineering")


@router.get("/pidl/decisions", dependencies=[Depends(authenticate)])
def pidl_decisions(request: Request, scope: str = "", project: str = "", item_id: str = "",
                   limit: int = 50, ctx: dict[str, Any] = Depends(authenticate)):
    """Versioned PIDL decision trace (newest last)."""
    from core import pidl
    return from_request(request, {"decisions": pidl.history(scope=scope, project=project,
                                                           item_id=item_id, limit=limit)},
                        resource="engineering")


@router.get("/pidl/decisions/{decision_id}", dependencies=[Depends(authenticate)])
def pidl_decision(decision_id: str, request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    """A single PIDL decision record (evidence/confidence/risk/approval/outcome)."""
    from core import pidl
    d = pidl.get(decision_id)
    if not d:
        raise ApiError("NOT_FOUND", "pidl decision not found")
    return from_request(request, d, resource="engineering", resource_id=decision_id)


@router.get("/pidl/candidates", dependencies=[Depends(authenticate)])
def pidl_candidates(request: Request, status: str = "proposed", ctx: dict[str, Any] = Depends(authenticate)):
    """Evidence-gated learning candidates proposed from PIDL corrections (promote via learning_synth)."""
    from core import pidl
    return from_request(request, {"candidates": pidl.feedback_candidates(status=status)},
                        resource="engineering")


@router.get("/pidl/policy", dependencies=[Depends(authenticate)])
def pidl_policy(request: Request, action: str = "", area: str = "", components: str = "",
                ctx: dict[str, Any] = Depends(authenticate)):
    """The centralized approval policy view for an action/area."""
    from core import pidl
    comps = [c.strip() for c in str(components or "").split(",") if c.strip()]
    return from_request(request, pidl.approval_policy(action=action, area=area, components=comps),
                        resource="engineering")


@router.post("/pidl/decisions/{decision_id}/outcome", dependencies=[Depends(require_operator)])
async def pidl_outcome(decision_id: str, request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    """Record an outcome/correction for a decision; corrections become candidates (never rules)."""
    from core import pidl
    with contextlib.suppress(Exception):
        body = await request.json()
    body = body if isinstance(body, dict) else {}
    out = pidl.record_outcome(decision_id, outcome=str(body.get("outcome") or ""),
                              corrections=body.get("corrections") or [],
                              by=str((ctx or {}).get("subject") or "operator"))
    return from_request(request, out, resource="engineering", resource_id=decision_id)


@router.post("/pidl/approvals/{decision_id}", dependencies=[Depends(require_operator)])
async def pidl_approve(decision_id: str, request: Request, ctx: dict[str, Any] = Depends(require_operator)):
    """Authenticated approve/reject of a decision (recorded on the trace)."""
    from core import pidl
    with contextlib.suppress(Exception):
        body = await request.json()
    body = body if isinstance(body, dict) else {}
    out = pidl.record_approval(decision_id, approved=bool(body.get("approved")),
                               by=str((ctx or {}).get("subject") or "operator"),
                               reason=str(body.get("reason") or ""))
    return from_request(request, out, resource="engineering", resource_id=decision_id)


@router.get("/schedule", dependencies=[Depends(authenticate)])
def schedule(request: Request, scope: str = "product_forge", project: str = "",
             ctx: dict[str, Any] = Depends(authenticate)):
    from core import scheduler
    s, p = _scope_project(scope, project)
    return from_request(request, scheduler.plan(s, p), resource="engineering")


# ── PFSSOT-P4 (BI-PF-0365): eligibility over the canonical backlog (read-only) ──
@router.get("/schedule/status", dependencies=[Depends(authenticate)])
def schedule_status(request: Request, scope: str = "product_forge", project: str = "",
                    ctx: dict[str, Any] = Depends(authenticate)):
    """Scheduler roll-up: eligibility counts + task-contract report (read-only)."""
    from core import scheduler
    s, p = _scope_project(scope, project)
    eb = scheduler.eligible_backlog(s, p)
    return from_request(request, {"eligible": eb["eligible"], "blocked": eb["blocked"],
                                  "total": eb["total"], "report": scheduler.report(s, p)},
                        resource="engineering")


@router.get("/schedule/eligible", dependencies=[Depends(authenticate)])
def schedule_eligible(request: Request, scope: str = "product_forge", project: str = "",
                      stage: str = "", ctx: dict[str, Any] = Depends(authenticate)):
    from core import scheduler
    s, p = _scope_project(scope, project)
    return from_request(request, scheduler.eligible_backlog(s, p, stage=stage or None), resource="engineering")


@router.get("/schedule/next", dependencies=[Depends(authenticate)])
def schedule_next(request: Request, scope: str = "product_forge", project: str = "",
                  stage: str = "", ctx: dict[str, Any] = Depends(authenticate)):
    from core import scheduler
    s, p = _scope_project(scope, project)
    if stage == "execute" and s != "product_forge":
        raise ApiError("VALIDATION_FAILED",
                       "the worker claim path is product_forge-only; project changes run through the PF pipeline",
                       details={"scope": s})
    return from_request(request, scheduler.next_eligible(s, p, stage=stage or None), resource="engineering")


# ── BI-PF-0419: external-worker assignment lifecycle (per-item claim + lease) ──

@router.post("/assignments/claim", dependencies=[Depends(require_worker)])
def assignment_claim(body: dict[str, Any], request: Request,
                     ctx: dict[str, Any] = Depends(require_worker)):
    from core import backlog, job_manager, vcs
    from core.paths import ROOT
    s, p = _worker_scope(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    worker = str(body.get("worker_id") or ctx.get("actor") or "worker")
    res = job_manager.claim_next(s, p, worker=worker, lease_seconds=int(body.get("lease_seconds") or 0))
    if not res.get("claimed"):
        return from_request(request, {"assigned": False, **res}, resource="engineering")
    item = str(res["item"])
    it = backlog.get_epic(s, p, item) or {}
    proj_dir = _common.project_dir(p) if s == "project" else str(ROOT)
    vm = vcs.VCSManager(proj_dir)
    wt = vm.add_worktree(f"assign-{item}", branch=vm.feature_branch_name("wg", item))
    if not wt.get("ok"):
        job_manager.release(s, p, item, reason="worktree setup failed")
        raise ApiError("WORKTREE_FAILED", "could not create the assignment worktree",
                       details={"error": wt.get("error") or ""})
    pkg = {"assigned": True, "item_id": item, "title": it.get("title"),
           "description": it.get("body") or "", "acceptance_criteria": it.get("acceptance_criteria") or [],
           "assignment_id": res.get("assignment_id"), "lease_id": res.get("lease_id"),
           "lease_expires_at": res.get("lease_expires_at"), "worker_id": worker,
           "pidl_context": res.get("pidl_context"), "execution_policy": res.get("execution_policy"),
           "worktree": wt.get("path"), "branch": wt.get("branch"), "base_ref": wt.get("base")}
    return from_request(request, pkg, resource="engineering")


@router.post("/assignments/{item_id}/heartbeat", dependencies=[Depends(require_worker)])
def assignment_heartbeat(item_id: str, body: dict[str, Any], request: Request,
                         ctx: dict[str, Any] = Depends(require_worker)):
    from core import job_manager
    s, p = _worker_scope(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    return from_request(request, job_manager.renew_lease(s, p, item_id,
                        lease_seconds=int(body.get("lease_seconds") or 0)), resource="engineering")


@router.post("/assignments/{item_id}/complete", dependencies=[Depends(require_worker)])
def assignment_complete(item_id: str, body: dict[str, Any], request: Request, background: BackgroundTasks,
                        ctx: dict[str, Any] = Depends(require_worker)):
    from core import delivery, job_manager
    s, p = _worker_scope(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = job_manager.complete(s, p, item_id, status=str(body.get("status") or "verifying"),
                               note=str(body.get("note") or ""))
    # BI-PF-0421: async optimistic delivery lane (push+PR -> validate -> rebase -> merge -> push)
    if res.get("ok") and str(res.get("status")) == "verifying":
        background.add_task(delivery.deliver, s, p, item_id)
    return from_request(request, res, resource="engineering")


@router.post("/assignments/{item_id}/deliver", dependencies=[Depends(require_operator)])
def assignment_deliver(item_id: str, body: dict[str, Any], request: Request,
                       ctx: dict[str, Any] = Depends(require_operator)):
    """Run the delivery lane for one item synchronously (operator; recovery/manual). BI-PF-0421."""
    from core import delivery
    s, p = _worker_scope(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    return from_request(request, delivery.deliver(s, p, item_id,
                        integration=str(body.get("integration") or "")), resource="engineering")


@router.post("/assignments/{item_id}/fail", dependencies=[Depends(require_worker)])
def assignment_fail(item_id: str, body: dict[str, Any], request: Request,
                    ctx: dict[str, Any] = Depends(require_worker)):
    from core import job_manager
    s, p = _worker_scope(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    return from_request(request, job_manager.fail(s, p, item_id, reason=str(body.get("reason") or "")),
                        resource="engineering")


@router.post("/assignments/{item_id}/release", dependencies=[Depends(require_worker)])
def assignment_release(item_id: str, body: dict[str, Any], request: Request,
                       ctx: dict[str, Any] = Depends(require_worker)):
    from core import job_manager
    s, p = _worker_scope(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    return from_request(request, job_manager.release(s, p, item_id,
                        reason=str(body.get("reason") or "released")), resource="engineering")


# ── ENG-1: engineering task contracts ───────────────────────────────────────

@router.get("/tasks", dependencies=[Depends(authenticate)])
def list_tasks(request: Request, scope: str = "product_forge", project: str = "",
               status: str = "", limit: int = 50, cursor: str = "",
               ctx: dict[str, Any] = Depends(authenticate)):
    from core import task_contract
    s, p = _scope_project(scope, project)
    items = task_contract.list_tasks(s, p, status=status)
    page, links = paginate(items, limit=limit, cursor=cursor)
    return from_request(request, page, resource="task_contract", links=links)


@router.get("/tasks/{task_id}", dependencies=[Depends(authenticate)])
def get_task(task_id: str, request: Request, scope: str = "product_forge", project: str = "",
             ctx: dict[str, Any] = Depends(authenticate)):
    from core import task_contract
    s, p = _scope_project(scope, project)
    it = task_contract.get(s, p, task_id)
    if not it:
        raise ApiError("NOT_FOUND", "task contract not found")
    return from_request(request, it, resource="task_contract", resource_id=task_id)


@router.post("/tasks", dependencies=[Depends(require_operator)])
def create_task(body: dict[str, Any], request: Request,
                ctx: dict[str, Any] = Depends(require_operator)):
    from core import task_contract
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    try:
        it = task_contract.create(s, p, body)
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    return from_request(request, it, resource="task_contract", resource_id=str(it.get("task_id") or ""))


@router.post("/tasks/{task_id}/status", dependencies=[Depends(require_operator)])
def set_task_status(task_id: str, body: dict[str, Any], request: Request,
                    ctx: dict[str, Any] = Depends(require_operator)):
    from core import task_contract
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    try:
        res = task_contract.set_status(s, p, task_id, str(body.get("status") or ""),
                                       note=str(body.get("note") or ""))
    except ValueError as e:
        raise ApiError("VALIDATION_FAILED", str(e)) from None
    if res is None:
        raise ApiError("NOT_FOUND", "task contract not found")
    return from_request(request, res, resource="task_contract", resource_id=task_id)


# ── ENG-4: worker runtime (providers + run + results) ───────────────────────

@router.get("/worker-providers", dependencies=[Depends(authenticate)])
def worker_providers(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import worker
    return from_request(request, worker.available_providers(), resource="worker")


@router.get("/tasks/{task_id}/results", dependencies=[Depends(authenticate)])
def task_results(task_id: str, request: Request, scope: str = "product_forge", project: str = "",
                 ctx: dict[str, Any] = Depends(authenticate)):
    from core import worker
    s, p = _scope_project(scope, project)
    return from_request(request, worker.list_results(s, p, task_id),
                        resource="worker", resource_id=task_id)


@router.post("/tasks/{task_id}/run", dependencies=[Depends(require_operator)])
def run_task(task_id: str, body: dict[str, Any], request: Request,
             ctx: dict[str, Any] = Depends(require_operator)):
    from core import task_contract, worker
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    task = task_contract.get(s, p, task_id)
    if not task:
        raise ApiError("NOT_FOUND", "task contract not found")
    if s == "project":
        _common.project_dir(p)  # fail-closed if the project dir is missing
    pdir = worker.task_project_dir(s, p)
    try:
        res = worker.run_task(task, pdir, provider=str(body.get("provider") or "noop"),
                              base=str(body.get("base") or ""), run_id=str(body.get("run_id") or ""),
                              command=body.get("command"), commit=bool(body.get("commit") or False),
                              timeout=int(body.get("timeout") or 1800))
    except Exception as e:
        raise ApiError("INTERNAL", f"worker run failed: {type(e).__name__}") from e
    d = res.to_dict()
    worker.record_result(s, p, d)
    with contextlib.suppress(Exception):
        task_contract.set_status(s, p, task_id, worker.contract_status_for(d))
    return from_request(request, d, resource="worker", resource_id=task_id)
