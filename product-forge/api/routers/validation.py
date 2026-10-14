"""Validation API (API-3): canonical run verification + verification-policy coverage.

Read-models over ``core.close_loop`` (the scope-aware, run-bound verified/not decision) and
``core.verification_policy`` (internal/external/not_run classification). No shadow store.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
from . import _common

router = APIRouter(prefix="/validation", tags=["validation"])


def _scope_project(scope: str, project: str):
    s = str(scope or "project").strip()
    p = str(project or "").strip() or None
    if s not in ("product_forge", "project"):
        raise ApiError("VALIDATION_FAILED", "scope must be product_forge or project")
    if s == "project" and not p:
        raise ApiError("VALIDATION_FAILED", "project required for project scope")
    return s, p


@router.get("", dependencies=[Depends(authenticate)])
def validation(project: str, request: Request, scope: str = "", run_id: str = "",
               ctx: dict[str, Any] = Depends(authenticate)):
    from core import close_loop
    d = _common.project_dir(project)
    return from_request(request, close_loop.verify_run(d, scope=scope, run_id=run_id),
                        resource="validation", resource_id=project)


@router.get("/policy", dependencies=[Depends(authenticate)])
def policy(project: str, request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import verification_policy
    d = _common.project_dir(project)
    return from_request(request, verification_policy.summary(d),
                        resource="validation", resource_id=project)


# ── ENG-6: Common Validation Engine (profiles) ──────────────────────────────

@router.get("/profiles", dependencies=[Depends(authenticate)])
def validation_profiles(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import validation_engine
    return from_request(request, validation_engine.profiles(), resource="validation")


@router.get("/runs", dependencies=[Depends(authenticate)])
def validation_runs(request: Request, scope: str = "project", project: str = "", profile: str = "",
                    ctx: dict[str, Any] = Depends(authenticate)):
    from core import validation_engine
    s, p = _scope_project(scope, project)
    return from_request(request, validation_engine.list_runs(s, p, profile=profile),
                        resource="validation", resource_id=project)


@router.post("/dogfood", dependencies=[Depends(require_operator)])
def dogfood(body: dict[str, Any], request: Request,
            ctx: dict[str, Any] = Depends(require_operator)):
    from core import dogfood as _dog
    s, p = _scope_project(str(body.get("scope") or "product_forge"), str(body.get("project") or ""))
    if s == "product_forge":
        from core.paths import ROOT
        d = ROOT
    else:
        d = _common.project_dir(p)
    res = _dog.run(p or s, d, idea=body.get("idea") or {}, target=str(body.get("target") or ""),
                   baseline=str(body.get("baseline") or ""), run_id=str(body.get("run_id") or ""), scope=s,
                   trigger_pipeline=bool(body.get("trigger_pipeline", True)),
                   dry=bool(body.get("dry") or False), use_worktree=bool(body.get("use_worktree", True)),
                   repair=bool(body.get("repair") or False))
    return from_request(request, res, resource="validation", resource_id=str(res.get("run_id") or ""))


@router.get("/merge-gate", dependencies=[Depends(authenticate)])
def merge_gate(project: str, request: Request, scope: str = "project",
               ctx: dict[str, Any] = Depends(authenticate)):
    from core import merge_gate as _mg
    s, p = _scope_project(scope, project)
    if s == "product_forge":
        from core.paths import ROOT
        d = ROOT
    else:
        d = _common.project_dir(p)
    return from_request(request, _mg.evaluate(p or s, d, scope=s),
                        resource="validation", resource_id=project)


@router.get("/merge-gate/queue", dependencies=[Depends(authenticate)])
def merge_queue(request: Request, scope: str = "project", project: str = "",
                ctx: dict[str, Any] = Depends(authenticate)):
    from core import merge_gate as _mg
    s, p = _scope_project(scope, project)
    return from_request(request, _mg.queue(s, p or ""), resource="validation")


@router.post("/integration", dependencies=[Depends(require_operator)])
def integration(body: dict[str, Any], request: Request,
                ctx: dict[str, Any] = Depends(require_operator)):
    from core import validation_engine
    s, p = _scope_project(str(body.get("scope") or "project"), str(body.get("project") or ""))
    if s == "product_forge":
        from core.paths import ROOT
        d = ROOT
    else:
        d = _common.project_dir(p)
    res = validation_engine.run(p or s, d, profile_name="INTEGRATION",
                                target=str(body.get("target") or ""), base=str(body.get("base") or ""),
                                run_id=str(body.get("run_id") or ""), scope=s)
    return from_request(request, res, resource="validation", resource_id=str(res.get("run_id") or ""))


@router.post("/feature-pr", dependencies=[Depends(require_operator)])
def feature_pr(body: dict[str, Any], request: Request,
               ctx: dict[str, Any] = Depends(require_operator)):
    from core import validation_engine
    s, p = _scope_project(str(body.get("scope") or "project"), str(body.get("project") or ""))
    if s == "product_forge":
        from core.paths import ROOT
        d = ROOT
    else:
        d = _common.project_dir(p)
    res = validation_engine.feature_pr(p or s, d, target=str(body.get("target") or ""),
                                       base=str(body.get("base") or ""), run_id=str(body.get("run_id") or ""),
                                       scope=s, use_worktree=bool(body.get("use_worktree", True)),
                                       record_defects=bool(body.get("record_defects") or False))
    return from_request(request, res, resource="validation", resource_id=str(res.get("run_id") or ""))


@router.post("/run", dependencies=[Depends(require_operator)])
def run_validation(body: dict[str, Any], request: Request,
                   ctx: dict[str, Any] = Depends(require_operator)):
    from core import validation_engine
    s, p = _scope_project(str(body.get("scope") or "project"), str(body.get("project") or ""))
    prof = str(body.get("profile") or "FEATURE_PR")
    if validation_engine.profile(prof) is None:
        raise ApiError("VALIDATION_FAILED", "unknown validation profile", details={"profile": prof})
    if s == "product_forge":
        from core.paths import ROOT
        d = ROOT
    else:
        d = _common.project_dir(p)
    res = validation_engine.run(p or s, d, profile_name=prof, target=str(body.get("target") or ""),
                                base=str(body.get("base") or ""), run_id=str(body.get("run_id") or ""),
                                scope=s)
    return from_request(request, res, resource="validation", resource_id=str(res.get("run_id") or ""))


# ── Artifact Contract Registry (given format/semantics per artifact type) ────
# The registry tells each agent/stage the GIVEN sections/counts/size budget so output is
# bounded by construction. Owner: core/contracts.py. Data: config/artifact-contracts/.

@router.get("/artifact-contracts", dependencies=[Depends(authenticate)])
def artifact_contracts(request: Request, tier: str = "", kind: str = "",
                       ctx: dict[str, Any] = Depends(authenticate)):
    from core import contracts
    reg = contracts.load_registry()
    items = []
    for aid, c in reg.items():
        if tier and str(c.get("tier")) != tier:
            continue
        applies = [str(x).lower() for x in (c.get("applies_to") or [])]
        if kind and kind.lower() not in applies and "*" not in applies:
            continue
        items.append(dict(c, artifact_id=aid))
    return from_request(request, {"count": len(items), "contracts": items},
                        resource="artifact-contracts", resource_id="registry")


@router.get("/artifact-contracts/resolve", dependencies=[Depends(authenticate)])
def artifact_contracts_resolve(request: Request, agent: str = "", stage: str = "",
                               kind: str = "*", profile: str = "",
                               ctx: dict[str, Any] = Depends(authenticate)):
    from core import contracts
    return from_request(request, contracts.resolve(agent=agent, stage=stage, kind=kind,
                                                   profile=profile),
                        resource="artifact-contracts", resource_id=agent or stage)


@router.get("/artifact-contracts/kind", dependencies=[Depends(authenticate)])
def artifact_contracts_kind(request: Request, idea: str = "",
                            ctx: dict[str, Any] = Depends(authenticate)):
    from core import contracts
    return from_request(request, contracts.detect_kind(idea),
                        resource="artifact-contracts", resource_id="kind")


@router.get("/artifact-contracts/budget", dependencies=[Depends(authenticate)])
def artifact_contracts_budget(request: Request, agent: str = "", stage: str = "", kind: str = "*",
                              profile: str = "", ctx: dict[str, Any] = Depends(authenticate)):
    from core import contracts
    return from_request(request, contracts.budget(agent=agent, stage=stage, kind=kind, profile=profile),
                        resource="artifact-contracts", resource_id=agent or stage)


@router.get("/artifact-contracts/reconcile", dependencies=[Depends(authenticate)])
def artifact_contracts_reconcile(request: Request, project: str = "", agent: str = "",
                                 stage: str = "", kind: str = "*", profile: str = "",
                                 run_budget_seconds: float = -1.0,
                                 ctx: dict[str, Any] = Depends(authenticate)):
    """Reconcile summed per-artifact budgets vs the run budget (ADVISORY; never gates)."""
    from core import contracts
    d = _common.project_dir(project) if project else ""
    rb = None if run_budget_seconds is None or run_budget_seconds < 0 else run_budget_seconds
    return from_request(request, contracts.reconcile(project_dir=d, agent=agent, stage=stage,
                                                     kind=kind, profile=profile,
                                                     run_budget_seconds=rb),
                        resource="artifact-contracts", resource_id="reconcile")


@router.get("/artifact-contracts/{artifact_id}", dependencies=[Depends(authenticate)])
def artifact_contract_one(artifact_id: str, request: Request,
                          ctx: dict[str, Any] = Depends(authenticate)):
    from core import contracts
    c = contracts.contract(artifact_id)
    if not c:
        raise ApiError("NOT_FOUND", "unknown artifact contract", details={"artifact_id": artifact_id})
    return from_request(request, dict(c, artifact_id=artifact_id),
                        resource="artifact-contracts", resource_id=artifact_id)


@router.post("/artifact-contracts/validate", dependencies=[Depends(require_operator)])
def artifact_contract_validate(body: dict[str, Any], request: Request,
                               ctx: dict[str, Any] = Depends(require_operator)):
    from core import contracts
    aid = str(body.get("artifact_id") or "").strip()
    if not aid:
        raise ApiError("VALIDATION_FAILED", "artifact_id is required")
    return from_request(request, contracts.validate_artifact(aid, str(body.get("text") or "")),
                        resource="artifact-contracts", resource_id=aid)


@router.post("/artifact-contracts/refresh-check", dependencies=[Depends(require_operator)])
def artifact_contract_refresh_check(request: Request,
                                    ctx: dict[str, Any] = Depends(require_operator)):
    """Advisory: check upstream sources for newer versions (never applies)."""
    import subprocess
    import sys as _sys
    from core.paths import ROOT
    p = subprocess.run([_sys.executable, "scripts/dev/artifact_contracts_refresh.py", "--check"],
                       cwd=str(ROOT), capture_output=True, text=True)
    return from_request(request, {"ok": p.returncode == 0,
                                  "output": (p.stdout or p.stderr or "")[-4000:]},
                        resource="artifact-contracts", resource_id="refresh-check")


# ── Agent Registry (declarative agent spec: inputs/outputs/artifacts) ─────────
# Owner: core/contracts.py (Go engine). Data: config/agent-registry/index.json.

@router.get("/agents", dependencies=[Depends(authenticate)])
def agents(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import contracts
    reg = contracts.agent_registry()
    return from_request(request, {"count": len(reg), "agents": reg},
                        resource="agents", resource_id="registry")


@router.get("/agents/coverage", dependencies=[Depends(authenticate)])
def agents_coverage(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    import glob
    import json
    import os
    from core.paths import ROOT
    from core import contracts
    ids = []
    for f in glob.glob(os.path.join(str(ROOT), "agents", "*.agent.json")):
        try:
            ids.append(json.load(open(f, encoding="utf-8-sig"))["id"])
        except Exception:
            pass
    return from_request(request, contracts.agent_coverage(ids),
                        resource="agents", resource_id="coverage")


@router.post("/agents/register", dependencies=[Depends(require_operator)])
def agent_register(body: dict[str, Any], request: Request,
                   ctx: dict[str, Any] = Depends(require_operator)):
    """Register/update an agent in the agent registry (validates outputs; single writer)."""
    from core import contracts
    aid = str(body.get("agent") or "").strip()
    if not aid:
        raise ApiError("VALIDATION_FAILED", "agent is required")
    res = contracts.register_agent(aid, outputs=body.get("outputs") or ["none"],
                                   inputs=body.get("inputs") or [],
                                   title=str(body.get("title") or ""),
                                   kind_scope=str(body.get("kind_scope") or "*"))
    if not res.get("ok"):
        raise ApiError("VALIDATION_FAILED", "agent registration failed",
                       details={"errors": res.get("errors") or []})
    return from_request(request, res, resource="agents", resource_id=aid)


@router.get("/agents/{agent_id}", dependencies=[Depends(authenticate)])
def agent_one(agent_id: str, request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import contracts
    sp = contracts.agent_spec(agent_id)
    if not sp:
        raise ApiError("NOT_FOUND", "unknown agent", details={"agent": agent_id})
    return from_request(request, dict(sp, agent_id=agent_id), resource="agents", resource_id=agent_id)
