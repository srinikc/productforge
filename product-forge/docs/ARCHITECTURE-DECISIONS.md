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

