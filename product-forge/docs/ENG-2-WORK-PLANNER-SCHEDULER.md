# ENG-2 — Work Planner & Parallel Scheduler

**Phase:** ENG-2 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md` (§14)
**Status:** Implemented (planning core) — gate PASS
**Depends on:** ENG-1 (`docs/ENG-1-TASK-CONTRACT.md`), ENG-0 (`docs/ENG-0-ENGINEERING-ARCHITECTURE.md`)

> **Entry path (§2A):** the scheduler consumes task contracts from the **direct engineering entry** (Task/Work
> API); tasks are scheduled regardless of origin. Intake is not required and does not gate scheduling.

## What this phase builds

The planner/scheduler becomes a first-class Product Forge capability. ENG-2 delivers the **deterministic
planning core** over ENG-1 task contracts: task discovery, dependency graph + cycle detection, prioritization,
capability matching, file-overlap detection, and **elastic** assignment of ready tasks to declared worker
slots (`K <= N`).

```
core/scheduler.py                     # pure planner (no execution, no store writes)
  workers() / worker_slots()          #   declared pool -> concrete slots
  dependency_graph() / find_cycles()  #   graph + cycle detection
  capability_match()                  #   required_capabilities / required_worker_type
  path_overlap()                      #   file / dir-prefix / glob overlap
  plan(scope, project)                #   elastic wave assignment
  report(scope, project)              #   status roll-up
config/engineering-workers.json       # declared worker pool (types + capabilities + slots)  [registered]
api/routers/engineering.py            # GET /api/v1/engineering/workers | /schedule
scripts/dev/scheduler_check.py        # deterministic gate (in precheck)
config/engineering-flow.json          # scheduler step: planned -> exists
```

## Responsibilities — delivered vs deferred

| Plan §14 responsibility | ENG-2 |
|---|---|
| task discovery | ✅ from the contract store |
| dependency graph / cycle detection | ✅ `dependency_graph` + `find_cycles` |
| prioritization | ✅ P0..P3, then risk, then age |
| capability matching | ✅ capabilities + `required_worker_type` (wildcard supported) |
| file-overlap detection | ✅ path/dir/glob overlap (excludes concurrent collisions) |
| elastic model `K <= N` | ✅ slots from the declared pool; `K <= capacity` |
| worker registration / availability | ✅ declared pool config (+ enabled flag) |
| reporting | ✅ `report()` + plan `counts` |
| assignment *persistence* | ⏳ deferred — plan is a derivation; persisting "assigned" flips contract status (ENG-4) |
| worktree / branch allocation | ⏳ ENG-3 (git consolidation + worktrees) |
| rebase / PR sequencing / integration queue | ⏳ ENG-5 |
| failure / retry / reassignment | ⏳ ENG-4 |

## How the plan is computed

1. **Candidates** = contracts whose `status` is schedulable (`ready`) and that are not in a dependency cycle.
2. **Sort** by priority (P0<P1<P2<P3), then risk (critical>high>medium>low), then age.
3. For each candidate, in order:
   - **Blocked?** if any `dependencies`/`blocked_by` is not terminal (`done`/`cancelled`) ⇒ `blocked`
     (unknown refs block — fail-closed).
   - **Capability:** pick the first free slot matching `required_capabilities`/`required_worker_type`.
     None ⇒ `deferred: no matching worker`.
   - **File overlap:** if its paths overlap any task already assigned in this wave ⇒ `deferred: file overlap with <id>`.
   - Otherwise **assign** it to that slot.
4. `K = assigned`, bounded by `capacity = Σ slots.max_concurrency` (never a fixed worker count).

## Worker model (adapters, not dependencies)

`config/engineering-workers.json` declares worker **types + capabilities + slot count** only. Runtimes
(local agent runner, CLI, **OpenCode session**, human) are *adapters* behind the worker contract — never named
as required. A `human` slot with `["*"]` matches anything. Disabled types are excluded from the pool.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/engineering/workers` | declared pool + expanded slots |
| GET | `/api/v1/engineering/schedule?scope&project` | elastic plan (assignments/deferred/blocked/cycles/counts) |

## 360° dependency check

- `core/scheduler.py` is pure (no writes): it reads the task-contract store (owner `core/task_contract.py`)
  and the worker-pool config (registered, owner this module). **No second queue, no new state.**
- Reachable from `scripts/dev/scheduler_check.py` (precheck), so the invocation-audit stays green.
- No edits to `dashboard/` (frozen); no duplicate engines/stores.
- The ENG-0 architecture gate now verifies the `scheduler` step's owner file exists and its route is wired.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python scripts/dev/engineering_flow_check.py                      # engineering-flow: OK (23 steps, 7 planned)
python scripts/dev/scheduler_check.py                             # scheduler: OK (deps, cycles, capability, overlap, K<=N)
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §14)

| Criterion | Result |
|---|---|
| Dependency graph works | ✅ + cycle detection |
| Capability matching works | ✅ incl. wildcard + worker type |
| File-overlap detection works | ✅ concurrent collisions excluded |
| Elastic worker model works | ✅ `K <= N` (pool slots), never fixed count |
| Prioritization works | ✅ priority → risk → age |
| Read-only (no shadow queue/state) | ✅ pure planner |
| Exposed API-first + wired + exercised | ✅ `/api/v1/engineering/schedule` + gate + tests |
| ENG-0 flow updated | ✅ `scheduler`: planned → exists |

**ENG-2 GATE: PASS.** Next: **ENG-3 — Git / Worktree / Branch Orchestration** (consolidate `git_manager.py`/PF-050 into `core/vcs.py`, add per-task worktree isolation).
