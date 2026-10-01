# API-0 — API Discovery

**Phase:** API-0 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md`
**Status:** Discovery complete — gate PASS
**Depends on:** MASTER-0 (`docs/MASTER-0-CURRENT-STATE-TRUTH.md`)
**Scope note (binding, user directive):** the legacy Dashboard is **out of scope**. All new API work goes to a
**new canonical `api/` surface**; `dashboard/` (including `dashboard/api/app.py` and `dashboard/server.py`) is
frozen legacy and will only ever be a *client* of the canonical API.

---

## 1. Current API server (legacy location)

| Field | Value |
|---|---|
| Server | FastAPI `app` — `dashboard/api/app.py:44` |
| Launch | `python -m dashboard.api.app` (`app.py:1610-1616`, default port 8000); CLI `productforge dashboard` (`core/main.py:127-133`, default 3001) |
| Defined how | decorators on `app`; **no `APIRouter`/`include_router`/`mount`** |
| Auth | `auth()` `:60`, `operator_guard()` `:69`, `tenant_guard()` `:90` |
| OpenAPI | FastAPI auto `/openapi.json` (no committed canonical schema) |
| Legacy 2nd server | `dashboard/server.py` stdlib `ThreadingHTTPServer` (frozen legacy) |

**Decision:** this is the *legacy* surface. It stays untouched. The canonical API control-plane is built fresh in
`api/` and becomes the contract SSOT. The legacy app may be wrapped/adapted later without edits.

## 2. Current API entrypoint & consumers

| Consumer | How it talks to PF today |
|---|---|
| CLI | `scripts/run_pipeline.py` (pipeline); `core.main:main` (dashboard branch) |
| OpenCode adapter | `.opencode/command/*` → CLI (`scripts/run_pipeline.py`); **not** an architectural dependency |
| MCP server | `core/mcp.py` (tools over `core/tool_registry`) exposed via legacy `app.py` `/api/v1/mcp/*` |
| MCP client | `adapters/claude/server.py` (stdio JSON-RPC → REST `/api/v1/intake`) |
| Browser adapters | `adapters/{chatgpt,claude,gemini}` POST `/api/v1/intake` |
| `.opencode` | client surface only (per plan §2.2, §30) |

## 3. Current Intake path (live)

```
POST /api/v1/intake (legacy app.py:527)
  → core/intake.py:61 ingest()
  → core/intake_adapters.normalize()/to_conversation()  (raw → products/inbox/<source>/)
  → store.save_conversation()  · core/intake_channels.add_item() (IN-####)
  → core/intent_router.py:71 IntentRouter.process_conversation()
      → core/backlog_link.py:115 promote_conversation() → core/backlog.py
      → new_project → intent_router.py:575 _start_pipeline() → PipelineExecutor.execute_pipeline() (thread)
```

**Defect found:** `_run_pipeline_thread` (`intent_router.py:608-611`) calls `execute_pipeline()` **without**
`run_entry.begin_run` → blocked by run-lock guard (`pipeline_executor.py:2994-3005`) unless
`PIPELINE_ALLOW_UNGUARDED=1`. Must be reconciled in API-1.

**Stale comments:** `core/intent_router.py:1-4` correctly says intake is NOT replaced by PipelineExecutor, but
`core/intake_api.py:1`, `core/main.py:1`, `conversation_*.py:1`, `global_orchestrator.py:1`,
`product_ingestion.py:1`, `product_analyzer.py:1` carry the wrong blanket deprecation; `docs/UNWIRED-MODULES-TRIAGE.md:35-40`
contradicts. Fix in API-1.

## 4. Existing application services

No `services/` package — API imports `core/*` directly. Services: `core/intake.py`, `core/run_entry.py`
(`begin_run:20`/`end_run:94`/`enqueue:116`), `core/control_plane.py:34` (SQLite tenants/users), `core/job_manager.py`,
`core/intake_channels.py` (funnel actions **not exposed by any route**).

## 5. Existing contracts & tests

- **OpenAPI:** FastAPI auto only; hand-written `adapters/chatgpt/schema.yaml` (intake). No canonical committed schema.
- **Tests:** `test-framework/tests/pipeline/` (108 files). **No API/contract tests** exercising routes; no test for
  intake path, auth, idempotency, or error envelope.

## 6. Duplicate mechanisms (relevant to API)

| # | Duplicate | Canonical |
|---|---|---|
| A1 | Two HTTP servers (FastAPI legacy + stdlib `dashboard/server.py`) | new `api/` |
| A2 | Route definitions only in legacy app (no router modules) | new `api/` routers |
| A3 | Two issue stores; two event streams; two Git managers (see MASTER-0 D1–D8) | per MASTER-0 |

## 7. Required changes (API program)

1. **API-0.1** contract reconciliation: request/response/error envelopes, request_id/correlation_id, tenant_id,
   actor/authorization, idempotency_key, api_version, pagination, deprecation, OpenAPI ownership.
2. **API-1** foundation in new `api/`: app boundary, `/api/v1`, request context (IDs), auth/authz boundary, tenant
   context, common errors, idempotency, audit, health/readiness, OpenAPI foundation, pagination/filter conventions.
   Establish/reuse the **direct engineering control surface** (`OpenCode/CLI → Task/Work API → task/run/worker`).
   Keep **Intake as an external ingestion path only** (it enqueues through `run_entry`; fix stale deprecations) —
   **without editing `dashboard/`**. Two independent entry paths; Intake is not an engineering prerequisite (§2A).
3. **API-2** core PF APIs: project → run → pipeline → stage → task → artifact → evidence → backlog, via canonical services.
4. **API-3** engineering/validation APIs: validation, evidence, defect/RCCA, test, gate, git/vcs, task, worker, agent.
5. **API-5** hardening: contract governance, security, contract tests, event API formalization.

## 8. Affected files / dependencies / risks

- **New:** `api/` package (app, routers, contracts, middleware, errors, auth, idempotency, events).
- **Reuse (canonical):** `core/backlog.py`, `core/run_entry.py`, `core/pipeline_executor.py`, `core/issues.py`,
  `core/events.py`, `core/artifact_store.py`, `core/agent_ledger.py`, `core/control_plane.py`, `config/store-registry.json`.
- **Risks:** (R1) route parity with legacy app needed for consumers (adapters target `/api/v1/intake`); (R2) auth
  model decision — `auth()` vs `operator_guard` vs `tenant_guard` must become a documented boundary; (R3) port
  defaults mismatch (8000/3001/8765); (R4) intake→run_entry lock gap; (R5) `wired_audit` requires every new store
  registered + every new core module imported on a runtime path.

## 9. Unknowns

- Whether legacy `dashboard/api/app.py` should later be replaced by an adapter shim (deferred).
- Canonical OpenAPI ownership (generate+commit vs served) — resolve in API-1/API-5.
- Tenant model scope for community/enterprise (API-4).

---

## API-0 Gate

| Criterion (plan §6) | Result |
|---|---|
| Current API server identified | ✅ (legacy `dashboard/api/app.py`, frozen) |
| Current API entrypoint identified | ✅ |
| Current Intake path traced | ✅ (+ lock-gap defect) |
| Current API consumers identified | ✅ |
| Existing contracts identified | ✅ (auto OpenAPI only; no canonical) |
| Existing tests identified | ✅ (no API/contract tests → gap) |
| Existing application services identified | ✅ |
| Duplicate mechanisms identified | ✅ (A1–A3, +MASTER-0 D1–D8) |
| Unknowns recorded | ✅ |
| Required changes listed | ✅ |
| Affected files/dependencies/risks listed | ✅ |

**API-0 GATE: PASS.** Proceed to API-0.1 (contract reconciliation) before any API code.

**Binding scope decisions carried forward:** new `api/` surface = canonical; `dashboard/` frozen legacy; OpenCode =
adapter only; no duplicate engines/stores.
