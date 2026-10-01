# Provider Health Tracking — Design (BI-PF-0279)

## Goal
Routing/strategy currently cannot consider provider **availability, rate-limits, errors, or latency**
(only a retired flag exists). Add a **provider-health store (single writer)** updated from real call
outcomes, surfaced to the router/strategy gate and the dashboard — resilience-aware, scalable, API-first.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Call outcomes | `core/orchestrator/llm_client._call_llm_single` knows status (200/429/5xx), latency, retries | feed a health store | reuse + hook |
| Candidate ordering | `core/provider_kinds.order_candidates` (kind-aware, no health) | health-aware tie-break/deprioritize | extend |
| Strategy gate | `core/model_strategy.assess` (no health) | surface degraded providers + warnings | extend |
| Routing | `core/intent_router`/`knowledge_router` (not providers) | unchanged | — |
| Budgeted breakers | `core/budget.py` breakers (budget, not provider) | keep separate (different concern) | — |

**Blast radius:** new `core/provider_health.py` (single writer `data/provider-health.json`), a thin hook in
`llm_client` outcome handling, health-aware ordering in `provider_kinds.order_candidates`, a warning line in
`model_strategy.assess`, API + store-registry entry.

## Design decisions (modular, 1 truth per concern)
- **New `core/provider_health.py`** — the **only writer** of `data/provider-health.json`:
  - `record(provider, *, ok, status=0, latency_ms=0, error="", kind="")`: update a rolling window per
    provider — `success`, `fail`, `rate_limited` (429), `errors_by_status`, EWMA `latency_ms`,
    `last_error`, `last_seen`, and a derived `state` ∈ `healthy|degraded|unavailable`.
  - `state(provider)` / `snapshot()` / `score(provider)`: a bounded 0..1 health score (recency-weighted);
    **fail-open when unknown** (a provider with no data scores neutral, never punished).
  - `cooldown(provider)`: after repeated 429/5xx, a short cooldown window so routing deprioritizes it.
  - **Circular-safe:** bounded per-provider counters (no unbounded lists); atomic write; never raises.
- **Hook (thin, in the existing call path):** `llm_client._call_llm_single` records one outcome per
  attempt — success (200 + latency), rate-limit (429), or error (status/exception). Best-effort; a health
  write failure never affects the call. This is the **only** integration into the hot path.
- **Router consumes health:** `provider_kinds.order_candidates` applies a **stable** health-aware
  ordering: unavailable/cooling-down providers sink, healthy ones rise, **relative order otherwise
  preserved** (`prefer_kind`/`reject_unknown` semantics untouched). Unknown ⇒ neutral (no behavior change
  when there is no health data → **zero regression**).
- **Strategy gate surfaces it:** `model_strategy.assess` adds `provider_health` (per-assignment state) +
  `warnings` for degraded/unavailable providers. Advisory; never blocks.
- **Reuse, never fork:** budget breakers remain budget-only; this is provider-only. One store, one writer.
- **API-first:** `GET /api/v1/provider-health` (snapshot), `GET /api/v1/provider-health/{provider}`
  (state+score), `POST /api/v1/provider-health/record` (operator/admin override; guarded).
- **Scalable:** rolling counters + EWMA (O(1) update, fixed memory); atomic JSON write; no network.

## Plan (branch `feature/bi-pf-0279-provider-health`)
1. `docs/PROVIDER-HEALTH-DESIGN.md` (this file).
2. `core/provider_health.py` — `record`, `state`, `score`, `snapshot`, `cooldown`, `reset`.
3. Register `data/provider-health.json` in `config/store-registry.json`.
4. Hook `llm_client._call_llm_single` outcomes (success/429/error + latency).
5. `core/provider_kinds.order_candidates` — health-aware stable ordering (neutral default).
6. `core/model_strategy.assess` — expose `provider_health` + degraded warnings.
7. `dashboard/api/app.py` — `/api/v1/provider-health*`.
8. Tests `test_provider_health.py` — record→state transitions (healthy/degraded/unavailable); 429 cooldown;
   EWMA latency; **unknown ⇒ neutral ordering (no regression)**; degraded provider sinks in
   `order_candidates`; strategy report includes health; snapshot/API shape.
9. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
10. Merge; close `BI-PF-0279` through the loop.

## Acceptance
- A provider's availability/rate-limits/errors/latency are recorded from real call outcomes and exposed as a
  derived state + score.
- `order_candidates` deprioritizes degraded/unavailable/cooling providers **without** changing ordering when
  no health data exists (zero regression).
- Strategy gate surfaces provider health; API + dashboard can read it.
- Single writer; `precheck` PASS; fail-open on unknown; bounded memory.

## Out of scope (tracked separately)
Per-model (not just provider) health, live provider probes, multi-region health, alerting/SLO (0218).
