# API-0.1 — Contract Reconciliation

**Phase:** API-0.1 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md`
**Status:** Reconciled — gate PASS (contract fixed before any API code)
**Depends on:** API-0 (`docs/API-0-DISCOVERY.md`), MASTER-0 (`docs/MASTER-0-CURRENT-STATE-TRUTH.md`)

This document fixes the canonical HTTP contract for the new `api/` surface. It is the SSOT for envelopes, IDs,
errors, idempotency, auth boundary, versioning and OpenAPI ownership. No API code is written until this is fixed.

---

## 1. Canonical base

- Base path: **`/api/v1`** (single version root; unversioned only for `/health`, `/.well-known/*`, `/metrics`).
- Media type: `application/json` (events endpoint: `text/event-stream`).
- Transport: REST = command/query; **events** = long-running progress (SSE), per plan §18/§33.
- Resource naming: **plural, kebab-case, no verbs** in paths (`/projects`, `/runs`, `/backlog`, `/validation-runs`).
  Actions only where no resource exists → sub-resource noun (`/runs/{id}/stop`) or `POST .../actions` — prefer noun
  sub-resources. Query params: `snake_case` (`?project_id=`, `?limit=`, `?cursor=`).

## 2. Request context (headers + body)

| Field | Location | Required | Notes |
|---|---|---|---|
| `request_id` | header `X-Request-Id` (or generated) | no | server generates if absent; echoed back |
| `correlation_id` | header `X-Correlation-Id` | no | groups a logical operation across services/runs; defaults to request_id |
| `tenant_id` | header `X-Tenant-Id` or from auth claim | conditional | required for tenant-scoped routes |
| `actor` | from auth token / `X-Actor` | conditional | identity performing the action |
| `authorization` | `Authorization: Bearer <token>` | yes (except public) | boundary enforced in `api/` |
| `idempotency_key` | header `Idempotency-Key` | required for unsafe POST/PUT that create | replays return prior result |
| `api_version` | path `/v1` (header `X-Api-Version` optional override) | path yes | see §6 |
| `resource` / `operation` | path + method | yes | derived, echoed in response |

**Canonical request body wrapper** (when a body is wrapped):
```yaml
request_id:      # optional (header preferred)
correlation_id:  # optional
tenant_id:       # optional
actor:           # optional
payload: {}      # the operation's data
```

## 3. Canonical response envelope (success)

Every JSON response (except SSE) is:
```yaml
request_id:     # echoed/generated
correlation_id: # echoed/generated
status:         ok | accepted | error     # HTTP status also set
resource:       # e.g. "run"
resource_id:    # e.g. "run-1736..."
data: {}        # the resource/result
links: {}       # {"self": "...", "next": "...", "related": {...}}
warnings: []    # non-fatal advisories
error: null     # null on success; object on failure (see §4)
```
**Compatibility rule:** an envelope wrapper is applied consistently by a single response helper. Raw legacy
shapes are *not* mutated; the new `api/` always wraps.

## 4. Canonical error model

```yaml
code:           # stable machine code, SCREAMING_SNAKE, e.g. NOT_FOUND, VALIDATION_FAILED, IDEMPOTENCY_CONFLICT
message:        # human-readable, safe (no secrets)
category:       # client | server | auth | conflict | rate_limit | dependency
retryable:      # bool
details: {}     # field errors / context (safe)
request_id:
correlation_id:
```
HTTP mapping: `400 VALIDATION_FAILED`, `401 UNAUTHENTICATED`, `403 FORBIDDEN`, `404 NOT_FOUND`, `409 CONFLICT`
(`IDEMPOTENCY_CONFLICT`), `422 UNPROCESSABLE`, `429 RATE_LIMITED`, `500 INTERNAL`, `503 DEPENDENCY_UNAVAILABLE`.
**Fail-closed:** unknown auth ⇒ 401; unknown tenant scope ⇒ 403; malformed body ⇒ 400 with `details`; never return a
stack trace. Secret redaction applied to `message`/`details`.

## 5. Idempotency

- Unsafe operations (POST create, PUT) **required** `Idempotency-Key`.
- Store: `data/api/idempotency.json` (new registered store, single writer `api/idempotency.py`), keyed by
  `(tenant_id, method, path, idempotency_key)` → `{status, response_hash, resource_id, at}`.
- Replay of a completed key returns the **stored result** with same envelope and `status: ok` (not re-executed).
- Concurrent duplicate while first is in-flight ⇒ `409 IDEMPOTENCY_CONFLICT` (`retryable: true`).
- Scope: idempotency records are bounded/expiring (TTL, default 24h) — scalable.

## 6. Versioning & compatibility

- Version = path `/v1`. `X-Api-Version` header optional, must equal `v1` or ⇒ `400 API_VERSION_UNSUPPORTED`.
- **Additive-only** within `v1`: new optional fields/resources are compatible; removing/renaming a field or changing
  a type is **breaking** and requires `/v2` (escalation trigger per plan §37).
- Deprecation: `Deprecation` + `Sunset` response headers + `warnings[]` entry; process documented in API-5.
- Breaking-change detection is a contract test in API-5.

## 7. Authentication / authorization boundary

- Enforced at the `api/` boundary (middleware/dependency), never trusted from clients.
- **AuthN:** Bearer token. Dev no-op only when `DASHBOARD_API_TOKEN`-equivalent env is unset **and** an explicit
  `API_ALLOW_ANON=1` dev flag is set (fail-closed by default).
- **AuthZ:** role claims (`X-Roles` / token) → `operator` (platform admin) vs `tenant` (scoped). Tenant routes
  require matching `tenant_id`; cross-tenant ⇒ 403.
- Public: `/health`, `/ready`, `/.well-known/*`, `/metrics` (metrics may be token-gated by config).
- Reuses concepts already in the legacy app (`auth`/`operator_guard`/`tenant_guard`) but reimplemented cleanly in
  `api/` (no edits to `dashboard/`).

## 8. Audit & observability

- Every mutating call emits an **audit event** to the canonical event stream (`core/events.py`), carrying
  request_id/correlation_id/actor/tenant/resource_id.
- Request context propagated into run/stage/task/worker events (plan §27 correlation fields).
- OpenTelemetry GenAI spans already exist (`core/otel.py`); API spans link via correlation_id.

## 9. Pagination / filtering / sorting

- Cursor-based: `?limit=` (default 50, max 500) + `?cursor=`; response `links.next`.
- Filters: explicit whitelisted query params per resource (no arbitrary expressions in v1).
- Sorting: `?sort=field` / `?order=asc|desc`, whitelisted.

## 10. Event correlation

- Event envelope fixed in API-5 (plan §18); until then, `core/events.py emit()` remains the writer and API
  correlation fields are added additively (`correlation_id`, `causation_id`, `request_id`).

## 11. OpenAPI ownership

- **Owner:** the new `api/` package generates OpenAPI from its FastAPI app.
- **Canonical artifact (decision):** commit a **generated** `api/openapi.v1.json` + a `--check` guard so drift is
  detected in CI/contract tests (plan §38). The legacy `dashboard/api/app.py` OpenAPI is **not** canonical.
- Compatibility: contract tests assert the committed schema matches the app (API-5).

## 12. Migration sequence (legacy → canonical)

1. API-1 builds `api/` foundation + `/api/v1/health`, `/ready`, `/intake` (strengthened) with the envelopes above.
2. API-2/API-3 add resource routers via canonical services.
3. API-5 adds hardening, contract tests, committed OpenAPI, event API formalization.
4. Consumers (adapters, MCP, CLI) may point at the new base (`API_BASE_URL`); legacy app remains untouched as a
   frozen reference until explicitly retired (deferred, human decision if endpoint parity is broken).

---

## API-0.1 Gate

| Criteria (plan §7) | Result |
|---|---|
| Naming fixed | ✅ plural kebab-case, verbs-as-subresources |
| Security boundary fixed | ✅ Bearer + roles, fail-closed, tenant isolation |
| Compatibility policy fixed | ✅ additive-only in v1; breaking ⇒ v2 (escalation) |
| Idempotency fixed | ✅ required header + store + replay/conflict semantics |
| Error contract fixed | ✅ code/message/category/retryable/details/ids + HTTP map |
| OpenAPI ownership fixed | ✅ `api/` owns; committed generated schema + drift check |
| Migration sequence fixed | ✅ §12 |

**API-0.1 GATE: PASS.** Contract is frozen. Proceed to API-1 (foundation in new `api/`).

**New stores introduced by this contract (register in API-1, single writer each):**
- `data/api/idempotency.json` → owner `api/idempotency.py`
