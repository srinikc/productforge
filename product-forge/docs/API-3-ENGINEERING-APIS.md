# API-3 — Engineering / Validation APIs

**Phase:** API-3 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md` (§10)
**Status:** Implemented — gate PASS
**Depends on:** API-1 (`docs/API-1-FOUNDATION.md`), API-2 (`docs/API-2-CORE-APIS.md`)

## What this phase builds

Thin **engineering/validation APIs** that map onto existing internal systems — the control surface the
engineering factory (ENG-*) will build over. **No new engines, stores, or validation systems.**

```
api/routers/
  _common.py      shared project/products resolution (fail-closed)
  validation.py   verify_run + verification policy        (core.close_loop, core.verification_policy)
  tests.py        test-matrix plan/gaps + cycle summaries (core.test_matrix, test-framework results)
  gates.py        PR gate, quality gate, Go/No-Go         (core.pr_gate, core.run_quality_gate, core.qa_report)
  issues.py       findings + RCCA registry                (core.issues)
  vcs.py          git branch/status/commits               (core.vcs)
  workers.py      queue + capacity, pause/resume          (core.run_entry/job_manager, core.capacity)
  agents.py       agent specs + capability vectors        (core.agent_spec, core.agent_capabilities)
core/vcs.py       + read-only status()/branches() helpers (owner-extended, no new store)
scripts/dev/api_contract_check.py   extended with the API-3 surface + fail-closed unknown project
test-framework/tests/pipeline/test_api_engineering.py  7 tests
```

## Endpoints (24 new; 49 OpenAPI paths total)

| Method | Path | Backing canonical service |
|---|---|---|
| GET | `/api/v1/validation` | `core.close_loop.verify_run(project_dir, scope, run_id)` |
| GET | `/api/v1/validation/policy` | `core.verification_policy.summary` |
| GET | `/api/v1/tests/matrix` | `core.test_matrix` (kind → categories → plan/missing) |
| GET | `/api/v1/tests/cycles` | `test-framework/results/test-cycles/<project>_*.json` (read-model) |
| GET | `/api/v1/gates/pr` | `core.pr_gate.evaluate` |
| GET | `/api/v1/gates/pr/merge` | `core.pr_gate.can_merge` |
| GET | `/api/v1/gates/quality` | `core.run_quality_gate.latest` |
| GET | `/api/v1/gates/go-no-go` | `core.qa_report.load` |
| GET | `/api/v1/issues` | `core.issues.list_open/list_closed` (paginated) |
| GET | `/api/v1/issues/stats` | `core.issues.stats` |
| GET | `/api/v1/issues/{iid}` | `core.issues.get` |
| POST | `/api/v1/issues` | `core.issues.raise_issue` (operator) |
| POST | `/api/v1/issues/{iid}/rcca` | `core.issues.set_rcca` (operator) |
| POST | `/api/v1/issues/{iid}/status` | `core.issues.set_status` (operator, fail-closed close) |
| GET | `/api/v1/vcs` | `core.vcs.VCSManager.history` + `status` |
| GET | `/api/v1/vcs/status` | `core.vcs.VCSManager.status` (new read-only helper) |
| GET | `/api/v1/vcs/branches` | `core.vcs.VCSManager.branches` (new read-only helper) |
| GET | `/api/v1/vcs/commits` | `core.vcs.VCSManager.checkins` |
| GET | `/api/v1/workers/queue` | `core.run_entry.queue_status` (jobs enriched with `reason`) |
| GET | `/api/v1/workers/capacity` | `core.capacity.status` |
| POST | `/api/v1/workers/queue/{project}/pause` | `core.job_manager.pause_request` (operator) |
| POST | `/api/v1/workers/queue/{project}/resume` | `core.job_manager.resume` (operator) |
| GET | `/api/v1/agents` | `core.agent_spec.list_agent_ids` + `card_for` |
| GET | `/api/v1/agents/{agent_id}` | `core.agent_spec.card_for` |
| GET | `/api/v1/agents/{agent_id}/capabilities` | `core.agent_capabilities.vector` + `reasoning_enabled` |

## Reuse (no duplicate engines/stores)

- **Validation:** the canonical, run-bound decision is `core.close_loop.verify_run`; classification is
  `core.verification_policy`. No new "validation engine".
- **Tests:** catalogue/plan from `core.test_matrix`; actual cycle results are the test-framework's own files
  (read-only projection). The write path (`run_cycle`) is intentionally **not** exposed here.
- **Gates:** `pr_gate` (local checklist), `run_quality_gate` (compileall + wired-audit), `qa_report` (persisted
  Go/No-Go). All read-only on the API.
- **Defect/RCCA:** `core.issues` is the canonical single-writer `IS-*` registry (RCCA + 1:1 backlog link);
  the test-framework defect/RCCA bridge is not duplicated.
- **Git:** `core.vcs.VCSManager` remains the ONE git owner; API-3 only added read-only `status()`/`branches()`.
- **Workers:** `core.run_entry`/`core.job_manager` are the queue SSOT; `core.capacity` owns limits.
- **Agents:** `core.agent_spec` (cards) + `core.agent_capabilities` (vector). No agent store added.
- **Task:** no distinct Task store exists; the stage×agent projection (`GET /api/v1/tasks`, API-2) is the Task
  surface, and work truth stays in the backlog (`core.backlog`).

## 360° dependency check

- New routers live under `api/` (outside `wired_audit` scan roots); exercised by `api_contract_check.py`
  (precheck) and `test_api_engineering.py`.
- `core/vcs.py` gained only read-only methods; no new store, so `store-registry` is unchanged.
- No edits to `dashboard/` (frozen). No new pipeline/validation/backlog/artifact/event defect/Git engines.
- Reads are authenticated; mutations (`issues`, `workers` controls) are **operator-gated**.
- Project-scoped reads are fail-closed: unknown project ⇒ canonical `NOT_FOUND` (400 for bad input).

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §10)

| Criterion | Result |
|---|---|
| Validation API | ✅ `verify_run` + policy |
| Evidence API | ✅ (API-2 `/evidence/*`, run-bound manifests) |
| Defect/RCCA API | ✅ canonical `issues` (list/get + RCCA/status writes) |
| Test API | ✅ matrix plan/gaps + cycle summaries |
| Gate API | ✅ PR / quality / Go-No-Go |
| Git/VCS API | ✅ branch/status/commits (read-only) |
| Task API | ✅ stage×agent tasks (API-2) over definition/state (no shadow store) |
| Worker API | ✅ queue/capacity + pause/resume |
| Agent API | ✅ specs + capability vectors |
| Maps to existing systems / no shadow DB | ✅ every endpoint delegates to a canonical owner |

**API-3 GATE: PASS.** Proceed to ENG-0 (engineering factory architecture) and/or API-4 (enterprise/SaaS/OEM),
which may run in parallel once dependencies are available.

## Notes / deferred

- VCS `status()`/`branches()` are read-only additions to the canonical owner; `git_manager.py` (worktrees,
  PF-050) stays unwired and must be consolidated into `vcs.py` in **ENG-3**.
- Write actions that mutate run/engine state (e.g. `run_cycle`, `pr_gate.override`, verify-and-close) are
  deliberately out of API-3 scope; they belong with the ENG scheduler/worker work or API-5 hardening.
