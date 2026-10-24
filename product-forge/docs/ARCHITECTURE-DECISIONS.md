# Architecture Decision Register (ADR)

**Item:** BI-PF-0392 (Epic A / A0) · Owner: architecture · Format: MADR-style.
The register is the governance anchor for Epic A. ADRs are **immutable once accepted**; supersede with a new
ADR. Individual ADRs may later be split into `docs/adr/NNNN-*.md` (the index here stays the source of truth).

## How to add an ADR
1. Copy the template below into a new section.
2. Fill Context · Drivers · Options · Decision Outcome · Consequences · Confirmation.
3. Add a row to the index. Status: Proposed → Accepted → (Deprecated | Superseded by ADR-NNNN).

## Index
| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](#adr-0001-go-first-compiled-delivery) | Go-first compiled delivery (one source, many editions) | Accepted | 2026-10-06 |
| [ADR-0002](#adr-0002-workergrid-external-execution-plane) | WorkerGrid: external, producer-agnostic execution plane | Superseded by ADR-0003 | 2026-10-06 |
| [ADR-0003](#adr-0003-assignment-authority-in-the-producer-workergrid-is-a-runtime-host) | Assignment authority in the producer; WorkerGrid is a runtime host | Accepted | 2026-10-07 |
| [ADR-0004](#adr-0004-feature--epic--children-backlog-model) | Feature ↔ Epic ↔ children (backlog model) | Accepted | 2026-10-08 |
| [ADR-0005](#adr-0005-eventing--alerting-ssot-go-first-bus-python-thin-client) | Eventing & Alerting SSOT: Go-first event bus; Python thin client | Accepted | 2026-10-12 |
| [ADR-0006](#adr-0006-enterprise-data-plane-postgresql-system-of-record-object-store-tenant-isolation-residency) | Enterprise Data Plane (PostgreSQL system of record, object store, tenant isolation, residency) | Accepted | 2026-10-13 |
| [ADR-0007](#adr-0007-api-first---every-capability-is-a-secured-api-surface) | API-first - every capability is a secured API surface | Accepted | 2026-10-24 |
| [ADR-0008](#adr-0008-service-topology---go-backed-capabilities-are-exposed-by-go-services) | Service topology - Go-backed capabilities are exposed by Go services | Accepted | 2026-10-24 |
| [ADR-0009](#adr-0009-formal-retention-of-global-config-stores-design-systems) | Formal retention of global config stores (design-systems) | Accepted | 2026-10-24 |

## Template
```markdown
# ADR-NNNN: <title>
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXXX
**Date:** YYYY-MM-DD   **Deciders:** <roles>   **Related:** <backlog item(s)>
## Context and Problem Statement
## Decision Drivers
## Considered Options
## Decision Outcome
**Chosen option:** "…" because …
### Consequences
**Positive:** …  **Negative:** …  **Risks:** …
### Confirmation
```

---

# ADR-0001: Go-first compiled delivery (one source, many editions)

**Status:** Accepted
**Date:** 2026-10-06
**Deciders:** Product/Architecture
**Related:** BI-PF-0387 (delivery baseline), BI-PF-0388, Epic A (BI-PF-0390), plan `docs/PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md`

## Context and Problem Statement
PF's platform is 100% Python (`core/packaging.py` ships `source_dir`; 632 tracked `.py`). Deploying it to a
customer/enterprise/OEM environment exposes readable source → IP/reverse-engineering risk and loss of recurring
value. We need one codebase that ships safely across SaaS/Community/Professional/Enterprise/OEM without forks.

## Decision Drivers
- IP protection on customer-deployed editions.
- One source, many editions (no per-edition codebases).
- Keep development velocity (Python for internal/AI/build-time).
- Deterministic, reproducible, signed, air-gap-friendly delivery.

## Considered Options
1. Keep all Python; ship source (status quo) — no protection.
2. Full Python→Go rewrite — huge, AI ecosystem gap, big-bang risk.
3. **Go-first for new + existing compiled + migrate by value** (strangler).
4. SaaS-only (never ship) — not viable for on-prem/OEM demand.

## Decision Outcome
**Chosen option:** Option 3.
- **One source, one implementation per feature.** New **shipped/sensitive** features → **Go**; new
  build-time/AI/experimental → Python. **Existing Python → compiled** (Nuitka). High-value legacy → migrated to
  Go **by value** later.
- **Build compiles, never translates** (`go build` / Nuitka). **No raw `.py` in any customer package.**
- **SaaS runs the source; customer ships the compiled artifact + license.**
- A full rewrite is a **non-goal/aspiration**; compiled Python is the fallback for the low-value remainder.

### Consequences
**Positive:** strong protection where it matters; no forks; velocity retained for internal/AI; edition-flexible.
**Negative:** polyglot baseline (Python + Go) + Go↔Python contract; compiled-Python is partial protection;
Go ramp cost. *We accept these; mitigated by contract-first + value-driven migration.*
**Risks:** build complexity for compiled artifacts → mitigated by a CI build matrix + no-raw-source release gate.

### Confirmation
- A shipped package contains **no readable `.py`** (release gate).
- New shipped features land in Go; `work_pull`/`scheduler` unaffected.
- ADR-0001 is referenced by Epic A items and `BI-PF-0387`.

---

# ADR-0002: WorkerGrid — external, producer-agnostic execution plane

**Status:** Superseded by ADR-0003
**Date:** 2026-10-06
**Related:** `docs/WORKERGRID-DESIGN.md`, `docs/WORKER-SCHEDULER-OPERATIONS.md`, Epic A/B

## Context and Problem Statement
The worker/scheduler lives inside PF and is entangled with it (backlog, local files/SQLite). It cannot run
**multi-machine** (stale git, no push, no shared state) and offers **no parallelism**. Yet worker
orchestration is a **generic** capability, not PF-specific.

## Decision Drivers
- Decouple a generic capability from PF.
- Enable **parallel** work across workers/systems.
- Keep PF focused (backlog, grooming, product pipeline).
- Producer-agnostic (works with other producers too).

## Considered Options
1. Keep it inside PF (status quo) — entangled, single-machine.
2. Full external component, but it also ingests `.md` and creates backlog — wrong boundary.
3. **External execution plane (WorkerGrid) that only consumes a producer's work API** (chosen).

## Decision Outcome
**Chosen option:** Option 3.
- **WorkerGrid** = external, **producer-agnostic** execution plane: worker registry, adapters, leases,
  dispatch, assignment + a **shared coordination service/store**.
- **PF** = producer + SSOT: backlog, grooming/analysis/staleness, **backlog API** (read + status write-back),
  and the **product pipeline**.
- **Executor split:** product generation → PF pipeline; engineering/dev tasks → WorkerGrid.
- **WorkerGrid only** reads the backlog API, assigns, and writes status back — it does **not** ingest `.md`,
  create backlog, or groom.
- **Language:** Go (platform component; single binary; cross-platform).
- **Service:** a coordinator service must run; workers/operators query it for state (multi-machine).

### Consequences
**Positive:** PF simplified; parallel + multi-machine enabled; generic/reusable; clean dependency direction
(WorkerGrid → PF API).
**Negative:** a new service to run/operate; PF↔WorkerGrid contract to maintain; migration effort.
**Risks:** coordination store ops → start SQLite single-node, Postgres multi-node; git sync gaps → companion work.

### Confirmation
- PF works with WorkerGrid disabled (`WORKER_INTEGRATION_ENABLED=0`) — no PF dependency.
- Workers on different systems get the same eligible work + shared leases.
- PF's in-repo worker layer is removable after cut-over.

---

# ADR-0003: Assignment authority in the producer; WorkerGrid is a runtime host

**Status:** Accepted
**Date:** 2026-10-07
**Supersedes:** ADR-0002 (WorkerGrid owns registry/lease + a coordinator service)
**Related:** `docs/WORKERGRID-DESIGN.md` §16, `docs/WORKER-SCHEDULER-OPERATIONS.md`,
`docs/BRANCHING-GIT-WORKFLOW.md`, EPIC `BI-PF-0418`

## Context and Problem Statement
ADR-0002 made WorkerGrid own the worker registry + leases behind a coordinator service. In practice PF is the
only producer, and PF must orchestrate the whole loop (claim → worktree → execute → validate → merge → push →
backlog). The coordinator **duplicated** the assignment record, required a **second always-on service**, and
its per-*project* job model could not run many items of one backlog in parallel (PF's whole backlog is one
project — e.g. `product_forge`).

## Decision Drivers
- One always-on service (PF), not two.
- PF owns the assignment truth (parallel, per-item) and the delivery (gates/PR/merge/push).
- WorkerGrid stays producer-agnostic and thin (run a runtime; no store); coordinator only as fallback.

## Considered Options
1. Keep ADR-0002 (WorkerGrid owns registry/lease + coordinator) — second service; duplicated assignment;
   per-project serialization.
2. **Move assignment + delivery into PF; WorkerGrid becomes a thin runtime host** (chosen).
3. PF-only, no WorkerGrid — loses the pluggable runtime host.

## Decision Outcome
**Chosen option:** Option 2.
- **PF = single authority:** backlog, eligibility, **per-item assignment** (claim/lease/heartbeat/recover over
  `item.execution{}`), worktree/branch creation, and **delivery** (validate → PR → rebase → merge → push →
  `set_delivery`). Exposed via `POST /engineering/assignments/{claim | {id}/heartbeat | {id}/complete |
  {id}/fail | {id}/release | recover}` + `GET /engineering/assignments` (guarded by the `worker` role).
- **WorkerGrid = thin runtime host:** `/wg work` claims from PF, writes `.wg/assignment.json`, runs the runtime
  command in PF's worktree, heartbeats, and reports complete/fail. It keeps **no lease and no store**.
- **Coordinator = fallback** for a producer that does not implement the assignment contract
  (`agent.contract=coordinator`).
- **Two planes (never mixed):** worker plane = PF's OWN backlog (`product_forge`, `BI-PF-*`); pipeline plane =
  generated products (PF pipeline/agents). The worker path is `product_forge`-only (BI-PF-0427).
- **Delivery is optimistic:** validation runs in parallel (own worktree); only the *landing* is serialized; the
  live working tree is never checked out (IS-PF-0036) — `gh pr merge` or an `integrate/*` worktree push-ref.

### Consequences
**Positive:** one always-on service; PF orchestrates the whole loop; parallel per-item execution; WorkerGrid is
thin and producer-agnostic; the coordinator (Stage 3a/3b) becomes fallback-only.
**Negative:** PF grows the assignment + delivery responsibilities; the coordinator code is now fallback-only
(sunk cost); the producer contract gains claim/heartbeat/complete/recover.
**Risks:** expired-lease recovery policy (`PF_LEASE_RECOVERY`, default `REQUIRE_REVIEW` → blocked); the merge
landing needs a remote or `gh`.

### Confirmation
- A worker runs with **only PF up** (`/wg work`); the coordinator is not required.
- Assignment truth = PF `item.execution{}`; `GET /engineering/assignments` shows workers ↔ items.
- The coordinator mode still works behind `agent.contract=coordinator`.

---

# ADR-0004: Feature ↔ Epic ↔ children (backlog model)
**Status:** Accepted   **Date:** 2026-10-08   **Deciders:** product/eng   **Related:** BI-PF-0451 (EPIC), BI-PF-0452 (E2), BI-PF-0444

## Context and Problem Statement
The requirements/architect phase produces a feature list (F-x). The bridge (`core/backlog_link.py`) mapped a
Feature **1:1 to a single backlog item**, flat - no container, no children - and it was **unused** (0 items
carried `feature_id`). Backlog items also lacked shared context, so work was reconstructed by guessing.

## Decision Drivers
One feature should be a **container** of the work items that implement it; features come from the plan; work
must carry understandable context (brief/objective/acceptance criteria/where/how/review).

## Considered Options
- **(A)** keep Feature ↔ single item (flat).
- **(B)** Feature ↔ **Epic** ↔ children (the epic is the feature's backlog representation; children are the work).

## Decision Outcome
**Chosen option: B.** A plan **Feature (F-x)** maps 1:1 to an **Epic** (`type=epic`, `epic.feature_id=F-x`); the
epic's **children** are the work items (`child.epic=epic#`, `child.feature_id=F-x`); status mirrors
feature -> epic -> rollup (an epic is done iff all children are done). The flat bridge is superseded.

### Consequences
**Positive:** features, containers and work form one linked graph; a worker gets a child plus its epic context;
generated products are modeled the same way. **Negative:** the bridge is re-pointed (migration); epic rollup adds
a computed dependency. **Risks:** mixed old/new links during migration -> `children[]`/`epic` refs are audited by
the `backlog-context` gate.

### Confirmation
- A feature creates an epic; its children carry `epic#` + `feature_id`; epic done = all children done.
- The `backlog-context` gate fails an open item whose `epic` ref does not resolve.

---

# ADR-0005: Eventing & Alerting SSOT — Go-first bus; Python thin client

**Status:** Accepted
**Date:** 2026-10-12
**Deciders:** Product/Architecture
**Related:** EPIC BI-PF-1265, BI-PF-1266 (this design); ADR-0001 (Go-first compiled delivery);
BI-PF-0387/0388 (delivery baseline); BI-PF-0390/0393/0394 (A1 contracts + B1 Go core);
docs/EVENTING-ALERTING-SSOT-DESIGN.md

## Context and Problem Statement
Eventing + alerting across Product Forge is fragmented: the canonical run-lifecycle stream
(`core/events.py`) is emit-only; a second orchestration stream with in-process handlers lives in
`core/event_bus.py`; subscribers are bespoke (`core/agent_messenger.py` topics, a legacy WebSocket
transport, `core/notification_system.py`, `core/alerts.py` email). There is **no cross-process
subscriber, no pluggable transports, no subscription/alert-rule registry, and no single reusable
publish/subscribe + alert capability** — so every concern re-invents delivery and every long-running
run (5–30 min) has no reliable completion signal. ADR-0001 requires new shipped/sensitive logic to land
in Go, so the new bus core must be Go with Python as a thin client.

## Decision Drivers
- One SSOT event/alert capability used by all of PF (producers emit once; consumers subscribe).
- Cross-process delivery (the pipeline runs in a child process; API/UI run elsewhere).
- Pluggable transports: in-process callbacks, SSE (clients), webhook (external), notify/email.
- Go-first per ADR-0001; **no duplication** (a feature is Go xor Python); single writer per store.
- Zero regression for existing wired event/alert consumers.

## Considered Options
1. **Keep fragmented** (status quo) — no SSOT; bespoke delivery per concern.
2. **New Python bus** — contradicts ADR-0001 (new shipped logic → Go) and is blocked by
   `scripts/dev/language_rule_check.py` (new `.py` under `core/`, `api/`, `adapters/`).
3. **Go event core + Python thin client over the A1 wire seam** (strangle existing consumers behind
   shims, one-time replacement of the writer later) — chosen.
4. **Big-bang Python→Go rewrite** — non-goal (ADR-0001).

## Decision Outcome
**Chosen option:** Option 3.
- **One** event store (append-only, single writer) is the SSOT; **one** canonical envelope + taxonomy.
- The **new bus core is Go** under `go/` (extend `go/pfcore` or add `go/eventbus`): store + emit +
  monotonic `seq` + cursor, subscriber registry, dispatcher, transports, alert policy; invoked from
  Python via `core/go_host.invoke` + `core/contracts` (A1 wire, fail-closed).
- **`core/events.py` becomes a thin client** (edit-only, no new module) delegating emit to the Go core
  while keeping its public API (`TYPES`, `EVENT_VERSION`, `emit/read/counts`) and envelope back-compat.
- **Existing consumers migrate behind compatibility shims** (never a parallel copy). The **legacy
  WebSocket transport is retired when superseded, never extended**.
- New stores (subscriber registry, alert rules) are registered in `config/store-registry.json` with a
  **single writer**. A1 contracts are extended **additively** (`seq`; subscription; alert-rule; webhook
  signature) with Go↔Python parity tests.

### Consequences
**Positive:** one reusable capability; cross-process; pluggable transports; ADR-0001-conformant;
no-regression via shims.
**Negative:** polyglot seam + Go ramp cost; one long-running Go component to operate; migration effort.
**Risks / mitigations:**
- *Two writers during strangler* → single-writer discipline; staged writer-ownership cutover.
- *SSE over the subprocess wire seam is awkward* → SSE served at the API edge reading the stream
  (Go HTTP only if the edge decision says so).
- *Unreliable external delivery* → at-least-once + `event_id` dedupe + retry to the re-used DLQ.
- *`language_rule_check` blocks new Python in shipped roots* → all new logic in Go; Python edits
  existing files only.

### Confirmation
- A producer emits once; heterogeneous subscribers (inproc/SSE/webhook/email) receive it **across
  processes**.
- No new `.py` under `core/`, `api/`, `adapters/`; `language_rule_check` + `wired_audit` + `precheck`
  green.
- Existing event/alert consumers unchanged (`test_event_ssot`, `test_api_events`, `test_redaction`,
  `test_tracing`, `test_run_status_reconcile` green).

---

# ADR-0006: Enterprise Data Plane (PostgreSQL system of record, object store, tenant isolation, residency)

**Status:** Accepted
**Date:** 2026-10-13
**Deciders:** Product/Architecture
**Baseline:** `origin/develop` @ `e9cc7e371bcf8d79df01ee3e1fe20d5ab01ba8c1` (implementation baseline pinned for EPIC
BI-PF-1292 / EDP-01).
**Related:** EPIC BI-PF-1292 (Enterprise Data Plane); roadmap
`docs/Product_Forge_Enterprise_Performance_Security_DB_Storage_Roadmap.md`; ADR-0001 (Go-first compiled
delivery); ADR-0003 (assignment authority in the producer); ADR-0005 (eventing SSOT);
`docs/WORKER-SCHEDULER-OPERATIONS.md`.

## Context and Problem Statement
Product Forge's own operational state (backlog, issues, run/pipeline state, artifacts, jobs/leases, audit) is
stored as **local JSON files** plus two committed **SQLite** databases, with **no PostgreSQL, no row-level
security, and no server-verified tenant membership** (`api/auth.py` trusts `X-Tenant-Id`/`X-Roles`). The same
state is *also* git-tracked and worked on by multiple sessions, so parallel work collides on shared files
(`counters.json`, `config/id-blocks.json`, `epic.children[]`, derived indexes) and diverges across clones. There
is no single transactional job/lease truth and eventing is ad-hoc. This does not scale to the intended
enterprise, multi-tenant, multi-session workload (tens–hundreds of items in parallel).

## Decision Drivers
- **Enterprise multi-tenancy:** server-verified tenant isolation; authorization on every path.
- **Parallelism without conflict:** concurrent sessions must not contend on shared mutable files.
- **Performance:** indexed, paginated, pooled access; bounded payloads; measured SLOs.
- **Security & residency:** versioned, fail-closed data-residency/transfer policy; secrets out of git.
- **Migration safety:** inventory → parity → dual-read → cutover → rollback; no big-bang rewrite.
- **One writer per concern; Go-first (ADR-0001); thin workers (ADR-0003); one job truth.**
- **Git = code + reviewed config only** — never live operational state.

## Considered Options
1. **Keep file-based state (status quo).** Simple now; scales to ~10 items; conflicts/divergence compound.
2. **Full rewrite of every store at once.** Big-bang risk; prohibited by the roadmap and EOS.
3. **Provider-neutral evolution to an externalized data plane** — canonical interfaces, PostgreSQL system of
   record, object storage for bytes, durable jobs/outbox, git decoupled — chosen.
4. **Premature distributed infrastructure** (Kafka/Kubernetes/multiple DBs) — deferred until measured.

## Decision Outcome
**Chosen option:** Option 3 — evolve behind contracts; externalize state; keep domain APIs.
- **Relational system of record = PostgreSQL** (16 minimum) for authoritative shared/concurrent state
  (tenancy, projects/products, runs/stages, artifacts metadata, jobs/leases, outbox, audit, usage/quotas).
  JSON stores become **read-only compatibility projections** regenerated from the DB.
- **Object store** for bytes via an `ObjectStore` interface: local filesystem (dev) + one S3-compatible
  adapter (deploy). DB holds metadata + opaque object references; never bytes, never provider URLs as identity.
- **Canonical interfaces** (Go, ADR-0001): `RelationalStore`, `ObjectStore`, `ArtifactService`,
  `MemoryRepository`, `JobStore`, `OutboxStore`, `SecretStore`, `AuditStore`, `BackupProvider`,
  `Search`/`Vector` (optional), with a shared local+cloud **conformance** suite.
- **Tenant isolation:** tenant context resolved **server-side** from identity/membership (never trusted from
  headers); PostgreSQL **row-level security** (`USING` + `WITH CHECK`, least-privilege runtime role) as
  defense-in-depth; authorization enforced at every boundary.
- **Jobs/leases:** a durable `JobStore`/`OutboxStore` is the **one** job/lease truth (reuse WorkerGrid's
  PostgreSQL store per ADR-0003); retries, heartbeat/lease expiry, dead-letter; every async effect via the
  **transactional outbox** and the Go event bus (ADR-0005).
- **Data residency** is a **versioned, fail-closed policy** (JurisdictionProfile / RegionResolver / RegionCell
  capability attestation); legal profiles are counsel-owned inputs, never encoded conclusions.
- **Git is decoupled from live state:** backlog/issues/counters/IDs stop being text-merged; derived views are
  generated. Delivery records provenance via `set_delivery` (branch → merge → PR).
- **Migration:** incremental adoption behind interfaces; import/parity/rollback/cutover tooling; affected scope
  first is PF's **own** backlog/issues (glue items), then the broader data plane.

### Consequences
**Positive:** conflict-free parallel sessions; one authority; transactional correctness; enterprise
tenant isolation and residency; provider portability via tested contracts; measurable performance; git stays
for code/config.
**Negative:** a real data plane to build/operate (PostgreSQL + adapters + migrations); polyglot (Go) additions;
migration effort; some file-based consumers need projection compatibility.
**Risks / mitigations:**
- *Two writers during migration* → single-writer discipline + staged cutover; JSON read-only projections.
- *Live migration races* → import/dual-read/parity/rollback; never live text-merge into the cutover repo.
- *Provider capability gaps* → explicit capability attestation; fail closed.
- *Offline/dev + tests* → local Docker PostgreSQL + a file adapter default for isolated tests.
- *Worker streams* → keep the HTTP API contract stable; only the API's storage backend changes behind cutover.

### Confirmation
- Parallel sessions adding/claiming items produce **no** git merge conflicts on operational state.
- Creating item #N is a DB transaction; IDs are unique per scope with no local block minting.
- A tenant context resolved server-side cannot read/write another tenant's rows (RLS + tests).
- `language_rule_check` + `wired_audit` + `precheck` green; migration parity + rollback demonstrated before
  cutover; worker `/wg` claim/complete unchanged.

# ADR-0007: API-first — every capability is a secured API surface

## Context and Problem Statement
Capabilities implemented only as CLIs/scripts/tooling are not consumable by other actors (agents, workers,
generated products, internal or external clients) and cannot carry a consistent security posture. Product
Forge already treats its backlog/governance as an authoritative API (`api/`); each new capability must be
**assessed for API need**, and where there is a need, exposed as a secured API.

## Decision Drivers
- Uniform, secure way for **internal and external** consumers to use PF capabilities.
- Avoid needless API surface (assess the need first), but never trap a needed capability behind a script.
- Security must be uniform: authentication, authorization, tenant isolation, validation, quotas, audit.
- Language rule (BI-PF-0387/0388): new shipped logic is Go; Python API routes stay thin.

## Decision Outcome
For each capability, **do a proper need assessment for an API**, and where a need exists expose a **secured
API surface**:
1. **authn** (token/roles), **authz** (tenant scope; RLS for data — EDP-09), **input validation**,
   **quotas/rate limits** (EDP-10), **audit** (EDP-20), and a versioned **contract** (`api_contract` gate).
2. **Admin capabilities** get an **admin-scoped** API (operator authz), not a hidden local step.
3. Where an API is provided, **tooling/CLIs become clients of it** — not the sole path.
4. If no consumer (internal or external) needs an API, record that justification at Gate 1 (no blind API).
5. New capability **logic is Go** (language rule); Python API routes only validate + delegate.

## Consequences
- Backlog doc-ingest (BI-PF-1396): assess API need → if needed, expose it (tooling becomes a client).
- Schema migrations: assess → admin API where an admin consumer needs it (deploy step remains).
- Every new item's **Gate 1 states its API-surface decision (surface + security, or a written "no need")**.

### Confirmation
- An item reaching delivery either has a secured API surface or an approved "no API need" justification.
- API surface passes `api_contract`/governance gates; authz/tenant-isolation negative tests exist.
- New logic appears in `go/`; Python routes contain no business logic (language-rule green).

# ADR-0008: Service topology — Go-backed capabilities are exposed by Go services

## Context and Problem Statement
ADR-0007 exposes capabilities as APIs, and the language rule (BI-PF-0387/0388) puts new logic in Go. Bridging Go
logic through the Python API (subprocess/cgo) couples two languages in one request path. Each service should own
its language, and services should integrate over network APIs.

## Decision Drivers
- No cross-language in-process/subprocess bridge; keep each service single-language.
- A clear placement rule for where a Go-backed capability lives.
- Uniform security across surfaces.

## Decision Outcome
1. **Go-backed capabilities are exposed by Go API service(s)** — never bridged through the Python API.
2. **Placement criterion:** a capability that owns/operates a domain's data or infrastructure lives in that
   domain's service; cross-cutting Go capabilities live in the **generic capability service**.
   - **EDP data-plane service (Go):** the system of record and everything operating it — schema, tenants/
     projects/runs/stages/attempts/artifacts/objects, object store, RLS (EDP-09), quotas (EDP-10), audit
     (EDP-20), and **schema-migration admin**.
   - **Generic capability service (Go):** cross-cutting Go capabilities (e.g., backlog **doc-ingest** projection),
     which **call other services over HTTP** (e.g., the backlog API) to act.
   - **Python control-plane API (`api/`):** existing Python-owned concerns (backlog, engineering, …).
3. **Integration is over HTTP APIs only** — services consume each other's APIs; no language bridges.
4. All surfaces apply the **same security model** (authn roles, authz/tenant scope, validation, quotas, audit).

## Consequences
- **Doc-ingest** (`context:from-doc`) → **generic capability service**; applies changes via the backlog HTTP API.
- **Migrations admin** (`/admin/migrations/*`) → **EDP data-plane service**; reuses `go/migrate` + `go/store`.
- New Go services must implement the shared security contract (authn/authz/tenant/audit).
- No Python route carries Go-bridged logic.

### Confirmation
- Go-backed endpoints are served by Go services; no Python↔Go bridge exists on a request path.
- Service-to-service calls are HTTP; the EDP/go capability services share the auth/tenant model.

### ADR addendum: audit partitioning, retention and holds (EDP-20 / BI-PF-1312)

**Decision.** Partition `audit` monthly by `at` (UTC) with a shadow-table swap, and treat retention as a
two-stage pipeline (hot -> immutable cold archive -> audited purge) with row-level legal holds.

**Why.** A single append-only table cannot be pruned without a full-table `DELETE` (which the append-only
trigger forbids) and cannot scale indefinitely; partition `DROP` is the only safe prune. Enterprise
retention requires that a drop is not the end of the data's life.

**Constraints accepted (operator sign-off, Gate 1):**
- PostgreSQL >= 14 (row-level BEFORE triggers on partitioned tables).
- A privileged (`pf_owner`/superuser) `ATTACH PARTITION` outside the app boundary is **detected**
  (`audit_assert_hardened`) and audited, not prevented.
- Out-of-range writes **fail closed**; `audit_append_late` is the audited correction path.
- The swap freeze is short but non-zero; the delta bound is enforced, not measured.
- Evidence purged before a hold is recorded is unrecoverable (rejected at hold insert + spoliation alert).

**SQL vs Go ownership (CL-001).** SQL owns single-purpose, set-based primitives (attach/harden/assert,
candidates, mark, drop, extract); all orchestration, state machines, retries and object-storage I/O live in
Go (`go/pfaudit`), which is the single writer for swap and retention.

**Consequences.** New tables are `pf_owner`-only (no blanket RLS policy); `audit_legal_hold_archive` keeps
tenant `SELECT` under `tenant_isolation`. `audit_id_seq` is the one canonical sequence name; `--down`
restores the names and is gated on archives/holds plus an audited reason.

## EDP-16 - Object lifecycle, signed URLs, reconciliation (BI-PF-1308)

- **Lifecycle is an optional capability** (`datastore.LifecycleCapable`, found via `datastore.Lifecycle`), never
  a widened base `ObjectStore`. Providers that cannot lock fail closed with `datastore.ErrUnsupported`.
- **Retention modes**: `GOVERNANCE` is the default; `COMPLIANCE` requires `LifecyclePolicy.ComplianceOptIn=true`
  and is a **one-way door** (cannot be shortened or released). Retention at Put is requested via
  `PutOptions.Retention` + `RetentionMode` and always requires `Immutable`.
- **Local filesystem** cannot lock: retention/lifecycle return `UnsupportedError`; `Immutable` rejects replacing
  an existing object with different content (`ErrImmutable`).
- **Signed URLs have ONE minting boundary** (`go/objpolicy.Mint`): method allowlist, TTL bounds (30s..15m,
  default 5m), and the tenant taken from the authenticated context (`objpolicy.WithTenant`, wired by
  `objpolicy.HTTPMiddleware` with a credential-validating resolver) - never a caller argument. Denials are
  counted per tenant+reason (`objpolicy.Stats()`) with bounded logging.
- **Immutable semantics**: local rejects replacing different content; S3 requires bucket versioning for
  `Immutable` without retention (`UnsupportedError` otherwise). Retention at Put defaults to GOVERNANCE;
  COMPLIANCE requires `ComplianceOptIn=true`.
- **Reconciliation is read-only** (`go/objreconcile`): manifest vs `List`/`Head`, sha256 comparisons (never
  ETags), deterministic versioned report; it never deletes or repairs.
- **Ownership/modules**: each new package is its own module per the one-module-per-directory rule; the
  `go-modules` gate discovers and tests all modules.

# ADR-0009: Formal retention of global config stores (design-systems)

**Status:** Accepted
**Date:** 2026-10-24   **Deciders:** architecture + HIL   **Related:** BI-PF-1476, BI-PF-1439, BI-PF-0439

## Context and Problem Statement
`config/design-systems.json` is registered as a configuration store but had no recorded decision about where
its data lives. The stale title suggested moving it behind `tool_settings`. The catalog holds global,
read-only product metadata (product types, style, stack, palette, radius/type/motion dials, component set,
a11y target); `tool_settings` is tenant-scoped (`tenant_id`), so storing a global catalog there would mix a
global concern into a tenant partition and force duplicate rows per tenant.

## Decision Drivers
- One truth per concern; one writer per file (CL-001).
- Global product metadata is not tenant data and must not be tenant-scoped.
- Reversibility and no data migration for a store with no runtime rows.
- Durable rationale that survives the closing of the work item.

## Considered Options
1. **Move into `tool_settings`** - rejected: tenant-scoped table, wrong ownership and needless duplication.
2. **Formal retention as a file-backed global catalog** - chosen: matches the existing config pattern and
   stays swappable when the Go writer lands.
3. **Retain by default with no rationale** - rejected: the next contributor would re-propose the migration.

## Decision Outcome
**Chosen option:** "Formal retention as a file-backed global catalog" because the data is global, read-only,
and not tenant-scoped.

### Consequences
**Positive:** no schema/data change; the owner remains `core/go_host.py` with the planned Go writer
`go/pfcore/design_system.go` (BI-PF-1439); the registry carries a durable reason.
**Negative:** the catalog remains file-backed, so a future multi-writer or tenant-specific requirement needs
a new ADR. **Risks:** a contributor edits the registry without reading the ADR; mitigated by the gate check.

### Confirmation
- `python scripts/dev/store_registry_relationships.py` asserts the pinned retained tuple, non-empty
  `retained_reason`, and a `decision_ref` that resolves to this ADR's index row and section.
- `python scripts/dev/gen_store_dataflow.py --check` proves the generated inventory is fresh.
- `python scripts/dev/precheck.py` passes with no schema or data change.

### Supersede trigger
A new ADR is required if BI-PF-1439 makes the catalog runtime-writable, if the catalog becomes
tenant-specific, or if a second writer needs shared tenant settings. Re-open via a new backlog item that
supersedes this ADR; do not silently flip the registry target.
