# ENG-1 — Engineering Task Contract

**Phase:** ENG-1 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md` (§13)
**Status:** Implemented — gate PASS
**Depends on:** ENG-0 (`docs/ENG-0-ENGINEERING-ARCHITECTURE.md`), API-1..API-3

> **Entry path (§2A):** the task contract is the **direct engineering entry** (Task/Work API). It is created
> without a conversation/intake record. Intake (external ingestion) is an *optional* producer of the backlog work
> items a contract may reference — never a prerequisite.

## What this phase builds

A task is **not merely a backlog title** — it is a structured contract **any compatible worker can execute**.
ENG-1 adds the canonical task-contract model, its single-writer store, the API surface, and a schema gate, then
flips the ENG-0 flow step `task_contract` from `planned` → `exists`.

```
core/task_contract.py                  # model + single writer of the contract store + validator
  FILENAME = task-contracts.json       #   product-forge/tasks/  |  products/<project>/tasks/
  RISKS / STATUSES / PRIORITIES        #   enums
  validate() / normalize() / create() / get() / list_tasks() / set_status()
api/routers/engineering.py             # GET/POST /api/v1/engineering/tasks[...|/{id}|/{id}/status]
scripts/dev/task_contract_check.py     # schema gate (in precheck)
config/engineering-flow.json           # task_contract step: planned -> exists
```

## The contract (29 fields, plan §13)

| Group | Fields |
|---|---|
| Identity | `task_id` `project_id` `epic_id` `feature_id` `parent_task_id` |
| Intent | `title` `description` `objective` `acceptance_criteria` |
| Graph | `dependencies` `blocked_by` |
| Scope | `affected_components` `affected_files` `allowed_paths` `restricted_paths` |
| Worker fit | `required_capabilities` `required_worker_type` `owner` |
| Policy | `risk` `priority` `validation_profile` `branch_policy` `repair_policy` |
| Requirements | `test_requirements` `security_requirements` `performance_requirements` `expected_artifacts` |
| Lifecycle | `status` `run_id` (+ `created_at`/`updated_at`) |

**Required to create:** `title`, `objective`, and a non-empty `acceptance_criteria` list.
**Validation:** `risk ∈ {low,medium,high,critical}`, `priority ∈ {P0..P3}`, `status ∈` lifecycle below; every
list field must be a list. Invalid ⇒ `VALIDATION_FAILED` (fail-closed).
**Lifecycle:** `draft → ready → assigned → in_progress → (blocked|review) → done`; plus `cancelled` / `failed`.

## Reuse (no duplicate work store)

- Backlog items remain the **work SSOT**; a contract *references* them via `epic_id`/`feature_id` (and is
  identified by `TC-<TAG>-<nnn>`). The backlog is never copied or shadowed.
- The contract is the **execution** unit the scheduler/worker (ENG-2/ENG-4) will consume; it holds no state
  owned by another module.
- The store is registered once, with a single writer: `task-contracts.json` → owner `core/task_contract.py`
  (kind `work-items`, scope `project|product_forge`, visibility `scope-local`).

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/engineering/tasks?scope&project&status&limit&cursor` | paginated list |
| GET | `/api/v1/engineering/tasks/{task_id}?scope&project` | single contract |
| POST | `/api/v1/engineering/tasks` | create (operator); body = contract (+`scope`/`project`) |
| POST | `/api/v1/engineering/tasks/{task_id}/status` | set lifecycle status (operator) |

## 360° dependency check

- New module `core/task_contract.py` is reachable from the precheck gate (`task_contract_check.py`), so the
  invocation-audit stays green (a core module reachable only via `api/` would be flagged unwired).
- No edits to `dashboard/` (frozen). One new store, registered; no duplicate engine/store.
- Reads are authenticated; mutations are operator-gated.
- The ENG-0 architecture gate now verifies the `task_contract` step's owner file exists and its route is wired.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python scripts/dev/engineering_flow_check.py                      # engineering-flow: OK (23 steps, 8 planned)
python scripts/dev/task_contract_check.py                         # task-contract: OK (29 contract fields)
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §13)

| Criterion | Result |
|---|---|
| Task contract defined (all §13 fields) | ✅ 29 fields, normalized |
| A task is more than a title | ✅ objective + acceptance criteria required |
| Executable by any compatible worker | ✅ `required_capabilities` / `required_worker_type` / paths / validation profile |
| Canonical owner + single writer | ✅ `core/task_contract.py` (registered store) |
| Exposed via API-first surface | ✅ `/api/v1/engineering/tasks` |
| Wired + exercised | ✅ precheck schema gate + API roundtrip tests |
| ENG-0 flow updated | ✅ `task_contract`: planned → exists |

**ENG-1 GATE: PASS.** Next: **ENG-2 — Work Planner and Parallel Scheduler**.
