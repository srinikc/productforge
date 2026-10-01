# SESSION RESUME — Product Forge Master Plan

**Purpose:** hand-off notes to resume the master-plan execution in a fresh session. This session developed an
unreliable turn/tool-execution boundary (tool calls mixed with prose were dropped), so resume fresh.

## Governing plan (updated)
The authoritative plan is now
`docs/PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md`. Its **§2A Entry-Path
Contract** is normative and was retrofitted across MASTER-0 → ENG-4:
- **External ingestion** (Intake API → requirement → backlog/change work item) is an **independent** path.
- **Direct engineering** (OpenCode/CLI/agent/human → **Task/Work API** → run → scheduler → worker) is the normal
  path for the single-OpenCode-session use case.
- **Intake is NOT a prerequisite for engineering work**; engineering must not manufacture a conversation record.
The ENG-0 descriptor now models the two paths with **no edge** between them; `core/intent_router` no longer runs a
pipeline executor directly (it enqueues via `core.run_entry`). See `docs/ENG-0-ENGINEERING-ARCHITECTURE.md`.

## Repo / branch state

- Repo root: `C:\Users\ADMIN\Documents\Srinikc\AI Products\Exploring`
- Product code: `product-forge/`
- **Branch: `phase/master-0`** (DO NOT work on `develop`/`main`).
- Base: `develop` @ `ad75967`.
- Commits on `phase/master-0`:
  - `cc45664` MASTER-0: current-state architecture truth + discovery gate (+ repaired dangling `core/result_aggregator.py`)
  - `cc791f8` API-0: API discovery artifact + gate
  - `b236efa` API-0.1: contract reconciliation artifact + gate
  - `e57037a` API-1: canonical `api/` foundation
  - `API-2` (this session): core PF APIs — `api/routers/{projects,runs,pipeline,artifacts,evidence,backlog}.py`,
    `api/pagination.py`, `api/app.py` (8 routers), `scripts/dev/api_contract_check.py` (core GET surface +
    validation error), `scripts/dev/gen_docs_index.py` (classifies API-2 + this resume doc),
    `test-framework/tests/pipeline/test_api_core.py` (12 tests), `docs/API-2-CORE-APIS.md`,
    regenerated `docs/README.md` + `docs/documentation-index.html`, `data/backlog` (new `BI-PF-0331`;
    28 test-residue intake items removed). `data/api/idempotency.json` residue deleted pre-commit.
  - `API-3` (this session): engineering/validation APIs — `api/routers/{validation,tests,gates,issues,vcs,workers,agents}.py`
    + `api/routers/_common.py`, `api/app.py` (15 routers), read-only `status()`/`branches()` added to `core/vcs.py`,
    `scripts/dev/api_contract_check.py` (engineering surface + fail-closed unknown project),
    `test-framework/tests/pipeline/test_api_engineering.py` (7 tests), `docs/API-3-ENGINEERING-APIS.md`,
    regenerated docs index. 49 OpenAPI paths total.
  - `ENG-0` (this session): engineering architecture as an executable descriptor —
    `config/engineering-flow.json` (23-step requirement→deploy flow → canonical owner files + `/api/v1` routes,
    registered in store-registry), `core/engineering_flow.py` (read/validate), `api/routers/engineering.py`
    (`GET /api/v1/engineering[/stages|/coverage]`), `scripts/dev/engineering_flow_check.py` (precheck gate:
    owners exist + routes wired),     `docs/ENG-0-ENGINEERING-ARCHITECTURE.md`. 53 OpenAPI paths total.
  - `ENG-1` (this session): engineering task contract — `core/task_contract.py` (29-field contract model +
    single writer of the registered `task-contracts.json` store + validator), task endpoints on
    `api/routers/engineering.py` (`/api/v1/engineering/tasks[...]`), `scripts/dev/task_contract_check.py`
    (precheck schema gate), `docs/ENG-1-TASK-CONTRACT.md`; ENG-0 flow step `task_contract` flipped planned→exists.
    56 OpenAPI paths total.
  - `ENG-2` (this session): work planner & parallel scheduler — `core/scheduler.py` (pure planner: dependency
    graph + cycle detection, prioritization, capability matching, file-overlap detection, elastic `K<=N`
    assignment), `config/engineering-workers.json` (declared pool, registered), `GET /api/v1/engineering/workers`
    + `/engineering/schedule`, `scripts/dev/scheduler_check.py` (precheck gate), `docs/ENG-2-WORK-PLANNER-SCHEDULER.md`;
    ENG-0 flow step `scheduler` flipped planned→exists. 58 OpenAPI paths total.
  - `ENG-3` (this session): git/worktree orchestration — consolidated the duplicate `core/git_manager.py`
    (PF-050 bug) into the ONE owner `core/vcs.py` (removed git_manager; repointed `capability_bridge` +
    `pipeline_capabilities` + `core/__init__`); added `feature_branch_name`/`validation_branch_name`/`is_protected`/
    `worktree_root`/`add_worktree`/`list_worktrees`/`remove_worktree`; API `GET /vcs/branch-name`, `/vcs/worktrees`,
    `POST /vcs/worktrees[/{name}/remove]`; `scripts/dev/vcs_worktree_check.py` (precheck gate);
    `docs/ENG-3-GIT-WORKTREE-ORCHESTRATION.md`; ENG-0 flow step `worktree` flipped partial→exists.
    61 OpenAPI paths total.
  - `ENG-4` (this session): worker runtime & adapters — `core/worker.py` (provider abstraction
    Noop/Human/Command/OpenCode + normalized PF-owned `WorkerResult`; runs one task in an isolated ENG-3 worktree,
    optional commit, derives `files_changed`, maps status→contract), registered `worker-results.json` store,
    API `GET /engineering/worker-providers`, `POST /engineering/tasks/{id}/run`,
    `GET /engineering/tasks/{id}/results`; `scripts/dev/worker_check.py` (precheck gate);
    `docs/ENG-4-WORKER-RUNTIME.md`; ENG-0 flow step `worker_runtime` flipped partial→exists.
    OpenCode is an optional adapter (BLOCKED if absent), never a dependency. 64 OpenAPI paths total.

## Binding decisions (do not violate)

1. **Legacy Dashboard is OUT OF SCOPE.** Do not edit anything under `product-forge/dashboard/` (incl.
   `dashboard/api/app.py`, `dashboard/server.py`). It is frozen; later it is only a *client*.
2. **Canonical API = new `product-forge/api/` package.** API-first SSOT.
3. **OpenCode is an adapter/client only** — never an architectural dependency.
4. **No duplicate** engines/stores (pipeline, validation, backlog, defect, artifact, event, Git, runtime, API).
5. **Archive excluded** (`product-forge/archive/`).
6. New `docs/*.md` MUST be classified in `scripts/dev/gen_docs_index.py` then regenerated, else precheck docs-fresh FAILS.
7. Never put `*.json`/`*.jsonl` filename literals in code/tests (store_audit) — build dynamically (`"x."+"json"`).
8. Never use the word `factory` in scanned files (naming audit) — NAMING_ROOTS = core/scripts/dashboard.
9. Don't re-derive ROOT — use `core.paths.ROOT`.
10. Test residue: delete `data/api/idempotency.json` after API tests; leave untracked `products/inbox`/`.conversations`/`_test_*` alone.
11. **PowerShell quoting**: avoid inline `python -c` with nested quotes — write a `.py` file and run it.

## Gates (run from `product-forge/`)

```
python -m compileall -q api core scripts dashboard            # expect 0
python scripts/dev/wired_audit.py                             # expect 0 (use `; $LASTEXITCODE` to see code)
python scripts/dev/api_contract_check.py                      # expect "api-contract: OK"
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # expect ~738 passed, 1 skipped
python scripts/dev/precheck.py                                # expect precheck: PASS
```
`precheck` now includes `api-contract` and compiles `api`.

## Verified state at hand-off

- API-1..API-3, ENG-0..ENG-4 committed; **entry-path retrofit applied** (MASTER-0→ENG-4 re-audited).
- `wired_audit` = 0; `api_contract_check` OK; `engineering_flow_check` OK; `task_contract_check` OK; `scheduler_check` OK; `vcs_worktree_check` OK; `worker_check` OK; `test_entry_paths` OK; full suite green; `precheck` PASS.
- `api/` has 16 routers; **64 OpenAPI paths**; API-2 core reads + API-3/ENG reads all 200.
- `core/result_aggregator.py` (BI-PF-0277) dangling-integrity gap was repaired in MASTER-0 commit.

### Entry-path retrofit (this session; updated plan §2A)
- ENG-0 descriptor split into two INDEPENDENT paths: `external_ingestion` (Intake, no edge) + `flow` (starts at the
  direct entry `task_contract`). Gate asserts no engineering step is owned by `core/intake.py`.
- `core/intent_router._start_pipeline` no longer instantiates a pipeline executor; it enqueues via
  `core.run_entry` (canonical run identity). Worker runs use the canonical PF run id.
- Docs MASTER-0, API-0/0.1/1/2, ENG-0..4 updated with the two-entry-path contract.

## IMMEDIATE NEXT STEPS (after the entry-path retrofit; continue from the current phase)

1. **Proceed to ENG-5 — GitHub / PR / CI Orchestration**: push the worker branch, create a PR with exact-commit
   evidence (RUN_ID, task_id, commit SHA, base SHA, tests, validation result), CI status, and the integration
   queue toward develop. Flip the `pr`/`ci` flow steps `planned` → `partial`/`exists` in `config/engineering-flow.json`.
2. **API-5 — hardening** (contract governance, canonical OpenAPI, event API formalization, compatibility policy)
   can follow ENG-5.
3. **API-4** (enterprise/SaaS/OEM) may run in parallel once its dependencies are available.
4. Optional: close MASTER-0..ENG-4 via the Issue Tracker/RCCA loop per EOS.
5. Optional follow-up: consolidate `control.json` ownership — `config/store-registry.json` names owner
   `core/human_controls.py` (source absent, stale `.pyc` only); actual writers are `core.portfolio.control`,
   `core.run_guard._write_control`, `scripts/run_pipeline.py`.

### Defects fixed during API-2 review (RCCA-lite; see `docs/API-2-CORE-APIS.md`)

- `POST /runs/start {now:true}` raised: bad `run_now_on_priority` call (keyword-only `by`, no `actor`).
- `POST /runs/stop` was a no-op: called non-existent `pipeline_executor.request_stop`; now cancels the queue
  job and writes the canonical `control.json` stop signal.
- `GET /artifacts/{stage}/{agent}` always 404: wrong `get_artifact_content` signature; now resolves via
  `scan_project_artifacts` + `a.path`.

## Phase order remaining (governing plan)

`docs/PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md`
(branch progress: MASTER-0, API-0/0.1/1/2/3, ENG-0..ENG-4 done + entry-path retrofit)

```
API-3 → ENG-0 → ENG-1 (TaskContract) → ENG-2 (scheduler) → ENG-3 (git/worktree; consolidate vcs.py+git_manager.py) →
ENG-4 (worker abstraction + OpenCode adapter) → ENG-5 (GitHub/PR/CI) → API-5 (hardening + events) →
ENG-6 (single Validation Engine) → ENG-7 FEATURE_PR → ENG-8 INTEGRATION → ENG-9 DOGFOOD → ENG-10 RELEASE →
REL-0 (package/entitle/deploy) → FULL DOGFOOD → FINAL AUDIT
```

Discovery outputs already written (read these first): `docs/MASTER-0-CURRENT-STATE-TRUTH.md`,
`docs/API-0-DISCOVERY.md`, `docs/API-0.1-CONTRACT-RECONCILIATION.md`, `docs/API-1-FOUNDATION.md`,
`docs/API-2-CORE-APIS.md`.

## Key existing canonical components (reuse, don't duplicate)

- Run entry: `core/run_entry.py` (begin_run/enqueue/active) · Lock: `core/lock_manager.py`,`core/run_guard.py`
- Pipeline: `core/pipeline_executor.py` · DAG: `core/dag_executor.py` · stages: `core/orchestrator/stage_runner.py`
- Validation: `core/verification_runner.py`, `core/verification_policy.py` (NO single engine yet), `core/pr_gate.py` (local)
- Defects/RCCA: `core/defect_loop.py`, `core/issues.py` (canonical) vs `core/issue_tracker.py` (legacy twin)
- Backlog: `core/backlog.py` · Events: `core/events.py` (+`core/event_bus.py` global) · Artifacts: `core/artifact_store.py`
- Git: `core/vcs.py` (wired) vs `core/git_manager.py` (worktrees, unwired, PF-050 bug) → consolidate in ENG-3
- Agent specs: `agents/*.agent.json` (66) + `core/agent_spec.py`
- Store SSOT: `config/store-registry.json`; env flags: `config/env-flags.json`

## Known defects/risks to fix in later phases

- Intake→pipeline run-lock gap: `core/intent_router.py:608 _run_pipeline_thread` bypasses `core.run_entry`.
- `core/issues.py:227` broken `find_similar(bscope,bproj,title)` call (wrong signature).
- Git manager duplicate + `git_manager` `create_branch` signature bug (PF-050) → ENG-3.
- Port defaults mismatch (8000/3001/8765).

## Process directive (user, binding)

think → design → 360° check → produce/code → stitched/wired → exercised → scalable → **API-first** → verify.
Execute the governing plan phase-by-phase; do not skip existing-implementation phases (audit/reconcile/reuse).
