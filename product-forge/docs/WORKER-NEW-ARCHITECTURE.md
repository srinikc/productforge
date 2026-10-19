# Worker — New Architecture (design note)

> **Status: PARKED — captured as BI-PF-1463 for Gate 1 reconciliation.**
> EDP-17 (BI-PF-1309) is complete. This is a design/review input, not an implementation. No work starts until Gate 1 approves the reconciliation (keep/change/drop), the child-item sequence, and the updated single-writer ownership table.
> Scope: Product Forge (PF) worker workflow end‑to‑end — assignment, execution, coordination, state, delivery.

---

## 0. Purpose

PF's backlog should be **carried out by a worker fleet**, not by a single manual prompt session. To get
there, the worker workflow needs a redesign of its **substrate** (state + coordination), plus a
**control plane** (schedule → assign → coordinate → observe → deliver) over a **data plane** (isolated
execution). This note captures (a) the current architecture, (b) what breaks and why, (c) recommendations,
and (d) the target architecture for autonomous workers.

Guiding constraint from the product: **PF is framework‑agnostic — opencode is just one adapter.** The HTTP
API is also just one adapter. Neither is the core. The core is the state + coordination model.

---

## 1. Current architecture (map)

Model: **PF owns assignment + delivery; WorkerGrid is a thin runtime host** (ADR‑0003,
`docs/ARCHITECTURE-DECISIONS.md`). WorkerGrid keeps "no lease and no store" under `agent.contract=pf-assignments`;
its coordinator store is fallback only.

| Concern | Owner (single writer) | Concurrency primitive |
|---|---|---|
| Backlog items/indexes/history | `core/backlog.py` (`update()`, `_wj` via `os.replace`) | per-scope `.lock` file |
| Job/lease queue rows | `core/job_manager.py` | SQLite `BEGIN IMMEDIATE` (`claim_next`) |
| Shared item lease (cross-clone) | `core/job_manager.py` + `core/id_allocator.py` CAS | git ref CAS `refs/heads/pf-leases` |
| Backlog ids | `core/id_allocator.py` | in-proc `threading.Lock` + git CAS `pf-id-counter` |
| Validation runs | `core/validation_engine.py` | per-repo `.lock` file |
| Delivery landing | `core/delivery.py` | per-repo `.delivery.lock` (O_EXCL, TTL 900s) |
| Durable-state checkpoint | `core/state_checkpoint.py` | **none** (in-proc thread + per-delivery) |
| Coordinator workers/leases | `workergrid/internal/store/store.go` | SQL `ON CONFLICT … WHERE expired RETURNING` + `s.mu` |
| Local WG workers/leases JSON | `workergrid/wg.py` / `_cfg.py` | **none** (`os.replace` only) |

Key flows:
- **Claim:** `job_manager.claim_next` → `scheduler.next_eligible` → shared CAS acquire → SQLite `BEGIN IMMEDIATE`
  re-check → write `item.execution{}` lease; assignment worktree `assign-<item>`, branch `feature/wg/<slug>`.
- **Execute:** worker/agent runs in the worktree; heartbeat renews; complete/fail posts back.
- **Deliver:** `core/delivery.py` → `validation_engine.feature_pr` in a fresh `validation/*` worktree →
  serialized landing (`engineering/.delivery.lock`) → `set_delivery` + `set_status(completed)` → checkpoint.
- **State sync:** `state_checkpoint.py` commits durable files off a temp worktree → PR; git merge drivers
  (`union`, `pf-item`, `pf-derived`) reconcile.
- **Freshness:** `core/runtime_freshness.py` gates `deliver` only (`loaded_sha != current_sha` → block).
- **Auth:** `api/auth.py` token (`PF_API_TOKEN` > `API_TOKEN` > dev file when `PF_DEV=1`); worker sends
  `X-Roles: worker,operator`.

---

## 2. What breaks (observed + code-verified)

1. **Backlog SSOT is JSON files inside the git working tree, mutated by a live server and by sessions.**
   → dirty canonical tree, stale local `develop` used as validation base, `state_checkpoint` races,
   constant merge conflicts. A database modeled as files.
2. **Two claim authorities coexist** (PF `job_manager.claim_next` vs WG `store.Claim`); the active guard
   depends on the contract the agent picks. They can disagree; coordinator has no capacity cap.
3. **Lease lifecycle is not closed:** the shared CAS lease is **never renewed** (`renew_lease` writes local
   only); `fail()` / `recover_expired()` **don't release** it; same-`worker_id` re-acquire allowed →
   cross-clone double-claim / "denied while locally freed".
4. **Check-then-act across two lock domains** (SQLite mutex guards a value written under the backlog file lock).
5. **Ephemeral authority:** freshness gates only `deliver` (a stale server still hands out leases); `loaded_sha`
   captured at first import, not process start; multiple servers coexist with different tokens; `ensure_dev_token()`
   regenerates the file → intermittent 401s.
6. **Delivery lane is brittle + self-starving:** slot accounting **counts `validation/*` worktrees** (a leaked
   worktree permanently eats a slot; `max_parallel_validations=2` → "no validation slot"); worktree removal not
   in a `finally`; "delivery lane busy" is a hard non-retry; verification runs the **whole suite per delivery**
   and is **binary** (one red test blocks every delivery); a running server **contends** with the suite.
7. **Worktree leaks:** coordinator agent uses timestamped `wg/<slug>-<stamp>` names (never cleaned); recovery can
   force-delete a live worker's worktree.
8. **Backlog writes bypass the API** (partially fixed for code by BI-PF-1327's guard); the live server still holds
   a working tree, so API writes are uncommitted → checkpoint dance.
9. **Adapter coupling (minor):** the worker protocol/gates live in one runtime's command doc, not an
   adapter-neutral PF surface.

---

## 3. Root causes

- **R1 — File-based SSOT + live writer + git-mediated sync** → stale/dirty/conflicts/checkpoint races. *(~80% of the pain)*
- **R2 — Duplicate coordination authorities** (PF lease vs WG coordinator store).
- **R3 — Lease/slot lifecycle is not a closed state machine** (no renew/release/GC symmetry).
- **R4 — Ephemeral runtime authority** (tokens, freshness, multi-server, worktree leaks).

---

## 4. Do we need the PF API server? (No — for local coordination)

The API server currently does three unrelated jobs; only one needs HTTP:

1. **Product surface** (remote/tenant workers, generated-product producers) — needs HTTP. **Keep.**
2. **Local coordination** (claim/lease/backlog writes between same-machine sessions) — **does not need HTTP**; needs a
   shared *transactional store*.
3. **Stateful daemon** (caches token, code snapshot/freshness, in-memory store view) — the daemon shape is what forces
   "single authority + token + restart-on-change + tests-contend".

Because (2) was routed through (1)'s daemon, we get: each session wants a server → multiple authorities → token
regeneration/401s → "enforce a single dev server". That is HTTP-daemon lifecycle, not coordination.

**Fix — split coordination from transport:**

- **Coordination core = datastore + library** (backlog, claim/lease, checkpoint, delivery as library calls over an
  authoritative store — SQLite/Postgres; `go/datastore` + `migrations/` already exist). The store is the single writer;
  concurrency is a transaction, not a token.
- **HTTP API = one optional adapter** over the core (remote workers, tenants, WorkerGrid on another host).
- **Local sessions call the core directly** (CLI/library) — like `python -m core.delivery <item>` already does. A CLI
  loads current code every invocation → the "stale server → restart → freshness gate" problem disappears.

Removes for local work: the token, the "single dev server" rule, server/test contention, and (with a DB SSOT) the
stale/dirty/merge-conflict/checkpoint-PR dance. Note: "enforce a single dev-server authority" treats the symptom; once
coordination doesn't need a daemon, the rule and the token issues vanish.

---

## 5. Recommendations (prioritized)

### P0 — Kill R1: make state a datastore, not git files
- Make backlog/leases/assignments authoritative in a **DB** (reuse `go/datastore` + `migrations/`, and the coordinator's
  SQLite/PG). JSON becomes **export/mirror**, never the live writer's target. Git holds **code only**.
- If the migration is too big now: at minimum **separate the state repo from the code working tree** — the running
  server's state must not live in the tree sessions build in.

### P0 — Kill R2: one claim authority
- Delete/deprecate the coordinator claim path (or make it a pure client of PF `/claim`). `job_manager.claim_next` is the
  **only** lease authority; enforce a single capacity source.

### P1 — Close R3 (lease/slot state machine)
- **Renew the shared CAS lease on heartbeat**; **release it on `fail()` and `recover_expired()`**.
- Replace "count `validation/*` worktrees" with a **slot registry with leases + TTL** (no leak can starve).
- Add **periodic stale-worktree GC** (validation, assignment, coordinator) + **`finally` cleanup** everywhere; make
  worktree names **deterministic**.
- Make "delivery lane busy" **queue/retry**, not hard-fail.

### P1 — De-risk the delivery track
- **Verification scope:** run **affected tests + a fixed smoke**, not the whole suite per delivery; or add a
  **known-failure baseline** so a pre-existing red test doesn't block all items.
- **Isolate the suite from the live server** (separate port/state) — contention produces false negatives.

### P1 — Make authority fresh and singular (R4)
- **Gate `claim` on freshness too**; capture `loaded_sha` **at process start**.
- **Enforce a single dev server authority** only if the daemon remains — but prefer removing the daemon need (§4).
- **Stable token handling** (don't regenerate on a transient file miss; atomic rotation + grace window); **scope roles to
  the token** (`X-Roles` is currently self-asserted — any token holder can claim `operator`).

### P2 — Adapter neutrality + ergonomics
- Move the worker **protocol/gates** out of one runtime's command doc into an **adapter-neutral PF/WG contract**;
  formalize the **runtime-adapter interface** (`agent.runtimes.<name>.command` is a good seed).
- Add a **lightweight lane** for tooling/docs (fast gate + minimal checks, skip the heavy suite).

---

## 6. Worker control plane (target capabilities)

### 6.1 Auto-assignment via the scheduler — yes (mostly exists)
Separate the three concerns, keep each pure/idempotent:
- **Scheduler = pure eligibility** (`scheduler.next_eligible`, deps/waves/priority) — no side effects.
- **Dispatcher = assignment** (idempotent; retries; fairness/aging; epic & target-release ordering; backpressure).
- **Worker = execution** (isolated worktree/sandbox; heartbeats; complete/fail).

The real constraint is **safe parallelism**, not scheduling: leases + **fencing tokens**, isolated sandboxes, delivery
slots. **Do not scale the fleet before the spine (R1/R3) is closed** — otherwise you amplify duplicate/stale work.

### 6.2 Role-specific workers — as **capability contracts**, not personas
- Items declare `required_capabilities[]` (`go-core`, `api`, `migration`, `security-review`, `docs`, `packaging`, …) and
  a **change class** (tooling / core / sensitive).
- Workers register capabilities + a **versioned charter** (their instructions/policy). Routing matches requirements ↔
  capabilities.
- Instructions are **declarative + versioned** (config), injected at claim and recorded on the item — auditable, not
  smuggled into prompts.
- Powers **autonomy tiers by change class** (docs → auto; `core/` → gate; `licensing`/security → two-person).

### 6.3 Worker-to-worker communication — typed + brokered only
**Do not build free-form chat between workers** (unmanaged state channel: no schema/authorization/audit/replay). Build a
**brokered, typed event bus** on the existing eventing workstream (BI-PF-1266–1276):

- Message types (schema-validated): `handoff`, `dependency.wait/ready`, `claim/lease.granted/revoked`,
  `review.request/verdict`, `artifact.published`, `cancel`, `escalate.to_human`.
- Broker enforces: type allowlist, schema validation, authorization (who may send what to whom), rate limits, audit log,
  ttl/size caps.
- Workers **react to events**; they don't negotiate prose. Yields determinism, replay, observability.

### 6.4 Worker dashboard — an **ops console**, not a chat app
- **Ops console (high value, do first):** assignments, leases, queue, capacity, stuck/expired, throughput, failure rates,
  per-item timeline, who's working what, drift/conflicts. This is how you debug the flakiness.
- **Coordination UI (later):** the human **gateway** onto the *same typed bus* — approvals, escalations, unblock,
  reassign. Not a separate channel.
- Guardrails: RBAC (read vs act), allowlisted message types, per-tenant scoping, every action → an event, no secrets in
  messages.

### 6.5 Target shape

```
                 ┌─────────────── Control plane ───────────────┐
 Backlog(DB SSOT)→ Scheduler(eligibility) → Dispatcher(assign) → Policy(match + autonomy)
                        │                        │
                        ▼                        ▼
                   Event bus (typed, brokered, audited) ──► Ops console (read + human actions)
                        ▲
                 ┌──────┴──────── Data plane ─────────┐
                 Worker/adapter (isolated worktree) → gates → Delivery lane
```

---

## 7. Enterprise invariants (bake these in)

- **Single source of truth** (DB, not git files) — removes stale/dirty/merge conflicts.
- **At-least-once + idempotent** handlers; **leases with fencing tokens** so a stale worker can't write after its lease
  moves.
- **Backpressure & capacity** per repo/tenant; queue instead of hard-fail.
- **Audit + replay:** every assignment, lease, message, gate, and delivery is an event; the console is a projection.
- **Security:** token-scoped roles (no self-asserted `X-Roles`), tenant isolation, no secret-bearing messages.
- **Autonomy dial + kill switch + blast-radius caps** (max items in flight, max files touched, sensitive-path gate).

---

## 8. Autonomy tiers (esp. important because the only product is PF itself)

The backlog is **framework-internal, high-blast-radius** work → conservative autonomy:
- **Auto:** tooling/docs/tests/CI.
- **Gated (operator approval):** `core/`, `api/`, `adapters/`.
- **Two-person / senior:** `core/licensing.py`, `core/billing.py`, security-sensitive paths.

The 14–17 guidelines are the right guardrail **content** — they should live in the **policy engine**
(adapter-neutral), not in a single runtime's command doc.

---

## 9. Phasing

1. **Spine (must precede everything):** DB SSOT + one claim authority + lease renew/release symmetry + slot registry +
   worktree GC. *(R1–R3, §5 P0/P1)*
2. **Routing:** capabilities on items/workers + dispatcher + autonomy tiers + versioned charters.
3. **Coordination bus:** typed events on the existing eventing backbone + policy enforcement.
4. **Console:** ops observability first; then human gateway onto the same bus.
5. **Scale & harden:** fencing tokens, multi-tenant isolation, SLOs, capacity, idempotency/chaos tests.

---

## 10. Direct answers

- **Auto-assign:** yes, high value, mostly built — but gate behind the spine, else duplicate/stale work scales too.
- **Role/instruction workers:** yes — as **capability routing + versioned charters + autonomy tiers**, not personas.
- **Worker-to-worker comms:** valuable **only** as a typed, brokered, audited bus. Free chat = anti-pattern.
- **Dashboard:** high value as an **ops console**; coordination must reuse the same typed bus.

---

## 11. Open decisions (to resolve before starting)

- [ ] DB SSOT: SQLite per repo, or Postgres (multi-machine)? Migration path for the JSON store + merge drivers?
- [ ] Retire the coordinator claim path, or keep as a degraded fallback?
- [ ] Keep any long-running server for local dev, or CLI/library only (API for remote/tenant only)?
- [ ] Event bus: extend the existing eventing workstream (BI-PF-1266–1276) — confirm the schema/owner.
- [ ] Autonomy tiers: exact class → tier mapping and who may override.
- [ ] Verification: affected-tests scope + known-failure baseline policy.
```