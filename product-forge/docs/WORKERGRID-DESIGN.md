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
- `POST /backlog/items/{id}/status` — execution write-back (assigned/in-progress/done/blocked)

WorkerGrid:
- reads eligible items from PF, assigns to workers, and **writes status back** to PF.
- never creates backlog items, never ingests `.md`, never grooms.

## 5. Shared coordination state — the missing piece
Multi-machine requires state **outside** local files. WorkerGrid runs a **service** with a **shared store**:
- **Store:** workers, leases, assignments, heartbeats (SQLite single-node → PostgreSQL for multi-node).
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
  (service + PostgreSQL) for teams/multi-machine.
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
