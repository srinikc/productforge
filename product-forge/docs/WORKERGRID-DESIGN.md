# WorkerGrid — Design (external execution plane)

**Status:** design / decision (for review). **Related:** ADR-0002, `docs/ARCHITECTURE-DECISIONS.md`,
`docs/PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md`, `docs/WORKER-SCHEDULER-OPERATIONS.md`.

**WorkerGrid** is a **generic, producer-agnostic execution plane** for assigning work to workers. It is
**separate from Product Forge (PF)**. PF is the **producer + SSOT**; WorkerGrid is the **consumer/client**.

## 1. Why
- The worker/scheduler currently lives **inside PF** (`core/scheduler.py`, `job_manager.py`,
  `worker_registry.py`, `worker_adapters.py`, `work_pull.py`, `dispatcher.py`, `api/routers/workers.py`),
  which entangles a **generic** capability with PF and blocks **multi-machine / parallel** use.
- We want **parallel** execution across workers/systems (today a single opencode session is sequential), and
  workers that can be **registered and leased** centrally.

## 2. Roles (locked)
| Concern | Owner |
|---|---|
| Backlog SSOT (items, priority/order) | **PF** |
| Grooming / analysis / readiness / **staleness** | **PF** (integral) |
| **Backlog API** (read + status write-back) | **PF** |
| Product generation (build/evolve a product) | **PF pipeline** |
| Worker registry · adapters · leases · dispatch · assignment | **WorkerGrid** |
| Coordination state (shared) | **WorkerGrid** |

**Dependency direction:** WorkerGrid → PF backlog API. **PF depends on nothing from WorkerGrid.**

## 3. Executor split (by item nature)
```
backlog item
  ├─ product-generation intent (build/evolve a product) → PF pipeline (intake-driven; sequential run lock)
  └─ engineering / dev task (PF change, project dev, fix) → WorkerGrid (workers; parallel)
```
- **PF's own backlog** (dev tasks) runs through **WorkerGrid**, not the PF pipeline.
- The **PF pipeline** builds products — it is **not** the executor for PF development.
- Project/product **changes via intake** already enqueue **pipeline runs** (`intake_channels.execute_now` /
  `schedule(at)` → `run_entry.enqueue`); direct project *dev* items go to WorkerGrid.

## 4. Interfaces
PF exposes (already exists unless noted):
- `GET /backlog` (list), `GET /backlog/items/{id}`
- **`GET /backlog/eligible`** — fresh-only, priority-ordered, ready-to-assign *(add)*
- `POST /backlog/items/{id}/status` — execution write-back. The concrete statuses are PF's own vocabulary
  (`scheduled` = claimed/assigned, `executing` = running, `done`→`completed` on success, `blocked` = failed
  or gated); see §14 for the exact mapping the agent writes.

WorkerGrid:
- reads eligible items from PF, assigns to workers, and **writes status back** to PF.
- never creates backlog items, never ingests `.md`, never grooms.

## 5. Shared coordination state — the missing piece
Multi-machine requires state **outside** local files. WorkerGrid runs a **service** with a **shared store**:
- **Store:** workers, leases, assignments, heartbeats (SQLite single-node → PostgreSQL for multi-node;
  the pluggable store landed in Stage 3b, §15).
- **Service API** that workers and operators query:
  - `POST /workers/register`, `POST /workers/{id}/heartbeat`, `POST /workers/{id}/report`
  - `POST /work` (claim next assignment), `POST /leases/{id}/renew`, `POST /leases/{id}/release`
  - `GET /status`, `GET /workers`, `GET /assignments`
- **Yes — a service must be running**, and workers/operators query it for state. This is the "central
  coordinator." PF's backlog stays in PF (backlog API); WorkerGrid holds coordination state and writes
  execution status back to PF.

## 6. Language & deployment
- **Language: Go** (target) — WorkerGrid is a **platform/execution component**: single static binary, no
  runtime deps, cross-platform (linux/amd64+arm64, windows, darwin), easy to ship on-prem/air-gap/OEM, and
  it aligns with the Go-first rule (shipped/platform/sensitive → Go).
- **Deployment:** the coordinator **service** + worker agents. Single-node (local, SQLite) for dev; multi-node
  (service + PostgreSQL) for teams/multi-machine — both store backends implemented (§15).
- A Python spike was used for Stage 2b; it was **replaced by the Go binary in Stage 3a** (§13).

## 7. Multi-machine git sync (companion) — Stage 2a implemented
Coordination state ≠ code sync. **Stage 2a (done):**
- `VCSManager.fetch()` + `base_ref()` — new worktrees branch off **`origin/<integration>`** (fetched) when a
  remote exists, so cross-system workers aren't stale (falls back to local without a remote).
- `VCSManager.sync()` + **`/pf sync`** — fetch + push the integration branch.
- Worker: after committing, optionally pushes its **feature branch** (gated by `PF_AUTO_PUSH`, default off).
- `PF_AUTO_PUSH` (env-flags, owner `core/vcs.py`): auto-push after a controlled merge / worker commit (off by default).
- Gate: `scripts/dev/vcs_worktree_check.py` covers fetch + origin-base + auto-push gating.

**Stage 2b (implemented):** the standalone coordinator **service** + shared store landed (§12), and the
in-PF worker layer was removed (ADR-0002 cut-over). Remaining for Go (§6): Python spike → Go binary,
SQLite → PostgreSQL for multi-node.

## 8. Offline ingestion stays in PF
External `.md` (ChatGPT/Gemini, etc.) is ingested **by PF** (intake channel → analyze → backlog) — manually by
the operator or via an intake channel. **WorkerGrid does not ingest or create backlog.**

## 9. Gaps / plan
1. ~~PF: add `GET /backlog/eligible`~~ — served by `GET /api/v1/engineering/schedule/eligible` (status
   write-back via `POST /api/v1/backlog/items/{id}/status`).
2. PF: offline `.md` → intake channel ingestion. *(PF-side)*
3. WorkerGrid: ~~extract/implement the external execution plane~~ Python spike done (§12); ~~Go service~~
   **Go coordinator done (Stage 3a, §13)**; **worker agents + PostgreSQL** still to build (§6).
4. ~~Git sync: fetch/push + auto-push-after-merge (gated).~~ Done (Stage 2a, §7).
5. ~~Cut over: remove the in-PF worker layer.~~ Done (Stage 2b, §12).

## 10. Non-goals
- WorkerGrid does not own backlog, grooming, or product generation.
- PF's agents stay native; WorkerGrid is for external/dev-task workers.
- No change to PF's backlog SSOT or the product pipeline.

## 11. Stage 1 implemented (decoupled command surface + component)
- **Component:** `workergrid/` (sibling of `product-forge/`) — `wg.py` (CLI), `client.py` (producer API client),
  `_cfg.py`, `config.json`, `instructions.md`, `README.md`, `state/` (local, gitignored).
- **Command:** `/wg <verb>` → `.opencode/command/wg.md` (project) + `.opencode/command_global/wg.md` (global,
  installed to `~/.config/opencode/command/wg.md`). Verbs: register, list, status, unregister, work, schedule,
  adapters, dispatch, instruct, config.
- **`/wg instruct`** edits **`workergrid/instructions.md`** (the shared worker charter; edit any time).
- **Moved out of `/pf`:** worker/scheduler/work/adapters/dispatch verbs (removed from `scripts/pf.py` VERBS +
  `.opencode/command/pf.md` + global copy). `/pf` keeps product, backlog, dogfood, validate, release, package,
  audit, status, pidl.
- **Gates:** `scripts/dev/wg_surface_check.py` (added to precheck) + updated `pf_surface_check.py`.
- **Stage 2 (later):** extract coordination (registry/leases/dispatch) into a standalone **Go** service with a
  shared store + git sync (fetch/push). Until then, Stage 1 keeps a local coordination store and consumes PF's
  producer API (`/api/v1/engineering/schedule/*` read, `/api/v1/backlog/items/{id}/status` write-back).

## 12. Stage 2b implemented (coordinator service + shared store + cut-over)
*(Coordinator implementation superseded by the Go binary in Stage 3a — §13.)*
- **Service:** `workergrid/service.py` — stdlib HTTP coordinator (`python workergrid/wg.py serve`;
  `config.json` `service_host`/`service_port`, bearer token via `token_env`). Endpoints: worker
  register/heartbeat/unregister, `POST /work` (claim next + lease), lease renew/release/recover,
  `GET /status`, `GET /workers`. *(Design §5 extras `POST /workers/{id}/report` + `GET /assignments`
  are not built yet — leases carry the assignment state.)*
- **Shared store:** `workergrid/store.py` — SQLite (`state/workergrid.db`, gitignored) with `BEGIN
  IMMEDIATE` single-writer claim + lease expiry/recover; multi-node target stays PostgreSQL (§6).
- **Claim flow (producer contract):** WorkerGrid `POST /work` → `GET /api/v1/engineering/schedule/next`
  (PF refreshes stale analyses first (BI-PF-0389) and attaches `pidl_context` + `execution_policy`
  (BI-PF-0379)) → WorkerGrid takes the lease and hands the contract to the worker.
- **Cut-over (in-PF worker layer removed):** `core/{worker_registry,worker_adapters,work_pull,dispatcher}.py`,
  their gates, and the 6 worker pipeline tests deleted; `/api/v1/engineering/{workers,work,adapters,dispatch*}`
  routes removed; `scripts/dev/single_path_check.py` now **fails if they reappear**; `/pf` lost the
  work/worker verbs (they live in `/wg`).
- **Gates:** `wg_surface_check` (required verbs incl. `serve`), `single_path`, `pidl-synthesis` +
  `staleness` (wiring assertions moved from `work_pull` to `scheduler.next_eligible`), all under
  `precheck`.

## 13. Stage 3a implemented (Go coordinator + parity + cut-over) — BI-PF-0412
The Python coordinator (`service.py` + `store.py`) is **deleted**; the coordinator is now one static Go
binary (`CGO_ENABLED=0`, pure-Go SQLite via `modernc.org/sqlite`):
- **Binary:** `workergrid/cmd/wg-coordinator` → `workergrid/bin/wg-coordinator` (gitignored).
  `python workergrid/wg.py serve` / `/wg serve` exec-shims to it (fail-closed with the build hint).
  Flags `-host`/`-port`; same startup line as the spike; `config.json` read from `WORKERGRID_HOME` or
  walked up from the executable/cwd; env overrides `WORKERGRID_STATE_DIR`, `WORKERGRID_PF_API_URL`,
  `WORKERGRID_TOKEN`, `WORKERGRID_LEASE_SECONDS`.
- **Layout:** `workergrid/internal/{config,store,httpapi,producer}` (Go `cmd/`/`internal/` convention,
  `workergrid/go.mod` — the repo's first Go module). Store claim atomicity: store-wide mutex +
  single-connection DB (the spike's `BEGIN IMMEDIATE` equivalent).
- **Parity proof:** `test-framework/tests/pipeline/test_workergrid_service_contract.py` runs every
  behavior against **both** implementations (python leg auto-skipped post-cutover; `WG_CONTRACT_REQUIRE_GO=1`
  fails if the binary is missing). Envelope RCCA: `POST /work` unwraps the producer's canonical
  `{request_id, status, data:{…}}` envelope one level (spike bug, noted on BI-PF-0412).
- **Gates:** `wg_go_check` (gofmt + build + vet + test + contract suite, added to `precheck` fast tier,
  area `workergrid`/`wg`); `pidl-synthesis` now verifies passthrough in `internal/httpapi/httpapi.go`.
- **Not in this slice:** worker agents (3c), PostgreSQL (3b).

## 14. Stage 3c implemented (worker agent execution) — BI-PF-0413
The coordinator (Stage 3a) assigns; the **agent** now executes. `workergrid/cmd/wg-agent` → `bin/wg-agent`
is a second static Go binary; `python workergrid/wg.py agent` / `/wg agent` exec-shims to it (fail-closed
with the build hint), and it is gated by the same `wg_go_check`. One agent process = one execution slot.

- **Loop:** `recover → claim → write-back "scheduled" → isolated git worktree → execute runtime command →
  heartbeat/renew lease → write-back "executing" → success|blocked → release`. `-once` claims+runs at most
  one item then exits (tests/one-shots).
- **Two HTTP surfaces only:** the coordinator (claim/lease lifecycle) and the producer API (status
  write-back). No PF/producer code is imported — WorkerGrid stays producer-agnostic (ADR-0002).
- **Status mapping (PF vocabulary):** claim → `scheduled`; command start → `executing`; exit 0 →
  `agent.success_status` (default `verifying`, keeping gates/DoD in the human path); non-zero → `blocked`
  (note carries the exit code + output tail); PIDL `execution_policy.approval_required` → `blocked` without
  executing (fail-closed).
- **Isolation (IS-PF-0036):** each assignment runs in its own `git worktree` + `wg/<item>-<ts>` branch off
  `agent.base_ref` (default `develop`); the main checkout is never touched.
- **Crash safety:** the agent owns **all** producer write-back, including `POST /leases/recover` each poll —
  recovered leases are reopened to `queued`, so a worker that dies mid-run cannot wedge an item in a
  non-eligible status. The coordinator keeps lease truth only and is unchanged from Stage 3a.
- **Runtime commands:** `agent.runtimes.<name>.command` is a shell template; placeholders `{item_id}`
  `{title}` `{worktree}` `{branch}` `{base_ref}` are substituted (shell-quoted) and exported as `WG_*` env
  vars. On Windows the line runs from a generated `.cmd` file (cmd `/c` quote-stripping workaround).
- **Journal:** JSONL at `state/agent-journal.jsonl` (start, register, claim, worktree, exec_start/end,
  writeback, release, reopen, …) — the run-bound evidence trail.
- **Proof:** `test-framework/tests/pipeline/test_workergrid_agent_e2e.py` drives both binaries against a
  stub producer + throwaway git repo: happy path (status order, operator auth, worktree/branch, journal),
  command failure → blocked, approval gate → fail-closed, no-work clean exit, heartbeat/renewal.
- **Not in this slice:** auto-push (agent push flag default off), PostgreSQL (3b), remote fleet.

## 15. Stage 3b implemented (pluggable store: SQLite + PostgreSQL) — BI-PF-0414
The coordination store is now backend-pluggable — **SQLite** (default, single-node) or **PostgreSQL**
(multi-node: several coordinator processes sharing one store). Same coordinator binary, same HTTP API, one
`store` package — no second store or engine.

- **Driver:** pure-Go `github.com/jackc/pgx/v5/stdlib` registered as `pgx`; SQLite stays `modernc.org/sqlite`
  (`sqlite`). Both `CGO_ENABLED=0`.
- **Config:** `store: {driver: sqlite|postgres, dsn}`; env `WORKERGRID_STORE_DRIVER` / `WORKERGRID_STORE_DSN`.
  Default = SQLite at `<state_dir>/workergrid.db` (back-compat). PostgreSQL requires an explicit DSN;
  startup `Ping` + schema ensure **fail closed** with a clear error.
- **Dialect mechanics:** `rebind` converts `?` → `$n` for PostgreSQL; the schema differs only in the float
  column (`REAL` vs `DOUBLE PRECISION`). UPSERT + `RETURNING` are shared.
- **Atomic claim (multi-node):** claim is a single statement —
  `INSERT … ON CONFLICT(item_id) DO UPDATE SET … WHERE leases.expires_at < now RETURNING worker_id` — so two
  coordinator processes cannot both claim one item. A live lease returns no row → `claimed:false` +
  "already leased by X" (Python parity). SQLite additionally keeps the store-wide mutex + single connection.
- **Limitation (documented):** lease expiry compares node wall-clock, so multi-node deployments need roughly
  synchronized clocks; a DB-time lease variant is deferred.
- **Proof:** Go unit tests for `rebind`/dialect/schema and fail-closed opens
  (`workergrid/internal/store/store_test.go`); an env-gated PostgreSQL e2e
  (`test-framework/tests/pipeline/test_workergrid_pg_store.py`, needs `WORKERGRID_PG_DSN`) proving two
  independent coordinators share state (2nd sees the 1st's lease, claim conflict, renew/release cross-process)
  and expired-lease recovery. The contract suite still runs on SQLite unchanged.
- **Not in this slice:** schema-migration engine (`CREATE TABLE IF NOT EXISTS` only), DB-time leases,
  HA/leader election, pooling tuning.

## 16. Stage 3x / parallel run engine implemented (PF authority + thin client) - EPIC BI-PF-0418 / ADR-0003
The execution model changed so PF drives the whole loop and WorkerGrid became a **thin runtime host** (ADR-0003
supersedes ADR-0002's lease/registry ownership). Shipped via BI-PF-0419..0428:

- **Per-item assignment (0419):** `job_manager.claim_next` is keyed by ITEM (not project) over
  `item.execution{}` - so N items of one backlog run in parallel. Assignment API:
  `POST /engineering/assignments/{claim | {id}/heartbeat | {id}/complete | {id}/fail | {id}/release | recover}`
  (+ `GET /engineering/assignments`, 0422); guarded by a new **`worker`** role. Claim creates the worktree and
  returns the package.
- **Parallel validation (0420):** runs are isolated (each `validation/<run_id>` worktree) with **run-scoped**
  results; per-repo concurrency cap (`max_parallel_validations`).
- **Optimistic delivery (0421 + 0428):** `core/delivery.py` = push branch + PR → validate → **serialized
  landing** that never checks out the live tree: `gh pr merge` (primary) or an `integrate/<item>` worktree +
  `push HEAD:develop` (fallback) → `set_delivery` + completed. Failure/conflict → **blocked**.
- **Worker path is `product_forge`-only (0427):** the assignment endpoints + `schedule/next?stage=execute`
  reject `project` (generated products use the PF pipeline/agents - the two planes never mix).
- **Thin client (0423):** `agent.contract` = auto | pf-assignments | coordinator. In PF mode the agent claims
  from PF, writes `<worktree>/.wg/assignment.json`, runs the runtime there, heartbeats, and completes/fails via
  PF - **no coordinator, no lease, no store**. `/wg work` = the worker; `/wg status` proxies PF assignments.
  The **coordinator is the fallback** (`contract=coordinator`).
- **Dedup guard (0422):** claim-time skip of a near-duplicate of an active/higher-ranked open item. Whole-backlog
  dedup **marking** at grooming is BI-PF-0432 (Option B).
- **Concurrency caps:** `max_parallel_assignments`, `max_parallel_validations` (`config/capacity.json`).
