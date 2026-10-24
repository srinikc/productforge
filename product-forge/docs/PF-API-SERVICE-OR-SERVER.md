# PF Server / Service — API & Service Topology (SSOT)

The authoritative vocabulary and rules for **what PF exposes and how it is called**. Binding with `AGENTS.md`
(EOS) and the ADRs (`docs/ARCHITECTURE-DECISIONS.md`: ADR-0001, ADR-0005, ADR-0006, ADR-0007, ADR-0008),
`docs/API-1-FOUNDATION.md`, `docs/API-0.1-CONTRACT-RECONCILIATION.md`. If this doc and the code disagree,
the code wins and this doc is corrected.

## 1. Vocabulary
- **PF Server / Service** = the umbrella — the set of services that serve PF's APIs **and** everything else
  needed to operate PF.
- **Service** = a bounded unit that owns a **domain/concern**, **exposes an API surface**, and may also
  **operate data/infrastructure** for that domain. Each service owns its data (single writer per concern).
- **Server / service instance** = a **running instance** of a service (a process on a host:port). "API server"
  is a running instance of a service that exposes an API — not a distinct concept.
- **API** = the **contract** (surface + schema + guards + authn/authz + envelope), **not** the transport.

## 2. Service taxonomy (today + expected later)
| Service | Language | Owns | Role |
|---|---|---|---|
| Control-plane service (`api/`) | Python | existing Python concerns: backlog, engineering, … | expose the Python control plane |
| Data-plane service (`go/edpsvc`, EDP) | Go | **the SoR + everything operating it**: schema, tenants/projects, artifacts/objects, RLS, quotas, audit, migrations | **required for PF to operate** |
| Capability service (`go/capsvc`) | Go | cross-cutting Go capabilities (e.g., backlog doc-ingest) | acts by calling other services over HTTP |
| Later/other | — | eventing/alerting (ADR-0005), worker/scheduler/lease, MCP adapter, future dashboard API | each its own service + surface |

All surfaces apply the **same security model** (authn roles, authz/tenant scope, validation, quotas, audit) — ADR-0008.

## 3. Ownership is by **domain**, not by language
There is no single "API layer owner". An **API surface is owned by the service that owns its domain**. The
"API layer" is the **federation** of service surfaces, unified by the shared security contract + version root (`/api/v1`).

## 4. Language rule = **Go-forward, not a port** (ADR-0001 + language rule BI-PF-0387/0388)
- **New** shipped/sensitive logic (`core/`, `api/`, `adapters/`) → **Go** (exposed by a **Go service**, ADR-0008).
- **Edits to existing shipped Python are allowed**; tooling Python (`scripts/`, `docs/`, `config/`, tests) is fine.
- Therefore **existing Python APIs remain** (ADR-0008) — **do NOT port them wholesale**. Python surfaces are
  **stable, not a growth surface**: if a Python endpoint needs *new shipped logic*, that is where the
  language-rule gate fires (→ Go). Exceptions/allowlist live in `config/language-rule.json`.

## 5. How APIs are called — caller classes × transport × auth
| Caller class | Transport | Server needed? | Auth |
|---|---|---|---|
| **External / remote** (adapters, MCP, CLI, dashboard, other services) | **HTTP** (ADR-0008: service-to-service is HTTP-only) | **Yes** (URL+port) | token |
| **Internal, same process** (session tooling, in-process clients) | **In-process API dispatch** (TestClient over `api.app`) | **No** | token or dev anon |
| **Implementation / build gates** (the router itself, precheck gates) | **Library call** (`core.*` single writers) | **No** | none |

`API-first` (ADR-0007) requires the **contract** everywhere; the **transport is an adapter**. Internal callers
use the contract **in-process**; external/other services use it **over HTTP**.

**Interim rule (until the token/server-sharing design lands):** internal callers use **no PF token** — the
in-process API runs in dev anon mode (`API_ALLOW_ANON`, same-process only; business guards — AC-at-create,
closure, revision — still run, since they are not auth). The proper **server + token design** (how the service
is deployed and shared/used by internal and external callers) is a **separate, pending decision** — not yet
implemented. Authn stays **on** for the HTTP/external path; `API_ALLOW_ANON` is for in-process internal use only.

## 6. Topology — one shared instance per service per environment
- **One instance per service per environment** (e.g., one control-plane API, one EDP data-plane service);
  **sessions/agents are clients**, never each their own server.
- Running a server **per session** fragments locks/state and defeats the single-writer/SoR rule — **not the target model**.

## 7. Required-for-operation vs exposure
- **Data-plane service (Go EDP) is required for PF to operate** — it *is* the SoR and the operations on it.
- **Control-plane API (Python `api/`)** is required for **exposing** Python concerns and for
  **service-to-service** calls (e.g., the capability service calling the backlog HTTP API). PF's internal
  Python runtime does **not** need it to run.

## 8. To be designed/implemented later — the PF server MUST cover these
Captured now so the future server/token design **addresses them** (interim state is temporary):
1. **Token/authn design** — issuance, roles/scopes, rotation/expiry, secure storage (secret manager, not a
   repo file), and **how internal vs external callers authenticate**. Replaces the interim `API_ALLOW_ANON`.
2. **Sharing/topology** — **one instance per service per environment**; how the server is hosted and
   **shared by internal and external callers**; local-dev vs deployed; canonical runner (not the `dev_server` wrapper).
3. **Authorization/tenant** — the shared security contract across surfaces: authn roles, authz/tenant scope,
   validation, quotas, audit (ADR-0008).
4. **Transport binding** — external + service-to-service = **HTTP only** (ADR-0008); internal = **in-process**;
   how adapters (MCP, CLI, dashboard, OpenCode) bind (`API_BASE_URL`).
5. **Service-to-service auth** — how Go services (EDP, capability) and the Python control plane authenticate to
   each other; no language bridges.
6. **Reliability/ops** — health, versioning (`/api/v1`), rate/quotas, observability, deploy/rollback — the
   current `:8010` dev wrapper is **not** the target.
7. **Migration off interim** — flip internal callers from `API_ALLOW_ANON` to the real token flow once designed.

## 9. One line
**PF Server/Service = many services; each owns a domain + its API + its data. New logic → Go services; Python
APIs remain. API = contract (mandatory, /api/v1); transport = adapter (external=HTTP, internal=in-process,
implementation=library). One shared instance per service per environment; sessions are clients.**

## 10. EDP data-plane limits (BI-PF-1302 / EDP-10)

`go/edpsvc` enforces the EDP data-plane guardrails:
- **Timeouts:** request 30s (JSON), DB 5s, upload 120s; server read-header 5s / read 180s / write 180s / idle 120s.
- **Caps:** 1 MiB headers and JSON body; 64 MiB `/artifacts` upload.
- **Quotas:** per-tenant 600 rpm / 5 concurrent, global 6000 rpm / 10 concurrent (in-process token buckets + semaphores). The global cap is the hard anti-evasion control because `edpsvc` has one admin principal; per-tenant buckets are attribution. Hard per-tenant authentication/isolation is **BI-PF-1478**.
- **Pool:** one shared bounded pgx pool (10 connections by default); `PF_EDP_GLOBAL_CONCURRENCY` must be <= the pool max or startup fails.
- **Config:** `PF_EDP_*` env flags are registered in `config/env-flags.json`; `PF_PROFILE=dev|production`; `PF_ALLOW_SUPERUSER_DSN=1` is a non-production escape hatch only.
- **Error contract (v1):** `{"error":{"code","message","category","retryable","request_id"}}` plus `X-Request-ID`; 413/429/504 are stable codes.
- **Routes:** `GET /admin/limits` (admin bearer: effective limits + aggregate counters/pool/role), `GET /metrics` (Prometheus counters/histograms; internal), `GET /ready` (DB ping).
- **Production:** `PF_PROFILE=production` refuses `PF_DEV`/`API_ALLOW_ANON`/`PF_ALLOW_ANON`, a missing/weak `PF_ADMIN_TOKEN`, and a superuser/BYPASSRLS runtime DSN. Migrations are a deploy step (`scripts/dev/db_migrate.py`); `/admin/migrations/*` is dev/ops-only. `PF_EDP_ENFORCE_LIMITS=0` is refused in production.
- **Rollback:** production is code revert/redeploy; non-production may set `PF_EDP_ENFORCE_LIMITS=0` (structured errors and the profile guard stay on).
