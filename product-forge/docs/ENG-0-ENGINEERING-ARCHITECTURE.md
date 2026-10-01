# ENG-0 — Engineering Architecture

**Phase:** ENG-0 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md` (§12)
**Status:** Implemented — gate PASS
**Depends on:** API-0/0.1 contract, API-1 foundation, API-2 core APIs, API-3 engineering/validation APIs

## What this phase builds

ENG-0 *defines the engineering architecture over the API-1..API-3 contracts* — as an executable artifact, not
prose. The ordered requirement → deploy flow is captured in one canonical descriptor, each step mapped to its
**canonical owner file** and the **`/api/v1` route** that exposes it, with an explicit status
(`exists` | `partial` | `planned`).

```
config/engineering-flow.json              # architecture descriptor (data only; no engine)
core/engineering_flow.py                  # single reader/validator (load/stage/coverage/validate)
api/routers/engineering.py                # GET /api/v1/engineering[/stages|/coverage]
scripts/dev/engineering_flow_check.py     # gate: owners exist AND routes are wired (in precheck)
test-framework/tests/pipeline/test_api_engineering.py   # +2 architecture tests
```

The descriptor is the reference the later phases (ENG-1..ENG-10, REL-0) build against: each phase flips its
step from `planned` → `partial`/`exists` and points at the real owner + route. An architecture that names a
non-existent owner or route **cannot pass** the gate.

## The flow (23 steps)

| # | Step | Phase | Canonical owner | API route | Status |
|---|---|---|---|---|---|
| 1 | Product Requirement | API-1 | `core/intake.py` | `POST /api/v1/intake` | exists |
| 2 | Product Plan | runtime | `core/product_plan.py` | `GET /api/v1/projects` | exists |
| 3 | Architecture | runtime | `core/orchestrator/stage_runner.py` | `GET /api/v1/pipeline` | exists |
| 4 | Epic | runtime | `core/backlog.py` | `GET /api/v1/backlog` | exists |
| 5 | Feature | runtime | `core/product_plan.py` | `GET /api/v1/backlog` | exists |
| 6 | Task | runtime | `core/backlog.py` | `GET /api/v1/tasks` | exists |
| 7 | Task Contract | ENG-1 | `core/task_contract.py` | `GET /api/v1/engineering/tasks` | planned |
| 8 | Scheduler | ENG-2 | `core/scheduler.py` | `GET /api/v1/engineering/schedule` | planned |
| 9 | Worker Queue | runtime | `core/job_manager.py` | `GET /api/v1/workers/queue` | exists |
| 10 | Worker Runtime | ENG-4 | `core/orchestrator/agent_runner.py` | — | partial |
| 11 | Worktree / Branch | ENG-3 | `core/vcs.py` | `GET /api/v1/vcs` | partial |
| 12 | Implementation | runtime | `core/pipeline_executor.py` | `GET /api/v1/runs` | exists |
| 13 | Tests | runtime | `core/test_framework_integration.py` | `GET /api/v1/tests/matrix` | exists |
| 14 | Commit | runtime | `core/vcs.py` | `GET /api/v1/vcs/commits` | exists |
| 15 | Pull Request | ENG-5 | `core/vcs.py` | — | planned |
| 16 | CI | ENG-5 | — | — | planned |
| 17 | FEATURE_PR | ENG-7 | — | — | planned |
| 18 | Review / Gates | runtime | `core/pr_gate.py` | `GET /api/v1/gates/pr` | exists |
| 19 | Merge | ENG-3 | `core/vcs.py` | — | partial |
| 20 | Integration | ENG-8 | — | — | planned |
| 21 | Dogfood | ENG-9 | — | — | planned |
| 22 | Release | ENG-10 | — | — | planned |
| 23 | Package / Entitle / Deploy | REL-0 | — | — | planned |

**Status:** 11 exists · 3 partial · 9 planned.

## Layer model (authority order)

```
Clients (OpenCode · MCP · CLI · future Dashboard)      adapters only — never own canonical state
        │  (control plane)
Canonical API  /api/v1   ── API-1 foundation · API-2 core · API-3 engineering
        │  (delegates to owners)
Owners / engines  core/*  ── one writer per concern (config/store-registry.json)
        │  (state)
Stores  data/, products/<project>/, config/*.json
```

## Invariants (must hold)

1. One owner per concern; no duplicate engines/stores (authority: `config/store-registry.json`).
2. Every step maps to a canonical owner file and, where an API exists, a canonical `/api/v1` route.
3. Clients are adapters over the API surface; none owns canonical state.
4. Exactly one git owner (`core/vcs.py`), one pipeline executor, one validation decision (`core/close_loop`).

## Forbidden (from plan §41 — recorded in the descriptor)

`second pipeline executor` · `second validation engine` · `second backlog` · `second defect store` ·
`second artifact store` · `second event source of truth` · `third git manager` · OpenCode-dependent
architecture · Dashboard-dependent architecture · worker-specific state as canonical state · direct
client-to-store mutation.

## Gap analysis (what the later phases add)

| Planned/partial step | Phase | Missing capability |
|---|---|---|
| Task Contract | ENG-1 | structured task contract + store (`core/task_contract.py`) |
| Scheduler | ENG-2 | dependency graph, capability matching, elastic scheduling |
| Worktree / Merge | ENG-3 | consolidate `git_manager.py` (PF-050) into `core/vcs.py`; worktree isolation |
| Worker Runtime | ENG-4 | normalized worker result + OpenCode/CLI adapter |
| Pull Request / CI | ENG-5 | GitHub PR + CI orchestration, exact-commit evidence |
| FEATURE_PR / Integration / Dogfood / Release | ENG-6..ENG-10 | the single Validation Engine + E2E stages |
| Package / Entitle / Deploy | REL-0 | packaging, entitlement, deployment validation |

## 360° dependency check

- New descriptor is a **config** store, registered in `config/store-registry.json` (owner
  `core/engineering_flow.py`); no runtime state, no engine.
- `core/engineering_flow.py` is read-only (never writes the store); it is wired via `api/routers/engineering.py`
  and `scripts/dev/engineering_flow_check.py`, so invocation/store audits stay green.
- No edits to `dashboard/` (frozen); no new pipeline/validation/backlog/artifact/event/defect/git engines.
- Reads are authenticated; the descriptor is a read-only surface.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python scripts/dev/engineering_flow_check.py                      # engineering-flow: OK (23 steps, 9 planned)
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS (now includes engineering-flow)
```

## Gate (plan §12)

| Criterion | Result |
|---|---|
| Engineering architecture defined over the API contracts | ✅ `config/engineering-flow.json` + this doc |
| Every step has a canonical owner | ✅ non-planned owners exist on disk (gate) |
| Every exposed step has a canonical API route | ✅ routes verified against the live OpenAPI (gate) |
| No duplicate engines/stores; boundaries recorded | ✅ invariants + forbidden list; one owner per concern |
| Executable / verifiable (not prose) | ✅ reader + API + precheck gate + tests |

**ENG-0 GATE: PASS.** Next: **ENG-1 — Engineering Task Contract** (`core/task_contract.py`).
