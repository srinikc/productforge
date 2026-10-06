# Worker & Scheduler — Operations Guide

How to register a worker, pull work **manually**, and enable **automatic** assignment. The external-worker
layer is **optional and removable** (`WORKER_INTEGRATION_ENABLED`); PF's own agents stay native and are
**never** routed through it.

## 1. Components (owners)

| Concern | Owner |
|---|---|
| Backlog SSOT (work items) | `core/backlog.py` |
| Eligibility (what can run now) | `core/scheduler.py` (`eligible`, `next_eligible`) |
| Claim + lease (atomic) | `core/job_manager.py` (`claim_next`, `renew_lease`, `release`, `recover_expired`) |
| Worker registry (capacity) | `core/worker_registry.py` |
| Runtime adapters | `core/worker_adapters.py` |
| Manual pull + assignment package | `core/work_pull.py` |
| Automatic dispatch | `core/dispatcher.py` |
| Decision gate (optional) | `core/pidl.py` |
| Command surface | `scripts/pf.py` (`/pf …`) + `api/routers/engineering.py` |

## 2. Flags (`config/env-flags.json`)

| Flag | Default | Meaning |
|---|---|---|
| `WORKER_INTEGRATION_ENABLED` | `1` | master switch; `0` disables the whole worker layer (endpoints → 503) |
| `WORKER_AUTO_DISPATCH` | `0` | `1` = automatic assignment without a manual pull |
| `WORKER_DISPATCH_POLL_SECONDS` | `5` | dispatch poll interval |
| `PF_LEASE_SECONDS` | `3600` | assignment lease duration |
| `PF_LEASE_RECOVERY` | `REQUIRE_REVIEW` | policy on expired lease: `RESUME|RETRY|REASSIGN|MARK_FAILED|REQUIRE_REVIEW` |
| `PF_WORKER_STALE_SECONDS` | `90` | heartbeat age after which a worker is `STALE` |

## 3. Register a worker

```
# slash command (in an opencode session)
/pf worker register --runtime opencode --caps python,code

# CLI equivalent
python scripts/pf.py worker register --runtime opencode --caps python,code

# other verbs
/pf worker list
/pf worker status <worker_id>
/pf worker unregister <worker_id>
```
Runtimes: `opencode` · `claude-code` · `remote` · `command` · `native` (see `docs/PFSSOT-P11-ADAPTERS.md`).
API: `POST /api/v1/engineering/workers/register`.

## 4. Pull work — MANUAL

```
python scripts/pf.py work --worker WRK-…          # or: --runtime opencode (auto-registers)
```
What happens (`core/work_pull.py:pull`):
1. eligibility + priority via `scheduler.next_eligible`,
2. atomic claim + lease via `job_manager.claim_next`,
3. adapter `accept_assignment`,
4. returns an **assignment package** (`task`, `contract`, `pidl_context`, `execution_policy`).

**`/pf work` creates no folder** and does **not execute**. It only claims and returns the package.

Execute the assignment (opt-in):
```
python scripts/pf.py work ...           # get the package, then execute it
# or programmatically: core.work_pull.start(scope, project, item_id, worktree=…, command=…)
```
Execution runs in an **isolated git worktree** (`<repo>-worktrees/<slug>/`, `core/vcs.py`), on a feature branch.

## 5. Assign work — AUTOMATIC

```
set WORKER_AUTO_DISPATCH=1                         # enable (Windows); export on *nix

python scripts/pf.py dispatch status
python scripts/pf.py dispatch tick                 # one pass (--force runs even if flag is off)
```
`dispatcher.tick()` (`core/dispatcher.py`): for each **ONLINE/IDLE** registered worker, assign the next
**eligible** item via `work_pull.pull`. It **assigns but does not execute**.
API: `GET /engineering/dispatch/status`, `POST /engineering/dispatch/tick` (operator).

A dispatch **loop** (run every `WORKER_DISPATCH_POLL_SECONDS`) is what makes it continuous — PF does not
spawn sessions; a worker must already be running.

## 6. Eligibility (why an item is or isn't assignable)

An item is **eligible** only if **all** hold (`core/scheduler.py:eligible`):
- status is open (`new`/`accepted`/`queued`/`scheduled`),
- **analysis is `COMPLETE`** (i.e. **groomed** — un-groomed items are NOT eligible),
- dependencies met (unknown refs block, fail-closed),
- readiness not false, not already leased, no path contention, capability matches the worker.

> **Groom the backlog first** or `/pf work` finds nothing. Deterministic grooming runs on create;
> deeper AI grooming is explicit (`/pf backlog groom <id>`).

## 7. Lease & recovery

- A claim attaches a **lease** (`PF_LEASE_SECONDS`). Two sessions can't get the same item.
- Heartbeat: `renew_lease` (adapter `heartbeat`).
- Expired leases → `job_manager.recover_expired` applies `PF_LEASE_RECOVERY` (default **REQUIRE_REVIEW**, never blind re-run).
- Release: `job_manager.release` returns the item to READY (or terminal).

## 8. End-to-end

**Manual**
```
1. check out PF (your working copy)
2. /pf worker register --runtime opencode
3. /pf work --worker WRK-…
4. execute the package → worktree <repo>-worktrees/<slug>/
5. lease renew/release; on completion the item closes
```

**Automatic**
```
1. /pf worker register --runtime opencode
2. set WORKER_AUTO_DISPATCH=1
3. dispatch loop: python scripts/pf.py dispatch tick   (every WORKER_DISPATCH_POLL_SECONDS)
4. workers receive assignments; workers execute
```

## 9. API reference (operator unless noted)

| Method | Route |
|---|---|
| POST | `/api/v1/engineering/workers/register` |
| GET | `/api/v1/engineering/workers` · `/workers/{id}` · `/adapters` |
| POST | `/api/v1/engineering/workers/{id}/heartbeat` · `/unregister` · `/assign` · `/report` |
| POST | `/api/v1/engineering/work` · `/work/{item_id}/start` |
| GET | `/api/v1/engineering/schedule` · `/schedule/status` · `/schedule/eligible` · `/schedule/next` |
| POST | `/api/v1/engineering/schedule/claim` · `/schedule/lease/{item_id}/renew` · `/schedule/lease/{item_id}/release` · `/schedule/recover` |
| GET/POST | `/api/v1/engineering/dispatch/status` · `/dispatch/tick` |

## 10. Troubleshooting

| Symptom | Cause |
|---|---|
| `worker integration disabled` | `WORKER_INTEGRATION_ENABLED=0` |
| `no eligible item` | backlog not groomed / deps unmet / all leased / capability mismatch |
| dispatch does nothing | `WORKER_AUTO_DISPATCH=0` (use `dispatch tick --force`) or no ONLINE/IDLE workers |
| `/pf work` assigned but nothing ran | pull ≠ execute; call `work_pull.start` / adapter `start` |
| two sessions got same item | should not happen — lease + atomic claim prevent it |

## 11. Non-goals

- PF's own agents are **not** routed through the worker scheduler (native path).
- The layer is **removable** — core imports none of it; disabling it leaves PF unaffected.
