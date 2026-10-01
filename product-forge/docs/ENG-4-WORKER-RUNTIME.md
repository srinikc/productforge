# ENG-4 — Worker Runtime & Adapters

**Phase:** ENG-4 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md` (§16)
**Status:** Implemented (runtime + provider abstraction) — gate PASS
**Depends on:** ENG-1 (task contract), ENG-2 (scheduler), ENG-3 (worktree isolation)

## What this phase builds

A worker executes **one scheduled task contract** inside an isolated worktree and returns a **PF-owned,
normalized `WorkerResult`**. The provider is an *adapter* — OpenCode is one, never a dependency.

```
core/worker.py                        # runtime + providers + normalized WorkerResult (single writer)
  WorkerProvider  (base)
    +-- NoopProvider      (NEEDS_REVIEW; safe default)
    +-- HumanProvider     (hand to a human)
    +-- CommandProvider   (run a configured command in the worktree)
    +-- OpenCodeProvider  (OPTIONAL session adapter; BLOCKED if absent)
  run_task(task, project_dir, provider, ...) -> WorkerResult
  available_providers() / record_result() / list_results() / contract_status_for()
config/engineering-workers.json       # (declared pool, ENG-2)
api/routers/engineering.py            # GET /worker-providers, POST /tasks/{id}/run, GET /tasks/{id}/results
scripts/dev/worker_check.py           # gate (in precheck)
config/engineering-flow.json          # worker_runtime step: partial -> exists
```

## Lifecycle (plan §16)

```
ASSIGNED → INITIALIZING → WORKING → TESTING → PR_READY → (INTEGRATING → DONE)
failures: BLOCKED | FAILED | NEEDS_REVIEW | CONFLICT
```
`WorkerResult.lifecycle` records the states actually traversed. Result status maps to the task-contract status
via `contract_status_for()` (`PR_READY/NEEDS_REVIEW → review`, `FAILED → failed`, `BLOCKED → blocked`).

## Normalized WorkerResult (PF-owned)

`task_id, worker_id, provider, run_id, worktree_id, branch, base_commit, final_commit, status, files_changed,
tests, artifacts, evidence, issues, warnings, error` (+ `lifecycle`, `created_at`).

The runtime creates the worktree via **ENG-3** (`feature/<area>/<task-id>`), runs the provider, optionally
commits, and derives `files_changed` from `git diff base..HEAD` ∪ `git status`. The provider's raw output is
kept under `evidence.provider_output`; **PF records the normalized result**, not the provider.

## Providers (adapters, never dependencies)

| Provider | Available when | Effect |
|---|---|---|
| `noop` | always | marks the task `NEEDS_REVIEW` (safe default; no code) |
| `human` | always | queues for a human operator (`NEEDS_REVIEW`) |
| `command` | always | runs a configured command in the worktree; `pr_ready`/`failed` |
| `opencode` | `opencode` on PATH | runs `opencode run <objective>`; otherwise `BLOCKED` |

`GET /api/v1/engineering/worker-providers` reports each provider and whether it is available — so the system
degrades gracefully and **never requires OpenCode**.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/engineering/worker-providers` | provider registry + availability |
| POST | `/api/v1/engineering/tasks/{task_id}/run` | claim + execute (operator); body `provider/command/commit/base/timeout` |
| GET | `/api/v1/engineering/tasks/{task_id}/results` | prior normalized results for the task |

The store `worker-results.json` (owner `core/worker.py`, kind `evidence`) is registered; task status is updated
only through `core.task_contract` (the task store's single writer).

## 360° dependency check

- One new store, registered, single writer (`core/worker.py`). No engine duplication; no second queue.
- `core/worker.py` is reachable from `scripts/dev/worker_check.py` (precheck) → invocation-audit stays green.
- `OpenCodeProvider.available()` is a runtime probe; absence ⇒ `BLOCKED`, never a crash. OpenCode remains a
  client only (plan §41: no OpenCode-dependent architecture).
- No edits to `dashboard/` (frozen).
- The ENG-0 architecture gate now verifies the `worker_runtime` step's owner file exists and its route is wired.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python scripts/dev/engineering_flow_check.py                      # engineering-flow: OK (23 steps, 7 planned)
python scripts/dev/worker_check.py                                # worker: OK (providers, isolated run, PR_READY/NEEDS_REVIEW/FAILED)
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §16)

| Criterion | Result |
|---|---|
| Worker abstraction (providers) | ✅ Noop/Human/Command/OpenCode adapters |
| Lifecycle states | ✅ recorded on every result |
| PF-owned normalized WorkerResult | ✅ all §16 fields |
| Runs in engine/isolated worktree | ✅ via ENG-3 (one git owner) |
| OpenCode is an adapter, not a dependency | ✅ optional; degrades to BLOCKED |
| API-first + wired + exercised | ✅ endpoints + gate + tests |
| ENG-0 flow updated | ✅ `worker_runtime`: partial → exists |

**ENG-4 GATE: PASS.** Next: **ENG-5 — GitHub / PR / CI Orchestration** (push, PR, exact-commit evidence,
integration queue), which also unblocks API-5.
