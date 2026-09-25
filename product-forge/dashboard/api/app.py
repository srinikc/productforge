"""FastAPI app for the Product Forge Dashboard (backend API layer).

Covers the API needs identified in the dashboard discovery:
  * intake (adapters: ChatGPT/Claude/Gemini/generic)  - BI-0051/0052/0053
  * backlog management for all scopes                  - BI-0081
  * model capability-fit (tier + per-agent)            - BI-0077
  * pipeline/agent status + SSE live events            - BI-0056
  * CORS/OPTIONS + bearer auth                         - BI-0049/0051

The pipeline stays the single source of truth: this layer reads its stores and
routes actions through the owning core modules.

Run:
    python -m dashboard.api.app            # uvicorn on DASHBOARD_API_PORT (default 8000)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

REPO = Path(__file__).resolve().parent.parent.parent
PRODUCTS = REPO / "products"

app = FastAPI(title="Product Forge Dashboard API", version="1.0.0")

_origins = [o.strip() for o in os.getenv("DASHBOARD_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _token() -> str:
    return os.getenv("DASHBOARD_API_TOKEN", "").strip()


def auth(authorization: Optional[str] = Header(default=None)) -> None:
    """Bearer auth when DASHBOARD_API_TOKEN is set (BI-0051)."""
    want = _token()
    if not want:
        return
    if not authorization or authorization.split()[-1] != want:
        raise HTTPException(status_code=401, detail="unauthorized")


def operator_guard(x_roles: Optional[str] = Header(default=None)) -> None:
    """Operator endpoints exist ONLY on an operator instance (BI-0069).

    On a tenant instance they 404 (invisible), never 403.
    """
    from core import licensing
    if licensing.instance_role() != "operator":
        raise HTTPException(status_code=404, detail="not found")
    roles = [r.strip() for r in (x_roles or "").split(",") if r.strip()]
    if _token() or roles:
        if roles and not licensing.is_platform_admin(roles):
            raise HTTPException(status_code=404, detail="not found")


def _rj(p: Path, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ── health / status ──────────────────────────────────────────────────────────
@app.get("/health")
@app.get("/api/v1/health")
def health():
    return {"ok": True, "ts": time.time(), "repo": str(REPO)}


@app.get("/api/v1/status", dependencies=[Depends(auth)])
def status(project: str = Query(...)):
    pj = PRODUCTS / project
    return {
        "project": project,
        "state": _rj(pj / "pipeline-state.json", {}),
        "agents_live": _rj(pj / "agents-live.json", {}),
        "control": _rj(pj / "control.json", {}),
    }


# ── billing / self-service checkout (BI-0058/0066) ───────────────────────────
@app.post("/api/v1/billing/checkout")
def billing_checkout(body: Dict[str, Any]):
    """Public self-service: choose a plan -> get a license + provisioned tenant."""
    from core import billing
    tenant = body.get("tenant")
    tier = body.get("tier", "trial")
    if not tenant:
        raise HTTPException(400, "tenant required")
    r = billing.checkout(tenant, tier, body.get("email", ""), int(body.get("trial_days", 0)))
    if not r.get("ok"):
        raise HTTPException(402, r)
    return r


# ── control plane (BI-0043) ──────────────────────────────────────────────────
@app.get("/api/v1/cp/tenants", dependencies=[Depends(operator_guard)])
def cp_tenants():
    from core import control_plane as cp
    return {"tenants": cp.list_tenants()}


@app.get("/api/v1/cp/users", dependencies=[Depends(auth)])
def cp_users(tenant: str = Query("")):
    from core import control_plane as cp
    return {"users": cp.list_users(tenant)}


# ── tenant admin: members/roles/seats (BI-0068) ──────────────────────────────
@app.get("/api/v1/tenants/{tenant}/members", dependencies=[Depends(auth)])
def tenant_members(tenant: str):
    from core import tenancy
    return {"tenant": tenant, "members": tenancy.members(tenant)}


@app.post("/api/v1/tenants/{tenant}/members", dependencies=[Depends(auth)])
def tenant_invite(tenant: str, body: Dict[str, Any]):
    from core import tenancy
    try:
        return tenancy.invite(tenant, body.get("email", ""), body.get("roles"), body.get("team", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/v1/tenants/{tenant}/members/{email}/role", dependencies=[Depends(auth)])
def tenant_set_role(tenant: str, email: str, body: Dict[str, Any]):
    from core import tenancy
    try:
        r = tenancy.set_role(tenant, email, body.get("roles"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not r:
        raise HTTPException(404, "member not found")
    return r


@app.delete("/api/v1/tenants/{tenant}/members/{email}", dependencies=[Depends(auth)])
def tenant_remove(tenant: str, email: str):
    from core import tenancy
    return {"removed": tenancy.remove_member(tenant, email)}


@app.get("/api/v1/tenants/{tenant}/seats", dependencies=[Depends(auth)])
def tenant_seats(tenant: str, tier: str = Query("")):
    from core import tenancy
    return tenancy.seats(tenant, tier)


# ── capacity (BI-0041: tenant/tier-aware) ────────────────────────────────────
@app.get("/api/v1/capacity", dependencies=[Depends(auth)])
def capacity(tier: str = Query("")):
    from core import capacity as cap
    return {
        "global": cap.status(),
        "effective": cap.effective_limits(tier) if tier else None,
        "can_add": cap.can_add_context(tier) if tier else cap.can_add(),
        "can_start": cap.can_start_context("", tier) if tier else cap.can_start(),
    }


# ── per-agent control (BI-0046) ──────────────────────────────────────────────
@app.post("/api/v1/agents/{agent}/control", dependencies=[Depends(auth)])
def agent_control(agent: str, body: Dict[str, Any]):
    """Per-agent op (pause|resume|stop|cancel) via the control channel."""
    project = body.get("project")
    if not project:
        raise HTTPException(400, "project required")
    op = str(body.get("op") or "").lower()
    if op not in ("pause", "resume", "stop", "cancel", ""):
        raise HTTPException(400, "op must be pause|resume|stop|cancel")
    cf = PRODUCTS / project / "control.json"
    data = _rj(cf, {}) or {}
    ops = data.get("agents") or {}
    if op:
        ops[agent] = op
    else:
        ops.pop(agent, None)
    data["agents"] = ops
    data["updated_at"] = time.time()
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"agent": agent, "op": op, "agents": ops}


# ── SSE live events (BI-0056) ────────────────────────────────────────────────
@app.get("/api/v1/events")
def events(project: str = Query("")):
    def _gen():
        ev = PRODUCTS / ".orchestration" / "events.jsonl"
        pos = 0
        last_beat = 0.0
        while True:
            try:
                if ev.exists():
                    with open(ev, encoding="utf-8", errors="replace") as f:
                        f.seek(pos)
                        for line in f:
                            line = line.strip()
                            if line:
                                yield f"data: {line}\n\n"
                        pos = f.tell()
            except Exception:
                pass
            if time.time() - last_beat > 15:
                last_beat = time.time()
                yield ": heartbeat\n\n"
            time.sleep(1)
    return StreamingResponse(_gen(), media_type="text/event-stream")


# ── intake (BI-0051/0052/0053) ───────────────────────────────────────────────
@app.post("/api/intake", dependencies=[Depends(auth)])
@app.post("/api/v1/intake", dependencies=[Depends(auth)])
def intake(body: Dict[str, Any]):
    try:
        from core.intake import ingest
    except Exception as e:
        raise HTTPException(500, f"intake unavailable: {e}")
    src = str(body.get("source") or body.get("source_platform") or "generic")
    payload = body.get("payload") or body
    return ingest(src, payload, body.get("scope"), body.get("project"))


@app.post("/api/v1/intake/upload-chunk", dependencies=[Depends(auth)])
def intake_upload_chunk(body: Dict[str, Any]):
    # Chunked upload buffering is owned by conversation_models; best-effort here.
    try:
        from core.conversation_models import ConversationStore
        store = ConversationStore(str(PRODUCTS))
        conv_id = str(body.get("conversation_id") or "")
        chunk = str(body.get("chunk") or "")
        if not conv_id:
            raise HTTPException(400, "conversation_id required")
        try:
            store.append_upload_chunk(conv_id, chunk)
        except Exception:
            pass
        return {"ok": True, "conversation_id": conv_id, "received": len(chunk)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/v1/intake/upload-complete", dependencies=[Depends(auth)])
def intake_upload_complete(body: Dict[str, Any]):
    try:
        from core.intake import ingest
        payload = dict(body)
        payload.setdefault("source", body.get("source_platform") or "generic")
        return ingest(str(body.get("source") or "generic"), payload,
                      body.get("scope"), body.get("project"))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/v1/intake/instructions")
def intake_instructions(source: str = "generic"):
    try:
        from core.intake import instructions
        return {"source": source, "instructions": instructions(source)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── backlog (BI-0081) ────────────────────────────────────────────────────────
def _scope_parts(scope: str) -> tuple:
    """scope: 'product_forge' | 'project:<id>' -> (scope, project)."""
    if scope.startswith("project:"):
        return "project", scope.split(":", 1)[1]
    return "product_forge", None


@app.get("/api/v1/backlog", dependencies=[Depends(auth)])
def backlog_list(scope: str = Query("product_forge"), status: str = "",
                 section: str = "", origin: str = "", q: str = ""):
    from core import backlog
    s, p = _scope_parts(scope)
    items = backlog.list_open(s, p, order=False) + backlog.list_closed(s, p)
    if status:
        items = [i for i in items if i.get("status") == status]
    if section:
        items = [i for i in items if backlog.section(i) == section]
    if origin:
        items = [i for i in items if i.get("origin") == origin]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in (i.get("title", "") + i.get("body", "")).lower()]
    return {"scope": scope, "count": len(items), "items": items}


@app.get("/api/v1/backlog/stats", dependencies=[Depends(auth)])
def backlog_stats(scope: str = Query("product_forge")):
    from core import backlog
    s, p = _scope_parts(scope)
    return backlog.stats(s, p)


@app.get("/api/v1/backlog/parked", dependencies=[Depends(auth)])
def backlog_parked():
    from core import backlog
    return {"items": backlog.parked_review()}


@app.get("/api/v1/backlog/{eid}", dependencies=[Depends(auth)])
def backlog_get(eid: str, scope: str = Query("product_forge")):
    from core import backlog
    s, p = _scope_parts(scope)
    it = backlog.get_by_ref(eid) if (":" in eid) else backlog.get_epic(s, p, eid)
    if not it:
        raise HTTPException(404, "not found")
    return it


@app.get("/api/v1/backlog/{eid}/history", dependencies=[Depends(auth)])
def backlog_history(eid: str, scope: str = Query("product_forge")):
    from core import backlog
    s, p = _scope_parts(scope)
    return {"id": eid, "history": backlog.history(s, p, eid)}


@app.post("/api/v1/backlog", dependencies=[Depends(auth)])
def backlog_create(body: Dict[str, Any]):
    from core import backlog
    s, p = _scope_parts(str(body.get("scope") or "product_forge"))
    title = body.get("title")
    if not title:
        raise HTTPException(400, "title required")
    return backlog.add_epic(s, p, title=title, body=body.get("body", ""),
                            type_=body.get("type", "feature"), origin=body.get("origin", "intake"),
                            moscow=body.get("moscow", "Should"))


@app.post("/api/v1/backlog/{eid}/{action}", dependencies=[Depends(auth)])
def backlog_action(eid: str, action: str, body: Dict[str, Any]):
    from core import backlog
    s, p = _scope_parts(str(body.get("scope") or "product_forge"))
    if action == "triage":
        return backlog.triage(s, p, eid, recommendation=body.get("note", ""),
                              value=body.get("value"), effort=body.get("effort"),
                              risk=body.get("risk"), moscow=body.get("moscow"))
    if action == "accept":
        return backlog.accept(s, p, eid, when=body.get("when", "later"), by=body.get("by", "hil"))
    if action in ("close", "reject", "wontfix", "duplicate", "merged"):
        return backlog.set_status(s, p, eid, action, note=body.get("note", ""))
    if action == "follow-up":
        return backlog.set_follow_up(s, p, eid, at=body.get("at", ""),
                                     every_days=int(body.get("every_days", 7)),
                                     snooze_days=int(body.get("snooze_days", 0)))
    if action == "update":
        fields = {k: v for k, v in body.items() if k != "scope"}
        return backlog.update(s, p, eid, **fields)
    if action == "link":
        refs = {k: v for k, v in body.items() if k != "scope"}
        return backlog.link(s, p, eid, **refs)
    raise HTTPException(400, f"unknown action: {action}")


# ── model capability-fit (BI-0077) ───────────────────────────────────────────
@app.get("/api/v1/model-fit", dependencies=[Depends(auth)])
def model_fit_get(project: str = Query(...)):
    from core import model_fit
    rep = model_fit.load_report(str(PRODUCTS / project))
    if not rep:
        raise HTTPException(404, "no model-fit report for this project yet")
    return rep


@app.get("/api/v1/model-fit/agent/{agent}", dependencies=[Depends(auth)])
def model_fit_agent(agent: str, project: str = Query(...)):
    from core import model_fit
    rep = model_fit.load_report(str(PRODUCTS / project))
    if not rep:
        raise HTTPException(404, "no report")
    return {"agent": agent,
            "entries": [e for e in rep.get("entries", []) if e.get("agent") == agent]}


@app.post("/api/v1/model-fit/run", dependencies=[Depends(auth)])
def model_fit_run_endpoint(body: Dict[str, Any]):
    """Run the fit for a project using its resolved tier (probe each model)."""
    from core import model_fit
    project = body.get("project")
    if not project:
        raise HTTPException(400, "project required")
    try:
        from core.pipeline_executor import PipelineExecutor
        ex = PipelineExecutor(project, products_dir=str(PRODUCTS))
        cfg_all = ex.model_router.load_tier_config() or {}
        prof = ex.model_router.active_profile() or {}

        def _probe(model, provider, endpoint, max_tokens):
            import time as _t
            t0 = _t.time()
            try:
                text, _m = ex.llm._call_llm_single(
                    "Reply with exactly this sentence and nothing else: "
                    "The quick brown fox jumps over the lazy dog.",
                    model, provider, endpoint, session_id=f"fit-{model}",
                    agent_id="model_probe", stage_id="preflight",
                    max_output_tokens=max_tokens or 700, fast_fail=True)
            except Exception as e:
                return {"ok": False, "content_len": 0, "error": str(e)}
            txt = (text or "").strip()
            return {"ok": bool(txt), "content_len": len(txt),
                    "latency_ms": int((_t.time() - t0) * 1000),
                    "error": "" if txt else "empty content"}

        merged = {"provider": prof.get("provider") or cfg_all.get("provider", ""),
                  "api_endpoint": prof.get("api_endpoint") or cfg_all.get("api_endpoint", ""),
                  "models": {**(cfg_all.get("models") or {}), **(prof.get("models") or {})},
                  "agents": prof.get("agents") or cfg_all.get("agents") or {}}
        report = model_fit.run(merged, _probe)
        model_fit.save_report(str(PRODUCTS / project), report)
        return report
    except Exception as e:
        raise HTTPException(500, str(e))


# ── project archive / soft-delete (BI-0071) ──────────────────────────────────
@app.get("/api/v1/projects/archived", dependencies=[Depends(auth)])
def projects_archived():
    from core.project_archive import list_archived
    return {"archived": list_archived()}


@app.post("/api/v1/projects/{project}/archive", dependencies=[Depends(auth)])
def projects_archive(project: str):
    from core.project_archive import archive
    r = archive(project)
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "archive failed"))
    return r


@app.post("/api/v1/projects/{project}/restore", dependencies=[Depends(auth)])
def projects_restore(project: str):
    from core.project_archive import restore
    r = restore(project)
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "restore failed"))
    return r


@app.post("/api/v1/projects/purge-due", dependencies=[Depends(operator_guard)])
def projects_purge_due():
    from core.project_archive import purge_due
    return {"purged": purge_due()}


# ── agent memory (BI-0054: wires core/memory_api into the API surface) ───────
@app.get("/api/v1/memory", dependencies=[Depends(auth)])
def memory_export(project: str = Query(...)):
    try:
        from core.memory_api import MemoryAPI
        return MemoryAPI(str(PRODUCTS), project).export_all()
    except Exception as e:
        raise HTTPException(500, f"memory unavailable: {e}")


# ── licensing (BI-0057/0059..0069) ───────────────────────────────────────────
@app.get("/api/v1/instance")
def instance():
    from core import licensing
    return {"role": licensing.instance_role()}


@app.get("/api/v1/licensing/tiers")
def licensing_tiers():
    from core import licensing
    return {"tiers": licensing.tiers(), "feature_groups": licensing.FEATURE_GROUPS}


@app.get("/api/v1/licensing/entitlements", dependencies=[Depends(auth)])
def licensing_entitlements(tier: str = Query(""), tenant: str = Query("")):
    from core import licensing
    if tenant and not tier:
        rec = licensing.load_tenants().get(tenant) or {}
        tier = rec.get("tier", "trial")
    return licensing.entitlements(tier or "trial")


@app.get("/api/v1/licensing/keys", dependencies=[Depends(operator_guard)])
def licensing_keys():
    from core import licensing
    return {"keys": licensing.load_licenses()}


@app.get("/api/v1/licensing/keys/verify")
def licensing_verify(key: str = Query(...)):
    from core import licensing
    return {"valid": bool(licensing.verify_key(key)), "payload": licensing.verify_key(key)}


@app.post("/api/v1/licensing/keys", dependencies=[Depends(operator_guard)])
def licensing_issue(body: Dict[str, Any]):
    from core import licensing
    tenant = body.get("tenant")
    if not tenant:
        raise HTTPException(400, "tenant required")
    key = licensing.issue_key(tenant, body.get("tier", "trial"), seats=body.get("seats"),
                              concurrency=body.get("concurrency"),
                              trial_days=int(body.get("trial_days", 0)),
                              days=int(body.get("days", 365)))
    return {"key": key, "payload": licensing.verify_key(key)}


@app.post("/api/v1/licensing/keys/revoke", dependencies=[Depends(operator_guard)])
def licensing_revoke(body: Dict[str, Any]):
    from core import licensing
    return {"revoked": licensing.revoke_key(str(body.get("key") or ""))}


@app.post("/api/v1/licensing/keys/extend", dependencies=[Depends(operator_guard)])
def licensing_extend(body: Dict[str, Any]):
    from core import licensing
    r = licensing.extend_key(str(body.get("key") or ""), int(body.get("days", 30)))
    if not r:
        raise HTTPException(400, "invalid key")
    return r


@app.get("/api/v1/licensing/tenants", dependencies=[Depends(operator_guard)])
def licensing_tenants():
    from core import licensing
    return {"tenants": licensing.load_tenants()}


@app.post("/api/v1/licensing/tenants", dependencies=[Depends(operator_guard)])
def licensing_provision(body: Dict[str, Any]):
    from core import licensing
    name = body.get("name")
    if not name:
        raise HTTPException(400, "name required")
    try:
        return licensing.provision_tenant(name, body.get("tier", "trial"),
                                          body.get("owner_email", ""),
                                          int(body.get("trial_days", 0)))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/v1/licensing/trials/expire", dependencies=[Depends(operator_guard)])
def licensing_expire():
    from core import licensing
    return {"expired": licensing.expire_trials()}


# ── build-time separation (BI-0070) ──────────────────────────────────────────
# Operator-only routes are REMOVED from a tenant build (not merely hidden); the
# runtime operator_guard remains as defense-in-depth. BUILD_ROLE is set at build
# time by scripts/dev/build_release.py; it defaults to the runtime INSTANCE_ROLE.
_OPERATOR_PATH_PREFIXES = (
    "/api/v1/licensing/keys",
    "/api/v1/licensing/tenants",
    "/api/v1/licensing/trials",
    "/api/v1/projects/purge-due",
    "/api/v1/cp/tenants",
)


def build_role() -> str:
    r = os.getenv("BUILD_ROLE") or os.getenv("INSTANCE_ROLE", "tenant")
    r = r.strip().lower()
    return r if r in ("operator", "tenant") else "tenant"


def _apply_build_role() -> None:
    if build_role() == "operator":
        return
    app.router.routes = [
        r for r in app.router.routes
        if not (getattr(r, "path", "") or "").startswith(_OPERATOR_PATH_PREFIXES)
    ]


_apply_build_role()


# ── New-capability API-first surface (BI-0122) ─────────────────────────────
# Stages/phases + per-agent prompt & capability bindings. The dashboard consumes
# ONLY these routes; the pipeline stays the single source of truth.

_CONFIG = REPO / "config"


@app.get("/api/v1/pipeline/stages", dependencies=[Depends(auth)])
def pipeline_stages():
    """All stages with presentation metadata (display_id, phase) + deps/gates."""
    with open(_CONFIG.parent / "pipeline-definition.json", encoding="utf-8-sig") as f:
        d = json.load(f)
    WANT = ("name", "display_id", "phase", "ideal_flow", "depends_on",
            "approval_gate", "optional", "parallel_safe", "budget_limit")
    out = []
    for sid, st in (d.get("stages") or {}).items():
        out.append({"id": sid, **{k: st.get(k) for k in WANT}})
    return {"version": d.get("version"), "count": len(out), "stages": out}


@app.get("/api/v1/pipeline/agents/{agent}", dependencies=[Depends(auth)])
def agent_binding(agent: str):
    """One agent's role prompt + declared capability bindings (SSOT)."""
    card = REPO / "agents" / f"{agent}.agent.json"
    if not card.exists():
        raise HTTPException(404, f"unknown agent: {agent}")
    with open(card, encoding="utf-8") as f:
        spec = json.load(f)
    bindings = {}
    try:
        with open(_CONFIG / "agent-capabilities.json", encoding="utf-8") as f:
            bindings = (json.load(f).get("agents") or {}).get(agent, {})
    except Exception:
        pass
    return {"id": agent, "name": spec.get("name"), "mode": spec.get("mode"),
            "model_tier": spec.get("model_tier"), "tools": spec.get("tools"),
            "skills": spec.get("skills"), "knowledge_layers": spec.get("knowledge_layers"),
            "allowed_inputs": spec.get("allowed_inputs"), "sub_agents": spec.get("sub_agents"),
            "capability_bindings": bindings}


@app.get("/api/v1/pipeline/agents", dependencies=[Depends(auth)])
def agent_list():
    """All agent cards (id/name/mode/tier) for the dashboard registry view."""
    out = []
    adir = REPO / "agents"
    for p in sorted(adir.glob("*.agent.json")):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            out.append({"id": d.get("id"), "name": d.get("name"), "mode": d.get("mode"),
                        "model_tier": d.get("model_tier"), "sub_agents": d.get("sub_agents") or []})
        except Exception:
            continue
    return {"count": len(out), "agents": out}


@app.get("/api/v1/capabilities", dependencies=[Depends(auth)])
def capability_bindings():
    """The per-agent capability binding matrix (knowledge/skills/MCP/domain/business)."""
    try:
        with open(_CONFIG / "agent-capabilities.json", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        raise HTTPException(500, f"capability config unreadable: {e}")
    return d


# ── BI-0115 tailoring + BI-0116 templates ──────────────────────────────────
def _pipeline_def() -> Dict[str, Any]:
    with open(REPO / "pipeline-definition.json", encoding="utf-8-sig") as f:
        return json.load(f)


@app.get("/api/v1/pipeline/tailoring/{project}", dependencies=[Depends(auth)])
def tailoring_get(project: str):
    """The per-project plan (or a fresh recommendation if none saved)."""
    from core import pipeline_tailoring as pt
    pdir = str(PRODUCTS / project)
    plan = pt.load_plan(pdir)
    return {"saved": bool(plan), "plan": plan or pt.build_plan(_pipeline_def(), pdir)}


@app.post("/api/v1/pipeline/tailoring/{project}", dependencies=[Depends(auth)])
def tailoring_set(project: str, body: Dict[str, Any]):
    """Accept/override the tailoring: {enable: [...], disable: [...]} -> writes pipeline-plan.json."""
    from core import pipeline_tailoring as pt
    pdir = str(PRODUCTS / project)
    plan = pt.build_plan(_pipeline_def(), pdir, enabled=body.get("enable"), disabled=body.get("disable"),
                         actor=body.get("actor", "dashboard"))
    return {"saved": pt.save_plan(pdir, plan), "plan": plan}


@app.get("/api/v1/pipeline/templates", dependencies=[Depends(auth)])
def pipeline_templates():
    """Available pipeline templates (pipeline_templates/)."""
    out = []
    tdir = REPO / "pipeline_templates"
    for d in sorted(tdir.glob("*/template.json")):
        try:
            with open(d, encoding="utf-8") as f:
                t = json.load(f)
            out.append({"id": t.get("id") or d.parent.name, "name": t.get("name"),
                        "category": t.get("category"), "description": t.get("description"),
                        "stages": len(t.get("stages") or {}), "agents": list((t.get("agents") or {}).keys())})
        except Exception:
            continue
    return {"count": len(out), "templates": out}


# ── BI-0086/0089 git config + history ──────────────────────────────────────
@app.get("/api/v1/projects/{project}/git", dependencies=[Depends(auth)])
def git_history(project: str, limit: int = 100):
    """Per-project git config + history (check-ins/tags/branches). Read-only."""
    from core.vcs import VCSManager
    pdir = str(PRODUCTS / project)
    try:
        mgr = VCSManager(pdir)
        h = mgr.history(limit=limit)
        return {"project": project, "config": mgr.cfg, "is_repo": h.get("is_repo"),
                "current_branch": h.get("current_branch"), "checkins": h.get("checkins", [])}
    except Exception as e:
        raise HTTPException(500, f"git history failed: {e}")


@app.post("/api/v1/projects/{project}/git", dependencies=[Depends(auth)])
def git_config_set(project: str, body: Dict[str, Any]):
    """Connect/create a project's git repo config (provider/remote/branch model)."""
    from core.vcs import VCSManager
    pdir = str(PRODUCTS / project)
    if not (PRODUCTS / project).exists():
        raise HTTPException(404, f"unknown project: {project}")
    path = VCSManager.save_config(pdir, body or {})
    return {"saved": path, "config": VCSManager.load_config(pdir)}


@app.get("/metrics")
def metrics():
    """BI-0094: Prometheus text exposition (from pipeline_telemetry + quality metrics)."""
    lines: List[str] = []
    lines.append("# HELP product_forge_info Static info about the Product Forge pipeline")
    lines.append("# TYPE product_forge_info gauge")
    lines.append("product_forge_info{app=\"dashboard-api\"} 1")
    try:
        from core import pipeline_telemetry
        tdir = REPO / "products"
        for pdir in sorted(tdir.iterdir()) if tdir.exists() else []:
            if not pdir.is_dir() or pdir.name.startswith(".") or pdir.name.startswith("_"):
                continue
            try:
                tel = pipeline_telemetry.build_telemetry(pdir.name, str(tdir))
            except Exception:
                continue
            tot = (tel.get("totals") or {}) if isinstance(tel, dict) else {}
            proj = pdir.name
            lines.append(f'product_forge_project_tokens{{project="{proj}"}} {int(tot.get("total_tokens", 0) or 0)}')
            lines.append(f'product_forge_project_cost_usd{{project="{proj}"}} {float(tot.get("total_cost", 0.0) or 0.0)}')
    except Exception:
        pass
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


# ── BI-0096 review ledger + BI-0117 dynamic agent creation ──────────────────
@app.get("/api/v1/projects/{project}/reviews", dependencies=[Depends(auth)])
def reviews_get(project: str):
    from core import review_ledger as rl
    return rl.load(str(PRODUCTS / project))


@app.post("/api/v1/projects/{project}/reviews", dependencies=[Depends(auth)])
def reviews_add(project: str, body: Dict[str, Any]):
    from core import review_ledger as rl
    if body.get("resolve"):  # resolve an existing entry
        return rl.resolve(str(PRODUCTS / project), body["id"], body.get("resolution", ""),
                          body.get("status", "resolved")) or {}
    return rl.record(str(PRODUCTS / project), body.get("producer", ""), body.get("artifact", ""),
                     body.get("reviewer", ""), body.get("feedback", ""),
                     body.get("severity", "major"), body.get("stage", ""))


@app.get("/api/v1/agents/templates", dependencies=[Depends(auth)])
def agent_create_template():
    """The spec shape accepted by POST /api/v1/agents (BI-0117)."""
    return {"required": ["id", "name", "role", "artifact"],
            "optional": ["description", "decides", "notd", "inputs", "outputs", "tier",
                         "tools", "skills", "knowledge", "sub_agents", "format"],
            "id_rule": "kebab-case [a-z][a-z0-9-]{1,40}"}


@app.post("/api/v1/agents", dependencies=[Depends(auth)])
def agent_create(body: Dict[str, Any]):
    """Create/register a MAIN agent dynamically (validated)."""
    from core import review_ledger as rl
    res = rl.create_agent(body, register=bool(body.get("register", True)))
    if not res.get("ok"):
        raise HTTPException(422, res.get("errors"))
    return res


@app.get("/api/v1/blueprint", dependencies=[Depends(auth)])
def blueprint_get():
    """BI-0092: the reusable dashboard+API blueprint + its instantiation surfaces."""
    from core import dashboard_blueprint as bp
    return bp.load_blueprint()


# ── Rerun review (GENERAL: any restart / stage / agent re-run) ──────────────
@app.get("/api/v1/projects/{project}/rerun-review", dependencies=[Depends(auth)])
def rerun_review_get(project: str, from_stage: str = "", only_stage: str = "",
                     agent: str = "", phase: str = ""):
    """Show what exists + recommendations for the given rerun scope (same as the CLI)."""
    from core import rerun_review as rr
    scope = {"from_stage": from_stage or None,
             "only_stages": [s for s in only_stage.split(",") if s],
             "agents": [a for a in agent.split(",") if a],
             "phase": phase or None}
    rv = rr.build(str(PRODUCTS / project), project, scope)
    return {"review": rv, "rendered": rr.present(rv)}


@app.post("/api/v1/projects/{project}/rerun-review", dependencies=[Depends(auth)])
def rerun_review_decide(project: str, body: Dict[str, Any]):
    """Record the operator's decision: continue | accept-recommendations | reject."""
    from core import rerun_review as rr
    decision = str(body.get("decision") or "continue").lower()
    if decision not in ("continue", "accept-recommendations", "reject"):
        raise HTTPException(422, "decision must be continue|accept-recommendations|reject")
    return rr.decide(str(PRODUCTS / project), decision, body.get("note", ""))


def main():
    import uvicorn
    port = int(os.getenv("DASHBOARD_API_PORT", "8000"))
    uvicorn.run(app, host=os.getenv("DASHBOARD_API_HOST", "0.0.0.0"), port=port)


if __name__ == "__main__":
    main()
