# ENG-0 — Engineering Architecture

**Phase:** ENG-0 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§12)
**Status:** Implemented — gate PASS (superseded by the entry-path retrofit §2A)
**Depends on:** API-1..API-3

## What this phase builds

ENG-0 defines the engineering architecture over the API-1..API-3 contracts as an **executable descriptor**
(`config/engineering-flow.json`), read by `core/engineering_flow.py`, served by
`GET /api/v1/engineering[/stages|/coverage]`, and gated by `scripts/dev/engineering_flow_check.py` (in precheck).

**Retrofit (§2A): two INDEPENDENT entry paths.** The descriptor was corrected so the engineering flow is **not**
rooted at Intake:

```
config/engineering-flow.json          # descriptor (data only; no engine)
  external_ingestion : [...]          # SEPARATE path; NO edge into engineering
  flow               : [...]          # engineering execution; starts at the direct entry
core/engineering_flow.py              # reader/validator (flow/external_ingestion/entries/coverage/validate)
```

## Path 1 — External ingestion (already implemented; independent)

```
external client → Intake API → requirement/change normalization → backlog / change (work item)
```

| Step | Owner | API | Status |
|---|---|---|---|
| Intake API | `core/intake.py` | `POST /api/v1/intake` | exists |
| Requirement / change normalization | `core/intake_adapters.py` | — | exists |
| Backlog / change (work item) | `core/backlog.py` | `GET /api/v1/backlog` | exists |
| Product Plan | `core/product_plan.py` | `GET /api/v1/projects` | exists |
| Architecture | `core/orchestrator/stage_runner.py` | `GET /api/v1/pipeline` | exists |
| Epic / Feature decomposition | `core/product_plan.py` | `GET /api/v1/backlog` | exists |

**This path has no dependency edge into the engineering flow.** Intake *may* produce a backlog work item that a
task can reference (`epic_id`/`feature_id`), but it is **never a prerequisite** for engineering work. Intake only
**ingests and enqueues** — it must not instantiate a pipeline executor (see `core/intent_router.py`).

## Path 2 — Direct engineering (canonical; starts at the Task/Work API)

```
OpenCode / CLI / Coding Agent / Human → Task/Work API → resolve/create task → run → scheduler → worker
```

| # | Step | Phase | Owner | API | Status |
|---|---|---|---|---|---|
| 1 | **Task Contract (direct engineering entry)** | ENG-1 | `core/task_contract.py` | `GET/POST /api/v1/engineering/tasks` | exists |
| 2 | Scheduler | ENG-2 | `core/scheduler.py` | `GET /api/v1/engineering/schedule` | exists |
| 3 | Worker Queue | runtime | `core/job_manager.py` | `GET /api/v1/workers/queue` | exists |
| 4 | Worker Runtime | ENG-4 | `core/worker.py` | `GET /api/v1/engineering/tasks` | exists |
| 5 | Worktree / Branch | ENG-3 | `core/vcs.py` | `GET /api/v1/vcs` | exists |
| 6 | Implementation | runtime | `core/pipeline_executor.py` | `GET /api/v1/runs` | exists |
| 7 | Tests | runtime | `core/test_framework_integration.py` | `GET /api/v1/tests/matrix` | exists |
| 8 | Commit | runtime | `core/vcs.py` | `GET /api/v1/vcs/commits` | exists |
| 9 | Pull Request | ENG-5 | `core/vcs.py` | — | planned |
| 10 | CI | ENG-5 | — | — | planned |
| 11 | FEATURE_PR | ENG-7 | — | — | planned |
| 12 | Review / Gates | runtime | `core/pr_gate.py` | `GET /api/v1/gates/pr` | exists |
| 13 | Merge | ENG-3 | `core/vcs.py` | — | partial |
| 14 | Integration | ENG-8 | — | — | planned |
| 15 | Dogfood | ENG-9 | — | — | planned |
| 16 | Release | ENG-10 | — | — | planned |
| 17 | Package / Entitle / Deploy | REL-0 | — | — | planned |

**Engineering status:** 9 exists · 1 partial · 7 planned (17 steps). The direct entry is `task_contract`.

## Invariants (must hold)

1. **Two independent entry paths** — external ingestion vs direct engineering; no shared prerequisite.
2. **Intake is not a prerequisite for engineering work** — no step in `flow` is owned by `core/intake.py`, and
   `external_ingestion` has no dependency edge into `flow`.
3. The direct engineering entry (Task/Work API) is reachable **without creating a conversation or intake record**.
4. One owner per concern; no duplicate engines/stores (`config/store-registry.json`).
5. Exactly one git owner (`core/vcs.py`), one pipeline executor, one validation decision (`core/close_loop`).

## Forbidden (recorded in the descriptor)

`making Intake a prerequisite for engineering tasks/workers` · `manufacturing a conversation record to start
engineering work` · second pipeline executor · second validation engine · second backlog · second defect store ·
second artifact store · second event source · third git manager · OpenCode-dependent architecture ·
Dashboard-dependent architecture · worker-specific state as canonical state · direct client-to-store mutation.

## Gap analysis (what the later phases add)

| Planned/partial step | Phase | Missing capability |
|---|---|---|
| Pull Request / CI | ENG-5 | push, PR, exact-commit evidence, integration queue |
| Merge | ENG-3/5 | controlled merge sequencing |
| FEATURE_PR / Integration / Dogfood / Release | ENG-6..ENG-10 | the single Validation Engine + E2E stages |
| Package / Entitle / Deploy | REL-0 | packaging, entitlement, deployment validation |

## 360° dependency check

- Descriptor is a registered **config** store (owner `core/engineering_flow.py`); no runtime state, no engine.
- `core/engineering_flow.py` is read-only; wired via `api/routers/engineering.py` and the precheck gate.
- No edits to `dashboard/` (frozen); no new engines/stores.
- Gate asserts: engineering flow starts at `task_contract`, **no intake-owned engineering step**, and every
  non-planned step's route is wired in the live OpenAPI (for **both** paths).

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/engineering_flow_check.py                      # OK (17 engineering, 6 ingestion, 7 planned)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §12 / §2A)

| Criterion | Result |
|---|---|
| Architecture defined over the API contracts | ✅ descriptor + this doc |
| Two independent entry paths | ✅ `external_ingestion` (no edge) + `flow` (direct entry `task_contract`) |
| Intake is not an engineering prerequisite | ✅ gate: no intake-owned step; no conversation required |
| No duplicate engines/stores; boundaries recorded | ✅ invariants + forbidden |
| Executable / verifiable | ✅ reader + API + precheck gate + tests |

**ENG-0 GATE: PASS.** Next: continue the current phase (**ENG-5 — GitHub/PR/CI**), per the resume plan.
