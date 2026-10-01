# API-2 — Core Product Forge APIs

**Phase:** API-2 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md` (§9)
**Status:** Implemented — gate PASS
**Depends on:** API-1 (`docs/API-1-FOUNDATION.md`), contract `docs/API-0.1-CONTRACT-RECONCILIATION.md`

## What this phase builds

Thin **application APIs** over the existing Product Forge engines in dependency order:

```
Project → Run → Pipeline → Stage → Task → Artifact → Evidence → Backlog
```

The API exposes *capabilities* (via canonical services), never direct file-store manipulation.

```
api/
  pagination.py         cursor pagination (bounded: default 50, max 500)
  routers/
    projects.py         list/get/create projects         (core.project_store + products dir)
    runs.py             list/active/start/stop runs       (core.run_entry, job_manager, control channel)
    pipeline.py         pipeline/stages/tasks read-model  (pipeline-definition.json + pipeline-state.json)
    artifacts.py        list artifacts + read content     (core.artifact_store, core.stage_paths)
    evidence.py         events + run manifest + index     (core.events, run-manifests/)
    backlog.py          list/stats/get + add/set-status   (core.backlog)
scripts/dev/api_contract_check.py                          # extended: core GET surface + validation error
test-framework/tests/pipeline/test_api_core.py             # 12 tests (read + control + artifact roundtrip)
```

## Endpoints (25 OpenAPI paths total; API-2 adds 15)

| Method | Path | Backing canonical service |
|---|---|---|
| GET | `/api/v1/projects` | products dir + `core.project_store` |
| GET | `/api/v1/projects/{project}` | `core.project_store.load` |
| POST | `/api/v1/projects` | `core.project_store.save` |
| GET | `/api/v1/runs` | `core.run_status.summary` |
| GET | `/api/v1/runs/active` | `core.run_entry.active` → `run_guard` |
| POST | `/api/v1/runs/start` | `core.run_entry.enqueue` / `run_now_on_priority` |
| POST | `/api/v1/runs/stop` | `core.job_manager.cancel` + `control.json` channel |
| GET | `/api/v1/pipeline` | `pipeline-definition.json` |
| GET | `/api/v1/pipeline/stages` | definition + `pipeline-state.json` |
| GET | `/api/v1/pipeline/stages/{stage_id}` | definition + `pipeline-state.json` |
| GET | `/api/v1/tasks` | definition `ideal_flow` + state agents |
| GET | `/api/v1/artifacts` | `core.artifact_store.get_artifact_summary` |
| GET | `/api/v1/artifacts/{stage_id}/{agent}` | `core.artifact_store.scan_project_artifacts` + content |
| GET | `/api/v1/evidence/events` | `core.events.read` / `counts` |
| GET | `/api/v1/evidence/manifest/{run_id}` | `run-manifests/<run_id>.json` |
| GET | `/api/v1/evidence/index` | run-manifests listing |
| GET | `/api/v1/backlog` | `core.backlog.list_open/list_closed/list_items` |
| GET | `/api/v1/backlog/stats` | `core.backlog.stats` |
| GET | `/api/v1/backlog/items/{item_id}` | `core.backlog.get` |
| POST | `/api/v1/backlog/items` | `core.backlog.add_epic` (operator) |
| POST | `/api/v1/backlog/items/{item_id}/status` | `core.backlog.set_status` (operator) |

## Reuse (no duplicate engines/stores)

- **Projects** read/write `core.project_store` (`project.json`); no shadow store.
- **Runs** go through the ONE entry `core.run_entry` (enqueue / priority) and the queue SSOT `core.job_manager`.
- **Pipeline/stages/tasks** are a read-model over `pipeline-definition.json` + per-project `pipeline-state.json`.
- **Artifacts/evidence** reuse `core.artifact_store` (content hashes, `stage_paths` naming) and `core.events`.
- **Backlog** uses `core.backlog` services only.
- **Pagination** is a local helper (API-0.1 §9); no new persistence.

## Task API boundary (updated plan §9 / §2A)

Two distinct "task" surfaces, deliberately separate:

- `GET /api/v1/tasks` — the pipeline **stage×agent projection** (read-model over `pipeline-definition.json` +
  `pipeline-state.json`). This is **not** the engineering work item.
- The **engineering Task/Work API** (`/api/v1/engineering/tasks`, delivered ENG-1) — the **direct engineering
  entry point**: resolve/create/claim/assign a task → run → scheduler → worker. It must **not** manufacture a
  conversation record merely to start work, and it does **not** require Intake.

Intake (external ingestion) may produce a backlog work item that a task references
(`epic_id`/`feature_id`), but is **not** an engineering prerequisite (updated plan §2A).

## Long-running actions

`POST /runs/start` never executes a pipeline inline. It returns a run/operation identity
(`resource_id` = `run_id`, status `accepted`) and progress is observable via `GET /runs`,
`GET /runs/active`, `GET /evidence/events`, and `pipeline-state.json`.

## 360° dependency check

- New routers live under `api/` (outside `wired_audit` scan roots), so no UNWIRED false positive;
  they are exercised by `api_contract_check.py` (precheck) and `test_api_core.py`.
- No edits to `dashboard/` (frozen). No new pipeline/validation/backlog/artifact/event/Git engines.
- Execution stays `core.run_entry`-owned; the intake-through-API path does not bypass the run lock.
- `control.json` is the canonical cross-process stop channel (same one `run_pipeline.py --control stop`
  and `run_guard.ensure_single_run` use); `core.portfolio.control` is reused as the writer.

## Defects found & fixed during API-2 review (RCCA-lite)

| # | Symptom | Root cause | Fix | Guard |
|---|---|---|---|---|
| 1 | `POST /runs/start {now:true}` raised (500) | called `run_entry.run_now_on_priority(project, dir, actor=...)`; signature is keyword-only (`by`, no `actor`) | call with `by=`, `item_id=`, `products_dir=` | `test_start_now_calls_priority_with_valid_kwargs` |
| 2 | `POST /runs/stop` silently did nothing | called non-existent `pipeline_executor.request_stop` | settle queue via `job_manager.cancel` + write `control.json` when a run is live | `test_stop_cancels_and_signals_control_channel` |
| 3 | `GET /artifacts/{stage}/{agent}` always 404 | called `get_artifact_content(dir, stage, agent)`; the function takes one file path | resolve via `scan_project_artifacts` then read `a.path` | `test_artifact_content_roundtrip` |

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python -m pytest test-framework/tests/pipeline/test_api_core.py \
                 test-framework/tests/pipeline/test_api_foundation.py -q -o addopts=""
                                                                  # 20 passed
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §9)

| Criterion | Result |
|---|---|
| create/read/update project | ✅ GET/POST `/projects` |
| create/start/stop/resume run | ✅ start (enqueue/priority), stop (cancel + control channel); resume stays `run_entry`/job_manager |
| inspect pipeline / stages / tasks | ✅ |
| inspect artifacts | ✅ list + content |
| inspect evidence | ✅ events/manifest/index |
| inspect/update backlog via canonical services | ✅ read + add + set-status (operator) |
| long-running actions return identity + events | ✅ `run_id` + canonical events |

**API-2 GATE: PASS.** Proceed to API-3 (engineering/validation APIs), mapping to existing internal
systems; no shadow databases.

## Open risk (tracked, not blocking)

- `config/store-registry.json` lists `control.json` owner as `core/human_controls.py`, but that source
  module is absent (only a stale `.pyc`). Actual writers: `core.portfolio.control`, `core.run_guard._write_control`,
  `scripts/run_pipeline.py` (+ API now reuses `portfolio.control`). Consolidating to one writer/registry
  entry belongs to the API-5 hardening pass (BI-PF-0331 OS/shell neutrality neighbour).
