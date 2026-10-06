"""Engineering architecture API (ENG-0): the requirement -> deploy flow over the API-1..API-3 contracts.

Read-model over ``core.engineering_flow`` (``config/engineering-flow.json``): each step with its canonical
owner file, the ``/api/v1`` route that exposes it, and its status (exists | partial | planned). No engine.
"""

import contextlib
from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
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


def _worker_on():
    """PFSSOT-P8A: the optional external-worker endpoints are disabled when WORKER_INTEGRATION_ENABLED=0."""
    from core import worker_registry
    if not worker_registry.integration_enabled():
        raise ApiError("DEPENDENCY_UNAVAILABLE", "worker integration disabled",
                       details={"flag": "WORKER_INTEGRATION_ENABLED"})


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


# ── ENG-2: worker pool + elastic schedule ───────────────────────────────────

@router.get("/workers", dependencies=[Depends(authenticate), Depends(_worker_on)])
def workers(request: Request, scope: str = "product_forge", project: str = "",
            ctx: dict[str, Any] = Depends(authenticate)):
    from core import scheduler, worker_registry
    reg = scheduler.workers()
    s, p = _scope_project(scope, project)
    dynamic = worker_registry.list_workers(s, p)
    return from_request(request, {"registry": reg, "slots": scheduler.worker_slots(reg),
                                  "dynamic": dynamic,
                                  "dynamic_slots": worker_registry.available_slots(s, p)},
                        resource="engineering")


# ── PFSSOT-P6 (BI-PF-0367): worker registry + heartbeat + lifecycle (runtime-neutral) ──
@router.post("/workers/register", dependencies=[Depends(require_operator), Depends(_worker_on)])
def worker_register(body: dict[str, Any], request: Request,
                    ctx: dict[str, Any] = Depends(require_operator)):
    from core import worker_registry
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    rec = worker_registry.register(s, p, runtime=str(body.get("runtime") or "opencode"),
                                   capabilities=body.get("capabilities") or [],
                                   role=str(body.get("role") or ""), endpoint=str(body.get("endpoint") or ""),
                                   workspace=str(body.get("workspace") or ""),
                                   worker_id=str(body.get("worker_id") or ""))
    return from_request(request, rec, resource="worker_registry", resource_id=rec.get("worker_id"))


@router.post("/workers/{worker_id}/heartbeat", dependencies=[Depends(authenticate), Depends(_worker_on)])
def worker_heartbeat(worker_id: str, body: dict[str, Any], request: Request,
                     ctx: dict[str, Any] = Depends(authenticate)):
    from core import worker_registry
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = worker_registry.heartbeat(s, p, worker_id, status=str(body.get("status") or ""),
                                    current_assignment_id=str(body.get("current_assignment_id") or ""))
    if not res.get("ok"):
        raise ApiError("NOT_FOUND", "unknown worker")
    return from_request(request, res, resource="worker_registry", resource_id=worker_id)


@router.get("/workers/{worker_id}", dependencies=[Depends(authenticate), Depends(_worker_on)])
def worker_get(worker_id: str, request: Request, scope: str = "product_forge", project: str = "",
               ctx: dict[str, Any] = Depends(authenticate)):
    from core import worker_registry
    s, p = _scope_project(scope, project)
    w = worker_registry.get(s, p, worker_id)
    if not w:
        raise ApiError("NOT_FOUND", "unknown worker")
    return from_request(request, w, resource="worker_registry", resource_id=worker_id)


@router.post("/workers/{worker_id}/unregister", dependencies=[Depends(require_operator), Depends(_worker_on)])
def worker_unregister(worker_id: str, body: dict[str, Any], request: Request,
                      ctx: dict[str, Any] = Depends(require_operator)):
    from core import worker_registry
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    return from_request(request, worker_registry.unregister(s, p, worker_id,
                        revoke=bool(body.get("revoke") or False)),
                        resource="worker_registry", resource_id=worker_id)


# ── PFSSOT-P8 (BI-PF-0369): manual work pull (first e2e milestone) ──
@router.post("/work", dependencies=[Depends(require_operator), Depends(_worker_on)])
def work_pull(body: dict[str, Any], request: Request,
              ctx: dict[str, Any] = Depends(require_operator)):
    """Manual pull: claim the next eligible item for a worker and return the assignment package."""
    from core import work_pull
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = work_pull.pull(s, p, worker_id=str(body.get("worker_id") or ctx.get("actor") or ""),
                         runtime=str(body.get("runtime") or ""))
    return from_request(request, res, resource="work",
                        resource_id=str(((res.get("package") or {}).get("task") or {}).get("item_id") or ""))


@router.post("/work/{item_id}/start", dependencies=[Depends(require_operator), Depends(_worker_on)])
def work_start(item_id: str, body: dict[str, Any], request: Request,
               ctx: dict[str, Any] = Depends(require_operator)):
    """Invoke the assigned worker's adapter ``start`` for the claimed item."""
    from core import work_pull
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = work_pull.start(s, p, item_id, worktree=str(body.get("worktree") or ""),
                          command=body.get("command"))
    return from_request(request, res, resource="work", resource_id=item_id)


# ── PFSSOT-P9 (BI-PF-0371): automatic dispatch (configurable; default off) ──
@router.get("/dispatch/status", dependencies=[Depends(authenticate), Depends(_worker_on)])
def dispatch_status(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import dispatcher
    return from_request(request, dispatcher.status(), resource="dispatch")


@router.post("/dispatch/tick", dependencies=[Depends(require_operator), Depends(_worker_on)])
def dispatch_tick(body: dict[str, Any], request: Request,
                  ctx: dict[str, Any] = Depends(require_operator)):
    """Run ONE dispatch pass (operator tick; deterministic, testable)."""
    from core import dispatcher
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = dispatcher.tick(s, p, force=bool(body.get("force") or False),
                          max_assign=int(body.get("max_assign") or 0))
    return from_request(request, res, resource="dispatch")


# ── PFSSOT-P7 (BI-PF-0368): runtime-neutral worker adapter contract ──
@router.get("/adapters", dependencies=[Depends(authenticate), Depends(_worker_on)])
def adapters(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import worker_adapters
    return from_request(request, {"contract": worker_adapters.contract(),
                                  "adapters": worker_adapters.list_adapters()},
                        resource="worker_adapter")


@router.post("/workers/{worker_id}/assign", dependencies=[Depends(require_operator), Depends(_worker_on)])
def worker_assign(worker_id: str, body: dict[str, Any], request: Request,
                  ctx: dict[str, Any] = Depends(require_operator)):
    """Assign a claimed item to a worker through its adapter (accept_assignment)."""
    from core import worker_adapters, worker_registry
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    w = worker_registry.get(s, p, worker_id)
    if not w:
        raise ApiError("NOT_FOUND", "unknown worker")
    ad = worker_adapters.resolve(str(w.get("runtime") or ""))
    if ad is None:
        raise ApiError("VALIDATION_FAILED", "no adapter for runtime", details={"runtime": w.get("runtime")})
    res = ad.accept_assignment(s, p, worker_id, str(body.get("assignment_id") or ""))
    return from_request(request, {"adapter": ad.runtime, "result": res},
                        resource="worker_adapter", resource_id=worker_id)


@router.post("/workers/{worker_id}/report", dependencies=[Depends(require_operator), Depends(_worker_on)])
def worker_report(worker_id: str, body: dict[str, Any], request: Request,
                  ctx: dict[str, Any] = Depends(require_operator)):
    from core import worker_adapters, worker_registry
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    w = worker_registry.get(s, p, worker_id)
    if not w:
        raise ApiError("NOT_FOUND", "unknown worker")
    ad = worker_adapters.resolve(str(w.get("runtime") or ""))
    if ad is None:
        raise ApiError("VALIDATION_FAILED", "no adapter for runtime", details={"runtime": w.get("runtime")})
    res = ad.report_result(s, p, worker_id, body.get("result") or {})
    return from_request(request, {"adapter": ad.runtime, "result": res},
                        resource="worker_adapter", resource_id=worker_id)


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
                      ctx: dict[str, Any] = Depends(authenticate)):
    from core import scheduler
    s, p = _scope_project(scope, project)
    return from_request(request, scheduler.eligible_backlog(s, p), resource="engineering")


@router.get("/schedule/next", dependencies=[Depends(authenticate)])
def schedule_next(request: Request, scope: str = "product_forge", project: str = "",
                  ctx: dict[str, Any] = Depends(authenticate)):
    from core import scheduler
    s, p = _scope_project(scope, project)
    return from_request(request, scheduler.next_eligible(s, p), resource="engineering")


# ── PFSSOT-P5 (BI-PF-0366): atomic claim + lease + recovery (single claimer: job_manager) ──
@router.post("/schedule/claim", dependencies=[Depends(require_operator), Depends(_worker_on)])
def schedule_claim(body: dict[str, Any], request: Request,
                   ctx: dict[str, Any] = Depends(require_operator)):
    from core import job_manager
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    res = job_manager.claim_next(s, p, worker=str(body.get("worker") or ctx.get("actor") or "api"),
                                 lease_seconds=int(body.get("lease_seconds") or 0))
    return from_request(request, res, resource="engineering", resource_id=str(res.get("item") or ""))


@router.post("/schedule/lease/{item_id}/renew", dependencies=[Depends(require_operator), Depends(_worker_on)])
def schedule_lease_renew(item_id: str, body: dict[str, Any], request: Request,
                         ctx: dict[str, Any] = Depends(require_operator)):
    from core import job_manager
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    return from_request(request, job_manager.renew_lease(s, p, item_id,
                        lease_seconds=int(body.get("lease_seconds") or 0)),
                        resource="engineering", resource_id=item_id)


@router.post("/schedule/lease/{item_id}/release", dependencies=[Depends(require_operator), Depends(_worker_on)])
def schedule_lease_release(item_id: str, body: dict[str, Any], request: Request,
                           ctx: dict[str, Any] = Depends(require_operator)):
    from core import job_manager
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    return from_request(request, job_manager.release(s, p, item_id,
                        reason=str(body.get("reason") or "released"),
                        terminal=bool(body.get("terminal") or False)),
                        resource="engineering", resource_id=item_id)


@router.post("/schedule/recover", dependencies=[Depends(require_operator), Depends(_worker_on)])
def schedule_recover(body: dict[str, Any], request: Request,
                     ctx: dict[str, Any] = Depends(require_operator)):
    from core import job_manager
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    return from_request(request, job_manager.recover_expired(s, p, policy=str(body.get("policy") or "")),
                        resource="engineering")


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
