# Shared-Path Reservation & Common-Code Detection — Design

**Concern:** parallel workers colliding on shared/common files (tracked as `BI-PF-0357`).
**Status:** Design (spec now; implement in **ENG-8**). Depends on: ENG-1 (task contract), ENG-2 (scheduler),
ENG-3 (vcs/worktree), ENG-4 (worker), ENG-5 (PR/evidence).
**Authority:** updated plan §14 (scheduler: module ownership, shared-core changes, file-overlap), §15 (worktree
isolation), §26/§35 (concurrency/failure rules).

## Problem / scenarios

1. **One worker** needs a shared-code change → no contention; it owns its worktree/branch. Merge via the gate.
2. **Two workers** need the *same* common file → naive parallel editing produces a merge conflict.
3. Worker A needs a common change that worker B is **actively changing but has not committed** → invisible to git;
   A can build on a version that will change.
4. **Rebase** ordering when shared changes land sequentially.

## Designed answer (principle)

> Serialize on shared/common paths; stay parallel on disjoint work. Prefer *preventing* conflicts over
> *resolving* them.

### 1. Common/shared detection (both signals)
- **Allowlist (explicit, config)** — `config/shared-paths.json` (new, registered): lists shared **components**
  (e.g. `core`, `api`, `config`) and **path globs** (e.g. `core/**`, `config/*.json`, lockfiles). A task touching
  any is **high integration risk**.
- **Git-hotspot heuristic (derived, advisory)** — files with the highest change frequency / number of authors
  over recent history are flagged as *likely* shared. Produced by a read-only analyzer (`scripts/dev/shared_hotspots.py`,
  later) from `git log`; advisory only (never blocks by itself).

A task's **declared** `affected_files` / `allowed_paths` / `affected_components` (ENG-1) are the primary signal;
the two above refine "is this *common*".

### 2. Reservation (runtime advisory lock)
- New store `reservations.json` (owner `core/reservations.py`, registered, single writer, scope `global`):
  ```
  {id, resource, kind: file|dir|glob, holder_task, holder_worker, run_id, acquired_at, ttl_s, state: held|released}
  ```
- **Acquire** before editing a shared/reserved path/component; **release** on merge (or TTL expiry).
- **Advisory + TTL** (like `lock_manager`) → a dead worker cannot deadlock the queue; stale holds expire.
- **Granularity:** default **directory/module** (safer, less parallelism); file-level opt-in.

### 3. Scheduler integration (ENG-2 `plan()`)
- Before assigning, a task is **deferred** if any of its paths/components is (a) reserved by another *live* holder
  or (b) overlaps an already-assigned task (existing ENG-2 behavior), or (c) is shared and another shared-path task
  is in flight. Deferral reason is explicit (`"reserved by <task>"` / `"shared path overlap"`).
- Shared changes that are **prerequisites** are ordered first (dependency: `blocked_by` the shared task).

### 4. Worker integration (ENG-4)
- The worker **acquires** reservations for its declared paths before editing; on completion it **commits** and
  **releases** on merge. If acquire fails → the task waits (`BLOCKED: reserved`) rather than editing.
- **WIP:** on a long hold (or before a rebase), the worker creates a `wip_snapshot` **commit on its own branch**
  (`VCSManager.wip_snapshot`, ENG-3) so work is recoverable — WIP is **never merged unvalidated**.

### 5. Integration & rebase (ENG-8)
- One **integration queue**: after a shared change merges to `develop`, each waiting worker **rebases** its branch
  on the new `develop` (isolated worktree), then runs FEATURE_PR validation.
- **Conflict** (`vcs.has_conflicts()` / rebase failure) → worker result `CONFLICT` → task `BLOCKED`/`NEEDS_REVIEW`
  (human owns the semantic resolution). **Never force-push.**

## API (proposed)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/reservations?resource&state` | current holds |
| POST | `/api/v1/reservations` | acquire (operator/worker) |
| POST | `/api/v1/reservations/{id}/release` | release |
| GET | `/api/v1/shared-paths` | the allowlist + detected hotspots |

## 360° dependency check

- One new store (`reservations.json`) + one config (`shared-paths.json`), both registered, single writers.
- Reuses `lock_manager` patterns (TTL/atomic), `core.vcs` (worktree/rebase/conflict), `core.scheduler`
  (deferral), `core.worker` (acquire/release). No duplicate lock/queue engine.
- Advisory by design → cannot deadlock; fail-closed only where a shared write would otherwise be unsafe.

## Status / phased delivery

| Piece | Where |
|---|---|
| allowlist config + reservation store + scheduler deferral + worker acquire/release | **ENG-8** |
| git-hotspot analyzer (advisory) | ENG-8 follow-up |
| integration queue + rebase sequencing + conflict escalation | ENG-8 |

**Recorded as** `BI-PF-0357`.
