# Worker & Scheduler — Operations Guide

> **SUPERSEDED (ADR-0002 / Stages 2b–3c):** the in-PF worker layer (`core/worker_registry.py`,
> `core/worker_adapters.py`, `core/work_pull.py`, `core/dispatcher.py` and the `/pf` work verbs) was
> **removed**. Workers now coordinate through **WorkerGrid** (`/wg …`, see `docs/WORKERGRID-DESIGN.md`
> §12–§14). What still applies from PF: backlog SSOT (`core/backlog.py`), eligibility/`next_eligible`
> (`core/scheduler.py`), `core/job_manager.py`, and `core/pidl.py`.

How to run workers with **WorkerGrid**: register, claim work, execute it (the agent), and dispatch. The
worker layer is **external and optional** — PF's own agents stay native and are **never** routed through it.

## 1. Components (owners)

| Concern | Owner |
|---|---|
| Backlog SSOT (work items) | `core/backlog.py` (PF) |
| Eligibility (what can run now) | `core/scheduler.py` (`eligible`, `next_eligible`) (PF) |
| Decision gate (optional) | `core/pidl.py` (PF) |
| Worker registry (capacity) | WorkerGrid coordinator `store` |
| Claim + lease (atomic) | WorkerGrid coordinator `store` |
| Assignment + execution | WorkerGrid agent (`cmd/wg-agent`) |
| Command surface | `workergrid/wg.py` (`/wg …`) + coordinator HTTP API |

> Historical rows (now removed): `core/worker_registry.py`, `core/worker_adapters.py`,
> `core/work_pull.py`, `core/dispatcher.py` — see the banner.

## 2. Config & flags

WorkerGrid reads `workergrid/config.json` (live; env overrides win):

| Key / env | Default | Meaning |
|---|---|---|
| `pf_api_url` / `WORKERGRID_PF_API_URL` | `http://127.0.0.1:8000` | producer (PF) API base |
| `token_env` (e.g. `API_TOKEN`) / `WORKERGRID_TOKEN` | — | bearer token for producer + coordinator |
| `default_runtime` | `opencode` | runtime used when a verb omits `--runtime` |
| `lease_seconds` / `WORKERGRID_LEASE_SECONDS` | `3600` | assignment lease TTL |
| `store.driver` / `WORKERGRID_STORE_DRIVER` | `sqlite` | coordination store backend: `sqlite` (single-node) or `postgres` (multi-node) |
| `store.dsn` / `WORKERGRID_STORE_DSN` | — | store DSN; sqlite defaults to `<state_dir>/workergrid.db`, **required** for postgres |
| `service_host` / `service_port` / `service_url` | `127.0.0.1` / `8790` | coordinator bind + client URL |
| `agent.repo_root` | — | git repo the agent executes in (**required**) |
| `agent.base_ref` | `develop` | worktree branch base |
| `agent.worktrees_dir` | `worktrees` | isolated worktrees root |
| `agent.success_status` | `verifying` | PF status written on an exit-0 run |
| `agent.runtimes.<name>.command` | — | shell command template per runtime |
| `agent.timeout_seconds` | `0` | command timeout (0 = none) |
| `WORKERGRID_HOME` | walked | WorkerGrid dir (where `config.json` lives) |
| `WORKERGRID_STATE_DIR` | `state/` | coordination DB + agent journal |

The PF-side flags that governed the removed in-PF layer (`WORKER_INTEGRATION_ENABLED`,
`WORKER_AUTO_DISPATCH`, `PF_LEASE_*`, `PF_WORKER_STALE_SECONDS`) are **historical**.

## 3. Register a worker

```
/wg register --runtime opencode --caps python,code
/wg list
/wg status <worker_id>
/wg unregister <worker_id>
```
Runtimes: `opencode` · `claude-code` · `remote` · `command` · `native` (`/wg adapters`).
Coordinator route: `POST /workers/register`. Registration requires the coordinator to be reachable
(`/wg serve`); if it isn't, the CLI falls back to a **local** store (single machine).

## 4. Claim work — `/wg work`

```
/wg work --worker WRK-…          # or --runtime opencode (auto-registers)
/wg schedule eligible|next|status
```
`/wg work` asks the coordinator to claim the next eligible item (`POST /work`), which asks PF
`GET /api/v1/engineering/schedule/next`, then takes an atomic lease in the coordinator store and returns an
**assignment package** (`item_id`, `title`, `assignment_id`, `expires_at`, and the producer's
`pidl_context` + `execution_policy`).

**`/wg work` creates no folder and does not execute** — it only claims and returns the package.

## 5. Execute work — `/wg agent`

```
/wg agent [--runtime R] [--worker-id W] [--scope S] [--project P] [--once]
```
`/wg agent` runs the Go agent (`bin/wg-agent`), one process = one execution slot. Loop:

1. `POST /leases/recover` → reopen any recovered item to `queued` (crash safety);
2. claim (`POST /work`) → write back `scheduled`;
3. create an **isolated git worktree** + `wg/<item>-<ts>` branch off `agent.base_ref`;
4. run the runtime command template in that worktree (placeholders `{item_id}` `{title}` `{worktree}`
   `{branch}` `{base_ref}`; also exported as `WG_*` env vars);
5. heartbeat + renew the lease on a ticker while it runs → write back `executing`;
6. on finish: exit 0 → `agent.success_status` (default `verifying`); non-zero → `blocked`; then release.

PIDL `execution_policy.approval_required` → the agent writes `blocked` **without executing** (fail-closed).
A JSONL journal is written to `state/agent-journal.jsonl` (run-bound evidence).

Status mapping (PF vocabulary): claim → `scheduled`; running → `executing`; success → `verifying`
(configurable); failure/gate → `blocked`.

## 6. Dispatch — `/wg dispatch`

```
/wg dispatch          # assign eligible work to ONLINE/IDLE registered workers (does not execute)
```
`/wg dispatch` claims for each ONLINE/IDLE worker via the coordinator; the workers' `/wg agent` processes
then execute. Continuous execution comes from running `/wg agent` (a loop) — **PF does not spawn sessions;
a worker must already be running.**

## 7. Eligibility (why an item is or isn't assignable)

An item is **eligible** only if **all** hold (`core/scheduler.py:eligible`, PF-side):
- status is open (`new`/`accepted`/`queued`/`scheduled`),
- **analysis is `COMPLETE`** (groomed — un-groomed items are NOT eligible),
- dependencies met (unknown refs block, fail-closed),
- readiness not false, not already leased, no path contention, capability matches the worker.

> **Groom the backlog first** or `/wg work` finds nothing. Deterministic grooming runs on create; deeper AI
> grooming is explicit (`/pf backlog groom <id>`).

**Execution claims (BI-PF-0416):** the worker claim path passes `stage=execute` to
`GET /api/v1/engineering/schedule/next`, which restricts eligibility to NOT-yet-executed items
(`new`/`accepted`/`queued`/`scheduled`). Already-executed items (`implemented`/`verifying`) are excluded, so a
worker cannot re-claim and re-run work that has already been executed. Omitting `stage` keeps the historical
gate (a verification stage may still pick those up).

### 6a. Analysis staleness — revalidation at pickup (BI-PF-0389)

Analysis is done at entry; by pickup the architecture may have changed, so PF prevents executing a **stale
design**: `core/backlog.arch_fingerprint()` hashes architecture-significant files
(`config/grooming-guidelines.json → arch_significant`); a `COMPLETE` analysis records it, and
`scheduler.eligible()` marks the item **not eligible** when the fingerprint no longer matches.
`scheduler.next_eligible` refreshes stale analyses at pickup (bounded, deterministic/offline-safe) and the
item becomes eligible again. Manual:
`python -c "from core import grooming; print(grooming.refresh_stale('product_forge'))"`.

## 8. Lease & recovery

- A claim attaches a **lease** in the coordinator store (`lease_seconds`); two workers can't get the same item.
- Heartbeat + `POST /leases/{item}/renew` keep it alive; the agent renews on a ticker.
- Expired leases: `POST /leases/recover` frees them. The **agent** calls recover each poll and reopens the
  item to `queued` — so a worker that dies mid-run cannot wedge an item in a non-eligible status.
- Release: `POST /leases/{item}/release` frees the lease and the worker (IDLE).

**Multi-node:** set `store.driver=postgres` (+ `store.dsn` / `WORKERGRID_STORE_DSN`) so several coordinator
processes share one store. Claim is a single atomic statement, so two processes cannot double-claim; expired
leases are recovered as above. Leases compare node wall-clock — keep clocks synced.

## 9. End-to-end

```
1. check out PF (your working copy) + build the binaries: cd workergrid && go build -o bin/ ./cmd/...
2. /wg serve                                   # coordinator (shared state)
3. /wg agent --runtime opencode                # a worker: claims + executes (loop)
   # or, one-shot: /wg agent --once
4. work lands on an isolated wg/<item>-<ts> branch in agent.worktrees_dir; the item is written back
```

## 10. API reference (coordinator = WorkerGrid; producer = PF)

Coordinator (bearer token when configured):

| Method | Route |
|---|---|
| GET | `/status` · `/workers` · `/workers/{id}` |
| POST | `/workers/register` · `/workers/{id}/heartbeat` · `/workers/{id}/unregister` |
| POST | `/work` · `/leases/{id}/renew` · `/leases/{id}/release` · `/leases/recover` |

Producer (PF) routes WorkerGrid uses: `GET /api/v1/engineering/schedule/next|eligible`,
`POST /api/v1/backlog/items/{id}/status` (operator role). The historical
`/api/v1/engineering/{workers,work,dispatch,…}` routes belonged to the removed in-PF layer.

## 11. Troubleshooting

| Symptom | Cause |
|---|---|
| `/wg work` → `no eligible work` | backlog not groomed / deps unmet / all leased / capability mismatch |
| `/wg agent` → `agent.repo_root not set` | set `agent.repo_root` (and `agent.runtimes.<r>.command`) in `config.json` |
| `coordinator binary missing` | build it: `cd workergrid && go build -o bin/ ./cmd/wg-coordinator ./cmd/wg-agent` |
| dispatch does nothing | no ONLINE/IDLE workers, or coordinator not running |
| `/wg work` assigned but nothing ran | claim ≠ execute; run `/wg agent` |
| two workers got same item | should not happen — coordinator lease + atomic claim prevent it |

## 12. Concurrency — one working tree per session (IS-PF-0036)

**Never run two concurrent sessions in the same folder.** git `HEAD`/branch state is global to the working
directory, so one session's checkout/commit races the other's — a commit can land on `develop` directly.
Give each session its **own clone or `git worktree`** (the `/wg agent` does this automatically for every
assignment):

```
git worktree add ../pf-worker-1 develop     # separate working tree for a worker session
```

## 13. Non-goals

- PF's own agents are **not** routed through WorkerGrid (native path).
- WorkerGrid never creates/grooms backlog items; it reads work and writes execution status back.
- Auto-push is off by default (the runtime command decides what to commit).
