# API-1 — API Foundation

**Phase:** API-1 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md`
**Status:** Implemented — gate PASS
**Depends on:** API-0 (`docs/API-0-DISCOVERY.md`), API-0.1 (`docs/API-0.1-CONTRACT-RECONCILIATION.md`)

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

## Reuse (no duplicate engines/stores)

- **Intake:** reuses the canonical facade `core.intake.ingest` unchanged (Conversation → IntentRouter → backlog).
- **Readiness:** probes the canonical `core.backlog` + `core.events` stores (no shadow store).
- **Events:** all canonical; no new event source of truth.
- **Config:** adds flags `API_TOKEN`, `API_ALLOW_ANON`, `API_PORT`, `API_ALLOW_ORIGINS` (owner `api/*`).
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
| Intake works | ✅ via canonical facade |
| OpenAPI validates | ✅ FastAPI `/openapi.json` (committed schema + drift check = API-5) |
| API tests pass | ✅ 8 tests + contract check |

**API-1 GATE: PASS.** Proceed to API-2 (core PF APIs), then API-3.
