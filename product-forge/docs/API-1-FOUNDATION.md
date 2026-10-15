# API-1 — API Foundation

**Phase:** API-1 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md`
**Status:** Implemented — gate PASS
**Depends on:** API-0 (`docs/API-0-DISCOVERY.md`), API-0.1 (`docs/API-0.1-CONTRACT-RECONCILIATION.md`)

## Governance: API-first, language, and service topology (ADR-0007 / ADR-0008)

Binding for everything built in Product Forge (rationale in `docs/ARCHITECTURE-DECISIONS.md`):

1. **API-first (need-assessed).** For each capability, assess whether an API is needed; where an internal or
   external consumer needs it, expose a **secured** API — authn, authz/tenant scope, input validation,
   quotas/rate limits, audit, and a versioned contract. No blind APIs: if none is needed, record the
   justification at Gate 1.
2. **Each service owns its language.** New shipped/sensitive logic is **Go** (language rule, BI-PF-0387/0388).
   Go-backed capabilities are exposed by **Go API services**, never bridged through the Python API (no
   subprocess/cgo on a request path). Python API routes stay thin (validate + delegate only).
3. **Service topology / placement.** Domain data ⇒ that domain's service; cross-cutting ⇒ generic surface:
   - **EDP data-plane service (Go):** the system of record and everything operating it (schema,
     tenants/projects/runs/stages/attempts/artifacts/objects, object store, RLS, quotas, audit,
     **schema-migration admin**).
   - **Generic capability service (Go):** cross-cutting Go capabilities (e.g., backlog **doc-ingest**), which
     consume other services over HTTP.
   - **Python control-plane API (`api/`):** existing Python-owned concerns (backlog, engineering, …).
4. **Integration is over HTTP APIs only** — services consume each other's APIs; no language bridges.
5. All surfaces share the **same security model** (authn roles, authz/tenant scope, validation, quotas, audit).

**Enforced at Gate 1:** every item declares its **API-surface decision** (surface + security, or a written
"no API need") **and** its service home.

## What this phase builds

The canonical HTTP control plane in a **new `api/` package** (the legacy `dashboard/` app is frozen and untouched;
it becomes a *client* later). It implements the API-0.1 contract.

```
api/
  __init__.py        expose app
  app.py             FastAPI app, /api/v1, middleware + handlers + routers
  context.py         request_id / correlation_id / tenant / actor middleware
  errors.py          canonical ApiError + envelope-rendering exception handlers (fail-closed, redacted)
  envelope.py        canonical success envelope helper
  auth.py            authN/authZ boundary (Bearer + roles; fail-closed; API_ALLOW_ANON dev-only)
  idempotency.py     single writer of data/api/idempotency.json (replay/conflict, TTL-bounded)
  routers/health.py  /health, /ready (+ under /api/v1)
  routers/intake.py  POST /api/v1/intake (reuses core.intake.ingest; idempotency-aware)
scripts/dev/api_contract_check.py   exercises the surface (wired into precheck)
test-framework/tests/pipeline/test_api_foundation.py   8 tests
```

## Two entry paths (updated plan §2A)

Intake is an **external ingestion** path only. The **direct engineering** control surface is
`OpenCode/CLI/coding agent/human → Task/Work API → task/run/worker` — delivered in **ENG-1**
(`core/task_contract.py` + `/api/v1/engineering/tasks`). The paths are **independent**: Intake is not a
prerequisite for engineering work, and engineering work does not create a conversation record.

## Reuse (no duplicate engines/stores)

- **Intake (external ingestion):** reuses the canonical facade `core.intake.ingest` unchanged. It ingests →
  work item and enqueues execution via `core.run_entry`; it is **not** an engineering prerequisite.
- **Readiness:** probes the canonical `core.backlog` + `core.events` stores (no shadow store).
- **Events:** all canonical; no new event source of truth.
- **Config:** adds flags `PF_API_TOKEN` (canonical; `API_TOKEN` deprecated alias), `API_ALLOW_ANON`, `API_PORT`, `API_ALLOW_ORIGINS` (owner `api/*`).
- **Store registry:** registers `idempotency.json` (owner `api/idempotency.py`, kind=state).

## Contract behaviours delivered (API-0.1)

| Contract element | Delivered |
|---|---|
| `/api/v1` base | ✅ (health/ready also under `/api/v1`) |
| request/correlation IDs | ✅ issued + echoed (`X-Request-Id`/`X-Correlation-Id`), in every envelope |
| success envelope | ✅ `request_id, correlation_id, status, resource, resource_id, data, links, warnings, error` |
| error model | ✅ `code, message, category, retryable, details, request_id, correlation_id` + HTTP map |
| fail-closed / redaction | ✅ missing token ⇒ 401; secrets redacted from messages; no stack traces |
| idempotency | ✅ required-key path, replay returns stored result, in-flight ⇒ 409 |
| auth boundary | ✅ Bearer + roles; `operator`/`tenant` deps; public health/ready |
| health/readiness | ✅ `/health`, `/ready`, `/api/v1/health`, `/api/v1/ready` |

## 360° dependency check

- New package `api/` is outside `wired_audit` scan roots (core/scripts/dashboard/adapters/test-framework), so no
  UNWIRED false positive; it is exercised by `api_contract_check.py` (precheck) and unit tests.
- No edits to `dashboard/` (frozen). No new pipeline/validation/backlog/artifact/event/Git engines.
- Intake route does **not** inline-run the pipeline, so the run-lock gap (`intent_router._start_pipeline`) is not
  reachable through this surface; execution stays `core.run_entry`-owned (its permanent fix belongs to the intake
  reconciliation follow-up, tracked, not done in legacy dashboard code).

## Verification (executed)

```
python -m compileall -q core scripts dashboard api        # 0
python scripts/dev/wired_audit.py                         # OK (legacy-frozen OK)
python scripts/dev/api_contract_check.py                  # api-contract: OK
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # 729 passed, 1 skipped
```
`precheck` now includes the `api-contract` step and compiles `api`.

## Gate

| Criterion (plan §8) | Result |
|---|---|
| API starts / reachable | ✅ in-process TestClient + uvicorn entry |
| auth works / fail-closed | ✅ 401 without token when required |
| authz works | ✅ operator/tenant dependencies present |
| tenant isolation | ✅ tenant dep requires header (enforcement expands in API-2/3) |
| errors conform | ✅ canonical error contract |
| IDs propagate | ✅ |
| idempotency works | ✅ replay + conflict |
| External ingestion (Intake) works | ✅ via canonical facade; enqueues via `run_entry` (no direct executor) |
| Direct engineering control surface | ✅ delivered ENG-1 (`/api/v1/engineering/tasks`); intake not required |
| OpenAPI validates | ✅ FastAPI `/openapi.json` (committed schema + drift check = API-5) |
| API tests pass | ✅ 8 tests + contract check |

**API-1 GATE: PASS.** Proceed to API-2 (core PF APIs), then API-3.
