# Eventing & Alerting SSOT — Design (BI-PF-1266)

**Status:** Design — **approval required before implementation**
**Epic:** BI-PF-1265 (Eventing & Alerting SSOT)
**Implements:** ADR-0005 and ADR-0011 (`docs/ARCHITECTURE-DECISIONS.md`)
**Related:** BI-PF-0387/0388 (Go-first), BI-PF-0390/0393/0394 (A1 contracts + B1 Go core),
BI-PF-1267 … BI-PF-1276 (children), BI-PF-1277 dogfood epic (first non-UI consumer)
**Owner:** architecture

---

## 1. Problem (why)
Eventing + alerting is fragmented and has no SSOT:
- `core/events.py` — canonical run-lifecycle stream (`events.jsonl`), **emit-only**; no subscribers, no
  reliable cursor (`since` compares timestamps).
- `core/event_bus.py` — a **second** stream (`.orchestration/events.jsonl`) + in-process `on()/emit()`
  handlers; not cross-process.
- Bespoke subscribers: `core/agent_messenger.py` (agent topics), a legacy WebSocket transport, the
  `core/notification_system.py` store, `core/alerts.py` (email).
- No subscription registry, no pluggable transports, no alert-rule policy, no at-least-once contract.

Consequences: a 5–30 min run has **no reliable completion signal**; every consumer re-invents delivery;
external/UI consumers cannot subscribe; alerting is inline policy with no throttle/escalation.

## 2. Goal / value
**One** reusable event+alert capability. Producers emit once into the SSOT; consumers subscribe through
stable contracts (in-process callbacks, SSE, webhook, notify/email) — **cross-process**. Anyone needing
eventing/alerting calls the same API. Python is a **thin client** over the A1 wire seam; the new shipped
logic is Go (ADR-0001). Existing wired consumers keep working throughout migration (shims).

## 3. Architecture (target)

**Storage authority:** ADR-0011. PostgreSQL is the event store; object storage holds large payloads; a bus is
an optional transport, never the source of truth.

```
                 producers (Go + Python thin client)
                          |  emit(canonical envelope)
                          v
        +-------------------------------------------+
        |  Go event core (single writer)             |
        |  - PostgreSQL events + transactional outbox|
        |  - per-tenant monotonic seq + cursor       |
        |  - large payload -> ObjectStore + ref/hash |
        +-------------------------------------------+
                          |
                    Go dispatcher (outbox cursor, at-least-once, event_id dedupe, retry -> DLQ)
                          |
        +-----------------+-------------------+------------------+
        v                 v                   v                  v
   inproc callbacks     SSE (API edge)     webhook (HMAC)     notify / email
   (compat shim)        GET /events/stream  (idempotency)      (reuse existing owners)
                          ^
                 subscriber registry + alert policy (PostgreSQL, single writer)
                          ^
                 API (thin Python edge): subscription CRUD + cursor reads

   Optional transport (later): Kafka/NATS/PubSub consumes the outbox; it is not authority.
   Compatibility: generated read-only events.jsonl projection/export only; never read as truth.
   Python seam: core/events.py (thin client) <-> core/contracts.py (A1 wire) <-> core/go_host -> go/
```

**Language boundary (ADR-0001 / `language_rule_check`):**
- **Go** (new shipped logic, under `go/`): event core, PostgreSQL writes/cursor, object payload handling,
  subscriber registry, dispatcher, transports, alert policy.
- **Python (edits to existing files only)**: `core/events.py` (thin client), API routes, and the seam call.
  **No new `.py`** under `core/`, `api/`, `adapters/`.
- **Python tooling/tests/docs**: design docs, gates (`scripts/dev`), contract tests
  (`test-framework/tests`).

## 4. Contracts (extended additively; A1 parity with Go)

- **Event envelope v2** (owner: `core/events.py`): add monotonic `seq` and durable storage fields
  (`payload_ref`, `payload_sha256`, `size_bytes`, `content_type`) while keeping `event_id`, `event_type`,
  `event_version`, `occurred_at`, `correlation_id`, `causation_id`, `task_id`, `worker_id`, `actor`,
  `payload`, and the legacy flat fields `ts/type/level/stage/agent/trace_id/span_id`.
- **PostgreSQL event row:** `(tenant_id, seq)` is the cursor key; `event_id` is globally unique; append-only
  privileges; RLS by tenant; indexes for `(tenant_id, seq)` and `(tenant_id, event_type, seq)`.
- **Payload threshold:** inline JSON below the configured limit; larger payloads go to the `ObjectStore`
  interface (ADR-0006). The DB stores only opaque reference + sha256 + size/content type.
- **transactional outbox:** event insert and outbox row commit in one transaction. Dispatcher reads the
  outbox; at-least-once; `event_id` dedupe; retry to DLQ.
- **subscription**: `{id, tenant_id, types[], filter, transport(inproc|sse|webhook|notify|email), target,
  auth_ref, enabled, created_by}`; PostgreSQL single writer.
- **alert-rule**: `{tenant_id, type/severity -> channels[], throttle_window, escalate}`; PostgreSQL single
  writer.
- **webhook delivery**: payload = envelope; headers carry `X-PF-Signature` (HMAC over body) and
  `X-PF-Idempotency-Key` (= `event_id`).
- Python remains the schema source of truth (`core/contracts.py`); `go/` mirrors it; parity asserted by a
  test (pattern: `test-framework/tests/pipeline/test_contracts.py`).
- **Compatibility projection:** `events.jsonl` may be generated read-only from PostgreSQL for legacy readers;
  it is never authoritative and is never dual-written as a source of truth.

## 5. Consumer migration matrix (with shims; no parallel copy)

| Consumer | Current | Target | Compat during migration |
|---|---|---|---|
| `core/event_bus.py` | own stream + in-proc `on/emit` | producer facade over `events.py`; `on()` → registry | keep `on/emit/recent/KINDS`; keep BI-PF-0233 mirror |
| `core/orchestration_context.py` | `event_bus` policy routing | alert-policy consumer | keep `_POLICY` behavior |
| `core/ops_phase.py`, `core/pipeline_capabilities.py`, `scripts/dev/parked_review.py` | `event_bus.on/emit` | subscriber API (inproc) | `on()` shim |
| `core/notification_system.py` | own store | `notify` transport adapter | method signatures unchanged |
| `core/alerts.py` | direct email | `email` transport adapter | `email(...)` unchanged |
| legacy WebSocket transport (`core/websocket_manager.py`) | in-proc WS fan-out | **retire when superseded** (never extend) | left frozen; SSE supersedes |
| `api/routers/events.py`, `evidence.py`, `runs.py`, `health.py` | read `events`/`run_status` | shared read/subscription API | responses identical |
| `core/log_router.py` | low-level writer | **stays** writer/path owner | — |

## 6. RECONCILIATION (binding)

**PRIOR DECISIONS**
- ADR-0001 / `PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md` §4.8 — "Go-first for new work"; new
  shipped/sensitive → Go; existing Python compiled; **no duplication** (a feature is Go xor Python).
- `ENG-9-DOGFOOD.md:30` — pipeline triggered through the ONE canonical path (`run_entry`).
- `core/events.py:1-11` — this module is the single writer of the canonical stream.
- BI-PF-0233 — project-scoped bus events mirror into the per-project canonical stream.
- `docs/API-5-HARDENING-EVENT-LAYER.md` — formalized event envelope (API-5).
- ADR-0004 — Feature ↔ Epic ↔ children backlog model (this work is EPIC BI-PF-1265).

**EXISTING PATH** (capability → exists? owner:file)
- Canonical emit + taxonomy → yes → `core/events.py`.
- Orchestration signal bus + in-proc handlers → yes → `core/event_bus.py`.
- Payload secret redaction → yes → `core/log_router.redact()`.
- DLQ (retry sink) → yes → `core/dead_letter_queue.py`.
- Notifications store → yes → `core/notification_system.py`; email → `core/alerts.py`.
- Go core invocation seam → yes → `core/go_host.invoke` + `core/contracts.py` (A1).
- Subscriber registry / dispatcher / transports / alert policy / SSE → **no** (to be built in Go + API edge edits).

**ASSUMPTIONS** (each needs explicit yes/no before implementation)
- A1. The Go core is the acceptable host for the new bus (persistent process vs on-demand invocation).
- A2. `core/events.py` may become a thin client while keeping its exact public API.
- A3. The Go event core is the single PostgreSQL writer at cutover; `events.jsonl` is a read-only projection only.
- A4. SSE is served at the API edge (thin Python read of the stream), not a Go HTTP server.
- A5. The subscriber registry + alert rules live in their own stores (single writer) registered in
  `config/store-registry.json`.
- A6. Existing consumers accept in-process shims (`on()` etc.) with identical behavior.

**DIVERGENCES**
- A **blocking/Go-daemon** model diverges from the historical "emit-and-read" async design
  (`DOGFOOD-E2E-DESIGN.md:65`): the bus adds an always-on dispatcher. → Amend via ADR-0005 (recorded).
- The legacy WebSocket transport is **not extended** (it is superseded by SSE); no new references added.

**OPEN QUESTIONS** (resolved by this design unless the approver says otherwise)
- Q1 Go packaging: extend `go/pfcore` vs new `go/eventbus` → **extend `go/pfcore` first** (smallest seam;
  split later if needed).
- Q2 Run model: **standalone Go bus daemon** for dispatch + external delivery; library invocation for
  emit/read.
- Q3 SSE edge: **API edge** (A4).
- Q4 Writer ownership: **Go event core is the writer from the first production cutover**; `events.jsonl` is a read-only projection only (ADR-0011).
- Q5 Python-emit handoff: **Python calls the Go core (seam)**; no dual writer, no file authority.

## 7. IMPACT REVIEW (mandated)

| Claim | Verdict | Evidence | Recommendation |
|---|---|---|---|
| New bus core in Go | aligned | ADR-0001; `go/pfcore/pfcore.go:1-6`; `core/go_host.py` | build under `go/`, invoke via A1 |
| No new Python in shipped roots | aligned | `config/language-rule.json` (`shipped_roots`) | Python edits existing files only |
| One event store (no second) | aligned | ADR-0011; `core/events.py:1-11`; `event_bus.py:48-62` mirror | PostgreSQL authority; JSONL projection only; no new stream |
| Single writer per store | aligned | `config/store-registry.json` rules | register registry/alert stores w/ one writer |
| Contract extension compatible | aligned | `core/events.py:43-74` envelope; `test_api_events.py` | additive `seq`; keep legacy fields |
| Consumers keep working | aligned | 50 `events` importers; `test_event_ssot.py` | migrate behind shims; no signature change |
| Reuse redaction + DLQ | aligned | `core/log_router.py:58`; `core/dead_letter_queue.py:42` | reuse both (no new impl) |
| Cross-process delivery | new-path | pipeline child process vs API | Go daemon or stream tail (Q2/Q4) — **approved?** |
| Event authority in PostgreSQL | aligned | ADR-0006, ADR-0011 | Go writer; no JSONL authority |
| Large payloads in object store | aligned | ADR-0006 ObjectStore contract | DB stores ref/hash/size only |
| Bus as optional transport | aligned | ADR-0011 | outbox first; broker never authority |
| Go API server rewrite | **violates** | ADR-0001 (existing Python stays) | **do NOT**; Python edge + Go behind seam |

## 8. Risks & mitigations
| Risk | Severity | Mitigation |
|---|---|---|
| Two writers during strangler | High | single-writer discipline; staged ownership cutover (A3) |
| Go toolchain absent in some envs | Medium | `core/go_host` builds on demand, fail-closed; feature flag falls back to current writer |
| SSE long-lived stream over subprocess seam | Medium | SSE at API edge reading the stream (A4) |
| Unreliable webhook delivery | Medium | at-least-once + `event_id` dedupe + retry → DLQ |
| Regression of 50 event consumers | High | frozen public API + contract test + full gate set |
| Backlog bloat / duplication | Low | dedup-first done (best match 0.51 vs completed B1) |

## 9. Delivery plan (phases → backlog; each on its own feature branch, gated)
1. BI-PF-1266 **this design** (ADR-0005 + this doc) — **approval gate here**.
2. BI-PF-1267 contracts (+ Go parity).
3. BI-PF-1268 Go event core (PostgreSQL store/outbox/emit/seq/cursor; object payloads).
4. BI-PF-1269 subscriber registry + dispatcher (retry→DLQ).
5. BI-PF-1270 transports (inproc/webhook/notify-email).
6. BI-PF-1271 alert policy (rules/throttle/escalation).
7. BI-PF-1272 Python thin-client cutover of `core/events.py`; JSONL becomes a read-only projection.
8. BI-PF-1273 migrate existing consumers (shims).
9. BI-PF-1274 API surface (SSE + subscription CRUD).
10. BI-PF-1275 bus daemon run model + ops.
11. BI-PF-1276 retire legacy WebSocket transport.

## 10. No-regression Definition of Done
- Frozen public APIs (`core/events.py`, `core/event_bus.py`, `core/run_status.py`, `core/log_router.py`)
  unchanged; new capability additive.
- Gates green: `compileall`, `wired_audit`, `single_path_check`, `language_rule_check`, `precheck`.
- Event/SSOT tests green: `test_event_ssot.py`, `test_api_events.py`, `test_redaction.py`,
  `test_tracing.py`, `test_log_router_retention.py`, `test_run_status_reconcile.py`, `test_section_d.py`.
- No new `.py` under `core/`, `api/`, `adapters/`; PostgreSQL is the only event authority; legacy
  transport only retired.
- Large payloads use object storage with sha256 verification; `events.jsonl` is not read as authority.
- Evidence linked on BI-PF-1266 (design) and each implementing item.

## 11. Plain-language summary
Today, "what happened in a run" and "tell someone / something about it" are spread across five different
mechanisms with no reliable completion signal. This design gives Product Forge **one event+alert spine**:
anything that happens emits **one** event; anything that cares **subscribes** — inside the process, to a
live stream, to a webhook, or to email — and it works even across processes and for long (5–30 min) runs.
It is built in Go (per the delivery rule) and the existing Python code keeps working unchanged.
