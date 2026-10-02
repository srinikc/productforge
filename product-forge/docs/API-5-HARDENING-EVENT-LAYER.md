# API-5 — API Hardening & Event Layer

**Phase:** API-5 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§18)
**Status:** Implemented (contract governance + event layer) — gate PASS
**Depends on:** API-1..API-3, ENG-5

## What this phase builds

1. **Contract governance** — a committed **canonical OpenAPI** (`api/openapi.json`) generated from `api.app`,
   plus a gate that fails on drift (**basic breaking-change detection**).
2. **Event layer** — the formal event envelope added **additively** to the existing owner `core/events.py`
   (single writer via `core/log_router`), and a read-only **Event API**.
3. **Security** — verify the existing controls; track the remaining hardening as backlog.

```
api/openapi.json                     # committed canonical schema (API-5)
scripts/dev/api_governance_check.py  # regenerate/compare; fails on drift (precheck gate)  [registered store]
core/events.py                       # + formal envelope fields (additive; owner unchanged)
api/routers/events.py                # GET /api/v1/events [+ /types]
```

## Contract governance (§18)

- `python scripts/dev/api_governance_check.py --write` regenerates `api/openapi.json`.
- `python scripts/dev/api_governance_check.py` (in precheck) compares the committed schema to the live app and
  reports **added/removed paths** — a change to a committed route is a breaking-change signal.
- `/api/v1` versioning is fixed; breaking changes require an explicit schema update (reviewed).

## Event layer (§18/§33)

`core/events.emit` now carries the formal envelope, **additively** (legacy flat fields kept for back-compat):

```
event_id · event_type · event_version · occurred_at · tenant_id · project_id · run_id · stage_id
task_id · worker_id · actor · correlation_id · causation_id · payload
```

The Event API is **read-only** (events are projections/history, never canonical state):

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/events/types` | canonical event types + envelope version |
| GET | `/api/v1/events?project&limit&since` | run-bound event stream (read-only) |

Streaming transports (SSE / WebSocket / AG-UI) are a follow-up (**tracked**); `core/agui.py` already exists.

## Security (§18) — verified vs deferred

**Verified present:** authentication/authorization (`api/auth.py`), secret redaction (`api/errors._redact`),
idempotency/replay protection (`api/idempotency.py`), path validation (routers), CORS (`api/app.py`),
error contract + request/correlation IDs.
**Deferred (tracked as a backlog item):** rate limiting, request/upload size limits, tenant-isolation
expansion, event streaming.

## 360° dependency check

- Events reuse the EXISTING single writer (`core/events.py` → `log_router`); **no second event store** (plan §41).
- `api/openapi.json` is a registered **derived** store (owner `scripts/dev/api_governance_check.py`).
- No edits to `dashboard/` (frozen); no duplicate engines/stores.
- Wired: governance gate in precheck; Event API mounted in `api/app.py`.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python scripts/dev/api_governance_check.py                        # api-governance: OK (71 paths, in sync)
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §18)

| Criterion | Result |
|---|---|
| Canonical OpenAPI committed | ✅ `api/openapi.json` (71 paths) |
| Breaking-change detection | ✅ `api_governance_check` (path/method drift) |
| Event envelope formalized | ✅ additive fields on `core/events.emit` (owner unchanged) |
| Event API exposed | ✅ `/api/v1/events[/types]` (read-only) |
| Existing security verified | ✅ auth/redaction/idempotency/CORS/path validation |
| Remaining hardening tracked | ✅ backlog item (rate limit/size/tenant/streaming) |
| No shadow event store | ✅ single writer `core/events.py` |

**API-5 GATE: PASS.** Next: **ENG-6 — Common Validation Engine**.
