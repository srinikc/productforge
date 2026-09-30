# Product-Scope Issue/RCCA/Backlog Integration — Design (BI-PF-0272)

## Goal
Make the issue → RCCA → backlog close-loop apply to the **product being built** (`scope="project"`),
wired into the pipeline, orchestrated per stage/run, API-based, and dashboard-ready. Today only the
`product_forge` scope is wired; a product under construction accumulates defects/issues that never
reach the canonical `IS-<TAG>-<nnn>` registry as RCCA-tracked, backlog-paired findings.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Canonical issue registry | `core/issues.py` (`IS-<TAG>-<nnn>`, RCCA, 1:1 backlog) — wired for `product_forge` only | same, exercised for `project` scope | `core/issues.py` |
| Defect → issue bridge | `issues.ingest_defects(scope, project)` **has ZERO callers**, and omits `auto_backlog=True` | called by the pipeline; auto-raises paired backlog | `core/issues.py` + pipeline |
| Legacy stage issues | `core/issue_tracker.py` writes `products/<p>/issues/<stage>-<agent>-issues.json` (no RCCA/link) | bridged into canonical issues (idempotent) | new bridge fn |
| Defect registration | `defect_loop.route_stage_issues` called at end-of-run in `_save_issues` | keep; add canonical-issue ingestion there | `core/defect_loop.py`/pipeline |
| Pipeline hook | `PipelineExecutor._save_issues()` (`pipeline_executor.py:3423-3440`), run-end, after metrics/report | single hook: also `ingest_defects("project", project)` + bridge legacy issues | `core/pipeline_executor.py` |
| Per-stage timing | only end-of-run aggregation exists | optionally a per-stage hook (stage_runner) for incremental issues | `core/orchestrator/stage_runner.py` |
| Latent bug | `agent_execution.py:472-475` checks `"security"/"nfr"/"tests"` but stage IDs are `"5"/"6"/"7"` → never fires | fix to real stage IDs | `core/orchestrator/agent_execution.py` |
| API (read) | `/api/v1/issues*` + `/api/v1/backlog*` support `?scope=project:<name>` | + product-scoped convenience routes | `dashboard/api/app.py` |
| Product read model | `core/product_page.py` surfaces `features` (backlog) but **no issues** | add `issues()` section + include in `page()` | `core/product_page.py` |
| Blueprint | `config/dashboard-blueprint.json` lists `backlog`, not `issues` | add `issues` surface | `config/dashboard-blueprint.json` |

## Design decisions
- **Single writer preserved.** `core/issues.py` owns issue state; `core/backlog.py` owns backlog.
  The bridge and pipeline only *call* their public APIs — no module writes another's store.
- **One hook, run-end.** In `_save_issues` (after `route_stage_issues`) call
  `issues.ingest_defects("project", self.project)`. It is idempotent (keyed on `(source, source_ref)`)
  so repeated runs never duplicate. Pass `auto_backlog=True` inside `ingest_defects` so each product
  issue gets its paired `products/<p>/backlog/` item and the 1:1 link.
- **Bridge legacy → canonical.** New `issues.ingest_stage_issues(scope, project)` reads the legacy
  `products/<p>/issues/<stage>-<agent>-issues.json` files (`issue_tracker.load_issue_list`), raising
  canonical issues with `source="stage_audit"`, `source_ref=f"{stage}:{agent}:{issue_id}"` (idempotent),
  carrying category→kind/priority/severity and `module`. Called from `_save_issues` too.
- **Fix the latent stage-ID bug** so `_track_security_issues`/`_track_test_issues` actually fire for
  stages `5`/`6`/`7`.
- **API stays read-only over truths + action passthrough**, scope-parameterized. Add product-scoped
  convenience routes mirroring `/api/v1/products/{project}/*`; the generic `/api/v1/issues*` already
  works with `?scope=project:<name>`. No store writes from the API.
- **Dashboard-ready:** add an `issues()` section to `core/product_page.py` (next to `features`) and
  include it in `page()`; add `issues` to `config/dashboard-blueprint.json`. No frontend build (repo
  has no JS build; UI consumes the API later — this task delivers the API + read model).

## Plan (one branch `feature/bi-pf-0272-project-issue-loop`)
1. `docs/PRODUCT-ISSUE-LOOP-DESIGN.md` (this file).
2. `core/issues.py`: `ingest_defects` → pass `auto_backlog=True`; add `ingest_stage_issues`.
3. `core/pipeline_executor.py::_save_issues`: call both ingest functions (guarded, best-effort).
4. `core/orchestrator/agent_execution.py`: fix stage-ID checks (`5`/`6`/`7`).
5. `core/product_page.py`: add `issues()` + include in `page()`.
6. `dashboard/api/app.py`: `GET /api/v1/products/{project}/issues(/{iid})` + `/backlog`.
7. `config/dashboard-blueprint.json`: add `issues` surface.
8. Tests: `test_product_issue_loop.py` — a product-scope run-like flow produces issue→backlog→RCCA
   pairs, closes both with `fixed_where`; `test_product_page_issues.py` for the read model; API test
   for scope=project routes.
9. Gates: `compileall`, `wired_audit`, `workflow_matrix_check`, pipeline tests, `precheck`.
10. Merge; close `BI-PF-0272` **through the loop itself**.

## Acceptance
- A product-scope defect becomes a canonical `IS-*` issue with a paired `products/<p>/backlog/` item,
  1:1 linked; RCCA gate prevents close until complete; closing the issue closes the backlog item with
  `fixed_where` (proven by test).
- Legacy stage-audit issues are bridged (idempotent), no duplicates on re-run.
- `GET /api/v1/products/{project}/issues` returns `{scope,state,count,items,stats}`; `product_page.page()`
  includes `issues`.
- `precheck` PASS; no new store/module; single-writer invariant intact.

## Out of scope (tracked separately)
Frontend UI implementation (later, on the dashboard backlog); auto-fixing defects; multimodal issues.
