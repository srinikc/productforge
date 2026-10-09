# Testing Reference — Product Forge (PF) + generated products

> **What this is:** a map of every test layer in Product Forge — where tests live, what they do, and
> **when/who/how** they are invoked. Two distinct layers: **PF's own regression suite** and the
> **generated-product test framework**.

Owner modules: `scripts/dev/precheck.py` (PF gates), `core/test_framework_integration.py` (product tests),
`core/verification_runner.py`, `core/test_matrix.py`, `core/pipeline_executor.py` (product-generation E2E).

## 0. The two layers

| Layer | What it tests | Where | Invoked by | When |
|---|---|---|---|---|
| **PF's own regression suite** | PF modules (backlog, API, validation, delivery, models, media, ...) | `product-forge/test-framework/tests/pipeline/` (~152 files) | `scripts/dev/precheck.py` (pytest) | every change (scoped) / merge+CI (`--full`) / release (`--release`) |
| **Generated-product tests** | the product PF builds (unit/api/db/integration/e2e/visual/...) | `test-framework/tests/<category>/` (convention) + `products/<project>/tests/<category>/` | pipeline `validate` stage → `test_framework_integration.run_cycle`; validation profiles (`verification`, `e2e`) | during product generation + validation/dogfood |

## 1. PF's own tests

- **Location:** `product-forge/test-framework/tests/pipeline/` (plus small category dirs, see §4).
- **Runner:** `python -m pytest test-framework/tests/pipeline -q` (config in `test-framework/tests/pipeline/pytest.ini`, fixtures in `conftest.py`).
- **Who/when (the gate):** `scripts/dev/precheck.py`:
  - **fast (default):** runs only tests affected by CHANGED files (`_scoped_tests`, `scripts/dev/precheck.py:54-80`) + always-run smoke; skips unrelated area gates.
  - **`--full` (merge/CI):** adds `pipeline-tests-full` = the complete suite (`-m pytest test-framework/tests/pipeline -q`, `precheck.py:167`) + the **deep** lifecycle gates: `validation-engine`, `feature-pr`, `merge-gate`, `dogfood`, `release`, `final-audit`, `backlog-e2e` (`precheck.py:134-140`).
  - **`--release`:** `--full` + the periodic full-tree `secret-scan-all` (`precheck.py:142`).
- **CI / PR merge gate** runs `precheck --full` (see `AGENTS.md` Definition of Done).
- **Note:** the deep lifecycle checks (`scripts/dev/*_check.py`) are part of precheck, not pytest.

## 2. Generated-product tests

### Categories & modes
- **Categories** (`config/test-matrix.json`): `unit, db, api, integration, ui, e2e, e2e_bdd, visual, accessibility, performance, security, reliability, scalability, smoke, sanity, install, packaging`.
- **Modes** (`test-framework/config/test-suites.yaml`):
  - `sanity` → unit, api
  - `feature` → unit, api, db, integration, e2e, mobile_ios, mobile_android
  - `nfr` → performance, security, accessibility
  - `packaging` → install, packaging
  - `full` → all
- **Kits** (`test-framework/kits/`): analytics, cloud_infra, compatibility, compliance, i18n, injection, media, notifications, offline_sync, rate_limit, social, tls, usability (merged into the matrix).

### Who calls them (how)
| Caller | Entry | What it does |
|---|---|---|
| Pipeline **validate stage** | `pipeline_executor._run_test_cycle` (`core/pipeline_executor.py:1948`) → `test_framework_integration.run_cycle` (`:272`) | register → ensure suites → build → matrix plan → **app lifecycle (deploy up) for UI/e2e** → `runner.run_suite` → record → log defects |
| Validation profile `verification` | `core/verification_runner.run_verification` (via `validation_engine.py:174`) | runs the product's test command (pytest/npm) in the target worktree |
| Validation profile `e2e` (BI-PF-0455) | `test_matrix.plan(project_dir, ['e2e'])` + `test_framework_integration._run_plan_item` (`validation_engine.py:214`) | runs the product's **e2e** category (e.g. `npx playwright test`); skip if no suite/runner |
| QA report / PR gate | `core/qa_report.py`, `core/pr_gate.py` | consume recorded results for GO/No-Go and merge decisions |
| Defect/RCCA loop | `test-framework/core/rcca.py`, `agent_integration.py` | failing test → defect → RCCA → agent prevention rule |

## 3. Full product-generation E2E (the 'run all stages/agents' path)

This is a **runtime engine, not a test suite**.
- `core.pipeline_executor.execute_pipeline(project, pipeline_file, products_dir)` → `PipelineExecutor.execute_pipeline()`
  iterates the **~38 stages** in `pipeline-definition.json` (`0, 0a, 1, 1a … 13b`) and runs each stage's agents.
  Each agent is an **LLM/model call** — i.e. the model runs stage-by-stage.
- **Manual harness:** `scripts/dev/run_e2e.py` → `execute_pipeline("test-pipeline", "pipeline-definition.json", "products")`.
  It is a dev script and is **NOT** a precheck/CI gate.
- **No pytest suite** runs the whole pipeline with live agents (non-deterministic + costly). Tests instead:
  - exercise executor internals via `PipelineExecutor.__new__(...)` (m0_acceptance, hil_*, run_manifest, per_feature_*, tool_authz, stop_conditions_duration, cache_policy);
  - `test_multimodal_e2e.py` — hermetic golden path per modality;
  - `core/e2e_lifecycle.py` ('FULL DOGFOOD') — walks lifecycle stages but is wiring/dry (dry ⇒ `PARTIAL_SUCCESS`).
- **Dogfood** (`core/dogfood.py`) is the self-proof gate: baseline → worktree → **enqueue** the pipeline → run the DOGFOOD validation profile → evidence/defects → report.

## 4. Category dirs under test-framework/tests/ (where generated-product tests go)

| Dir | Test files present | Purpose |
|---|---|---|
| `pipeline/` | 152 | pipeline category tests |

> These are the conventional per-category locations the matrix/bridge look up (`test-framework/tests/<category>`, `<category>`).

## 5. Dogfood / E2E product generation (plan + CI/CD alignment)

### 5.1 What "dogfood" is (and is NOT)
- Product generation runs on the **runtime engine**, not a worker:
  `POST /intake` / `POST /runs/start` → `run_entry.enqueue` (job_manager queue) → **supervisor**
  (`core/portfolio.run_supervisor`, hosted by `run_portfolio.py` / dashboard `/api/portfolio/start`) launches
  `scripts/run_pipeline.py --project <p>` → `PipelineExecutor.execute_pipeline()` → stage agents (LLM calls).
  It walks the ~38 stages in `pipeline-definition.json` (`0, 0a, 1, 1a … 13b`).
- There is **no worker** in the product-generation path. The worker/assignment plane (`/wg`,
  `/engineering/assignments/*`) is **`product_forge` backlog only** (BI-PF-0427).
- `scripts/dev/run_e2e.py` calls `execute_pipeline(...)` **directly** (bypasses the adapter) — a dev harness,
  NOT a precheck/CI gate. The sanctioned runner is **`scripts/run_pipeline.py`** (allowlisted CLI adapter:
  acquires the run lock, registers/finishes the job, tees `products/<p>/pipeline-run.log`).
- The "**stakeholder meeting**" is the **Human Proxy agent** (`agents/human.agent.json`, aliases
  `hil`/`stakeholder`/`human-proxy`), used in `--auto` mode to make HIL decisions.

### 5.2 Building blocks already present
| Concern | Owner / file | Notes |
|---|---|---|
| Start a run | `api/routers/runs.py` `POST /runs/start`; `api/routers/intake.py` `POST /intake` | `now`→`run_now_on_priority`, else enqueue |
| Runner flags | `scripts/run_pipeline.py` | `--idea --tier --auto --step --interactive --from-stage --only-stage --agent --no-cache --fresh` |
| Auto / HIL | `--auto` sets `auto_mode+auto_approve`; Human Proxy agent | no human needed |
| PIDL | `config/pidl-profile.json` | `autonomy: allowed, approval_required: false` default |
| Model tier | `config/model-tier.json` (`kctier` active) | kctier/opencode-go is the working path (Zen free tier 403, BI-PF-0247) |
| Logs / events | `products/<p>/pipeline-run.log`; `core/events.py` `events.jsonl` | `run_/stage_/agent_started|completed|failed`, `agent_blocked`, `agent_heartbeat` |
| Delivery | per-stage git branch/merge/push (Flow A) + `close_loop` | product remote is opt-in (`git-config.json`) |

### 5.3 Dogfood phases (API-first, compose canonical owners — no new engine/store)
- **Phase 0 — hermetic wiring** (PR gate, done): `core/e2e_lifecycle` + `dogfood_check` + `final_audit_check`.
- **Phase 1 — API auto-dogfood (the mechanism):** `POST /dogfood/run` `{idea, project, tier:"kctier", auto, caps, target}`
  → seed project (idea + auto + tier) → `run_entry.enqueue` → `run_id`; `GET /dogfood/runs/{id}` aggregates
  run + stages + agents + events/log tail + defects + validation; delivery assertions (repo commits/branch, tests,
  `close_loop`). Prereq: supervisor running.
- **Phase 2 — replay harness (deterministic):** LLM replay seam (record request→response by prompt hash) + cassette
  store; a CI-runnable integration dogfood wired into `precheck --full`.
- **Phase 3 — scheduled live dogfood (the cadence):** schedule the Phase 1 API (nightly/pre-release), store results
  in `validation-runs.json`, trends + regression alerts on the dashboard. (Same run as Phase 1; different trigger +
  governance.)

### 5.4 CI/CD + git alignment
Two "delivery" things — don't conflate: PF's own **code** lands via PF DoD (feature branch → precheck →
`merge --no-ff develop` → push); the **generated product's** delivery (Flow A) is what dogfood **asserts**.

| Trigger | PF gate | Validation profile | Product suite/mode | Live or replay | Blocks? |
|---|---|---|---|---|---|
| PR | `precheck` (fast/scoped) + hermetic `e2e_lifecycle`/`dogfood_check` | FEATURE_PR | sanity (unit, api) | hermetic/replay | yes |
| Merge / CI | `precheck --full` (+ deep gates) | INTEGRATION | feature (unit, api, db, integration, e2e) | **Phase 2 replay** | yes |
| Nightly | scheduled job | **DOGFOOD** | feature + e2e | **Phase 3 live** | no (trend/alert) |
| Pre-release | `precheck --release` + acceptance audit | RELEASE | full + packaging + nfr | live | yes (release gate) |

"When/what to call": on-demand → `POST /dogfood/run`; CI/merge → `dogfood-replay` gate in `precheck --full`;
nightly/pre-release → scheduler calls `POST /dogfood/run` → results to `validation-runs.json` + dashboard.

### 5.5 Profiles × suites alignment (orthogonal, they compose)
- **Validation profiles** = *when / what depth*: `FEATURE_PR` (before merge) → `INTEGRATION` (combined) →
  `DOGFOOD` (E2E product build) → `RELEASE` (qualify). Each selects checkers
  (`quality_gate, tests, policy, verification, pr_gate` + `cross_contract`/`e2e`/`security`).
- **Test suites/modes** = *which product tests* run inside that validation: `sanity`(unit,api),
  `feature`(unit,api,db,integration,e2e,mobile), `nfr`(performance,security,accessibility),
  `packaging`(install,packaging), `full`(all).
- Mapping: PR→FEATURE_PR/sanity; merge→INTEGRATION/feature; nightly→DOGFOOD/feature+e2e;
  release→RELEASE/full+packaging+nfr.

## 6. Appendix — PF pipeline test inventory (name :: purpose)

Total: **152** files in `test-framework/tests/pipeline/`.

| Test file | What it does |
|---|---|
| `test_a2a.py` | BI-0197: A2A interop — agnostic card, contract validation, server, client + pipeline tracking. |
| `test_agent_card_audit.py` | BI-PF-0252: agent-card tools/permission/model consistency audit. |
| `test_agent_ledger.py` | Tests for the Agent Ledger |
| `test_agnostic_cards.py` | BI-0201: framework-agnostic agent cards (no default .opencode dependency). |
| `test_agui.py` | BI-0198: AG-UI typed event stream — mapping + run filter + no-content. |
| `test_api_apidocs.py` | BI-PF-0355: the generated API reference surface (JSON + HTML + render). |
| `test_api_audit.py` | FULL DOGFOOD + FINAL AUDIT: acceptance audit + lifecycle API. |
| `test_api_core.py` | API-2: core PF read-model APIs — projects, runs, pipeline/stages/tasks, artifacts, evidence, backlog. |
| `test_api_dogfood.py` | ENG-9: DOGFOOD execution API (dry, fail-closed). |
| `test_api_engineering.py` | API-3: engineering/validation APIs — validation, tests, gates, issues, vcs, workers, agents. |
| `test_api_enterprise.py` | API-4: enterprise/SaaS/OEM surface — instance, tenants, users, tiers, license, entitlements, members, seats. |
| `test_api_events.py` | API-5: the formalized event envelope + read-only Event API. |
| `test_api_foundation.py` | API-1: canonical api/ surface — envelopes, ids, errors, idempotency, auth, health, intake. |
| `test_api_packaging.py` | REL-0: packaging manifest API (editions, validate, fail-closed). |
| `test_api_release.py` | ENG-10: release readiness / gate API (fail-closed). |
| `test_api_reservations.py` | ENG-8: shared-path reservations + merge gate + integration API. |
| `test_api_validation_engine.py` | ENG-6: Common Validation Engine profiles + run API. |
| `test_api_worker_metrics.py` | Worker timing / human-wait / token-cost metrics (reused owners). |
| `test_artifact_formats.py` | Tests for the dynamic artifact-format policy (BI-0110). Offline; emitters monkeypatched. |
| `test_asset_store.py` | BI-0187: media ingest + segmentation/tiling + asset store (fail-closed). |
| `test_assignment_dedup.py` | BI-PF-0422: assignments view + claim-time dedup guard (near-duplicates run at most once). |
| `test_assignments_api.py` | BI-PF-0419: external-worker assignment lifecycle (per-item claim + lease + API). |
| `test_backlog_context.py` | BI-PF-0444 (F2/D2): Epic entity - child linking, children rollup, no-dispatch, close-guard; context gate. |
| `test_backlog_field_types.py` | BI-PF-0441: core.backlog.update() rejects wrong-typed structured fields fail-closed (no write). |
| `test_backlog_id_audit.py` | BI-PF-0457: duplicate backlog id audit. |
| `test_backlog_integrity.py` | BU-C02/BZ-C02 backlog integrity: items/ truth vs derived indexes. |
| `test_backlog_pfssot_fields.py` | PFSSOT-P1 (BI-PF-0362): first-class execution fields on backlog items. |
| `test_backlog_refs.py` | Tests for scope-qualified backlog refs (BI-0082). |
| `test_bom.py` | BI-0217: product BOM/footprint build + write. |
| `test_branch_guard.py` | BI-PF-0430: pre-commit branch guard - never commit feature work directly on develop/main. |
| `test_budget_reservation.py` | F0-4 (PF-013): atomic budget reservation under a cap. |
| `test_byot_integration.py` | Tests for BYOT Integration |
| `test_cache_policy.py` | Cache-policy regression (philosophy: generation OUTPUT is never served from a |
| `test_capability_packs.py` | BI-0189: capability-pack registry + discovery->enablement profile (fail-closed). |
| `test_capability_steering.py` | S4 capability steering (BI-0221/0222/0223): vector + capability-aware request builder. |
| `test_change_log.py` | Engineering change log: append-only drift + corrective-action records, live entries, API. |
| `test_change_registry.py` | Tests for Change Registry |
| `test_close_loop_runbound.py` | F0-3 (PF-031): compliance evidence must be run-bound. |
| `test_context_discipline.py` | BI-0226: bounded context discipline. |
| `test_cost_model.py` | BI-0194: per-unit cost model — media per-unit pricing; text path unchanged; strategy integration. |
| `test_cost_modeling.py` | Tests for Cost Modeling |
| `test_credentials.py` | BI-0207: provider credential + budget registry. |
| `test_customer_onboarding.py` | Tests for Customer Onboarding |
| `test_deep_analysis.py` | PFSSOT-P3 (BI-PF-0364): deep architecture analysis merged into grooming. |
| `test_delivery.py` | BI-PF-0421 / BI-PF-0428: optimistic delivery lane (landing never switches the live tree's branch). |
| `test_delivery_writeback.py` | PFSSOT-P8A.1 (BI-PF-0381): auto delivery + evidence write-back on completion. |
| `test_dependency_catalog_check.py` | BI-PF-0443: dependency-catalog completeness hook - parsing, aliases, missing detection. |
| `test_design_review_guard.py` | Drift-guard tools: design_review_check flags violations and accepts aligned claims. |
| `test_diagram_render.py` | Tests for core.diagram_render (offline: the HTTP seam is monkeypatched). |
| `test_discovery_panel.py` | Tests for the 360-degree discovery panel (core/discovery_panel.py). |
| `test_domain_research.py` | Tests for Domain Research Engine |
| `test_entry_paths.py` | Retrofit R1: entry-path contract. |
| `test_escalation.py` | BI-0227: capability fallback / escalate-on-failure ladder. |
| `test_event_ssot.py` | F1 (BI-PF-0233): project-scoped bus events mirror into the canonical per-project stream. |
| `test_execution_contract.py` | M0.7 execution contract: missing fields => BLOCKED (fail closed). |
| `test_feasibility.py` | BI-0214: two-phase feasibility & capability triage (build-host verdict + destination shipping). |
| `test_feature_epic_bridge.py` | BI-PF-0452 (ADR-0004): Feature <-> Epic <-> children bridge. |
| `test_feature_epic_object.py` | BI-PF-0455: ensure_feature_item must accept a plan Feature OBJECT (not only a dict). |
| `test_feature_pipeline_p1.py` | BI-PF-0453 (P1): adding a plan feature materializes an Epic + child work items. |
| `test_finops.py` | Tests for FinOps Manager |
| `test_generator_adapters.py` | BI-0188: generator-model adapters (catalog, license gating, fail-closed, modality union). |
| `test_global_orchestrator.py` | Global Orchestrator Tests |
| `test_grooming.py` | PFSSOT-P2 (BI-PF-0363): AI + user grooming. |
| `test_grooming_consolidation.py` | BI-PF-0435: human-approved consolidation - fold unique content + close the duplicate (preserved). |
| `test_grooming_dedup_marking.py` | BI-PF-0432: grooming marks THIS item as a possible duplicate (advisory; same-project only). |
| `test_guardrails.py` | BI-0219: guardrails — actions, fail-closed, cards, C2PA provenance, governance, BOM integration. |
| `test_hil_decisions.py` | Regression for BI-0093: the full HIL approval decision model. |
| `test_hil_proxy_failclosed.py` | Regression for F0-1 approval truth (M0.1): BV-C01 + PF-001. |
| `test_human_proxy.py` | BI-PF-0245: HIL proxy is bounded to one decision per gate (cache) and surfaced. |
| `test_integration.py` | Integration Tests |
| `test_interactive_bridge.py` | Tests for the TTY-less prompt bridge (core/interactive.py) — BI-0026. |
| `test_invocation_audit.py` | Tests for the invocation (reachability) audit — BI-0029. |
| `test_issue_close_loop.py` | BI-PF-0271: the full issue <-> backlog close-loop, end to end and fail-closed. |
| `test_issues.py` | Issue tracker (BI-PF-0262): tagged ids, dedup by source_ref, 1:1 backlog mapping, |
| `test_learning_registration.py` | BI-PF-0295: operator-gated knowledge/skill registration from approved candidates. |
| `test_learning_synth.py` | BI-PF-0293: evidence-gated learning pipeline (no evidence -> no candidate; approve -> owner store). |
| `test_learnings.py` | Learnings registry: de-duplication + bounded (compact) rendering. |
| `test_licensing.py` | Tests for core/licensing.py (BI-0057/0060..0064/0069). |
| `test_llm_extract_no_reasoning.py` | Regression for BI-0075: LLM response extraction must NOT fall back to the model's |
| `test_lock_atomic.py` | F0-4 (PF-024): lock acquisition is atomic — exactly one contender wins. |
| `test_lock_manager.py` | Lock Manager Tests |
| `test_log_router_retention.py` | BI-PF-0233: log_router retention (rotate_runs) + canonical event routing. |
| `test_m0_acceptance.py` | M0 acceptance suite (BI-PF-0243): the 11 execution-integrity scenarios. |
| `test_main.py` | Tests for Product Forge main entry point |
| `test_maintenance.py` | Tests for Maintenance Manager |
| `test_marketing.py` | Tests for Marketing Generator |
| `test_mcp.py` | BI-0196: MCP interop — server round-trip, approval fail-closed, client call + ingest. |
| `test_media_agents.py` | BI-0190: media agents load, have live knowledge bindings, and are pack-gated in composition. |
| `test_media_chunking.py` | BI-PF-0288: media chunking + markdown asset-ref resolution. |
| `test_media_context.py` | BI-PF-0287: media context — native parts vs summary, token accounting, e2e threading. |
| `test_media_qa.py` | BI-0191: media QA validators (probe/perceptual/degrade; no-op without media; findings shape). |
| `test_model_fit.py` | Tests for core/model_fit.py (BI-0076): probe tier models, report agent compatibility |
| `test_model_gate.py` | BI-PF-0246: unknown-capability fail-closed rule in the model capability gate. |
| `test_model_policy.py` | BI-PF-0278: per-model eligibility policy — schema, eligibility, gate/strategy integration. |
| `test_model_recommendation.py` | Tests for Model Recommendation Engine |
| `test_model_strategy.py` | BI-0192/BI-0210: two-phase model & capability strategy gate (no-op + media e2e). |
| `test_multimodal.py` | BI-0186: multimodal LLM plumbing — media parts gated by model input_modalities (fail-closed). |
| `test_multimodal_e2e.py` | BI-0212: multimodal end-to-end acceptance (hermetic; one golden path per modality). |
| `test_otel_genai.py` | BI-0199: OTel GenAI spans (incl. multimodal) — mapping + emit; no content/bytes leak. |
| `test_parallel_validation.py` | BI-PF-0420: parallel-safe validation - run-scoped records + isolation + concurrency cap. |
| `test_pdf_generator.py` | Tests for PDF Generator |
| `test_per_feature_files.py` | Per-feature artifact files (option 1B) for design / product-design-spec. |
| `test_per_feature_gate.py` | Deterministic per-feature validation gate. |
| `test_per_feature_outline.py` | Per-feature sectioned generation + validation gate (BI-0098). |
| `test_phase1_new.py` | Tests for Version Manager, Release Manager, Logging, Cross-Review, and Skills Registry |
| `test_pipeline_composition.py` | BI-0213: capability-gated pipeline composition (identity guard + anchor insert + roster). |
| `test_plugins.py` | BI-0200: plugin/registry framework (drop-in registration + fail-closed resolve + composition). |
| `test_presentation_generator.py` | Tests for Presentation Generator |
| `test_product_analyzer.py` | Tests for Product Analyzer |
| `test_product_ingestion.py` | Tests for Product Ingestion |
| `test_product_issue_loop.py` | BI-PF-0272: the issue<RCCA>backlog loop applies to the PRODUCT being built (scope=project). |
| `test_product_page.py` | BI-0216: product one-stop page read model. |
| `test_product_plan.py` | Product Plan Tests |
| `test_progress.py` | Tests for the E2E progress banner (core/progress.py) — BI-0027. |
| `test_project_archive.py` | Tests for core/project_archive.py (BI-0071). |
| `test_prompt_discipline.py` | F0/EOS: the global engineering-discipline guard must reach EVERY agent prompt. |
| `test_provider_health.py` | BI-PF-0279: provider health tracking — outcomes, states, health-aware ordering (no regression). |
| `test_provider_kinds.py` | BI-0193: provider-kind abstraction + kind-aware routing (fail-closed). |
| `test_queue_manager.py` | Queue Manager Tests |
| `test_rcca_learning_loop.py` | BI-PF-0270: RCCA -> learning -> guideline loop is wired + the close gate is fail-closed. |
| `test_redaction.py` | Section D P2 (BI-PF-0244): canonical levels + secret redaction on log/event writes. |
| `test_render.py` | BI-0224: deterministic renderer for structured (JSON-first) agent output. |
| `test_result_aggregator.py` | BI-PF-0277: result aggregator — provenance, evidence merge, conflicts, quorum (bug fix). |
| `test_run_manifest.py` | F0-3 (M0.3): run-bound provenance — manifest + stale-approval rejection. |
| `test_run_status_reconcile.py` | F1 (BI-PF-0234): terminal events carry run_id and reconcile leftover 'running' state. |
| `test_scheduler_eligibility.py` | PFSSOT-P4 (BI-PF-0365): scheduler eligibility over the canonical backlog (read-only). |
| `test_scoped_learnings.py` | BI-PF-0294: scoped learnings (project/area) + need-based render + memory read-back opt-in. |
| `test_section_d.py` | Section D P3-P6 (BI-PF-0244): status rebuild, SLIs, OTel export, JSONL retention. |
| `test_security.py` | Security System Tests |
| `test_spec_id_allocation.py` | Deterministic per-feature FR/NFR/US id allocation + post-merge integrity gate. |
| `test_state_machine.py` | State Machine Tests |
| `test_state_projection.py` | BI-PF-0260: PROJECT-STATUS.md is single-writer (run_status); journal uses a distinct file. |
| `test_stop_conditions_duration.py` | Regression for BI-0072: max_duration_per_stage must measure the STAGE's elapsed |
| `test_tech_detect.py` | Regression for BI-0078: tech detection must not match common English words. |
| `test_tenant_authz.py` | PF-022 tenant-scoped authz: fail-closed cross-tenant decision. |
| `test_tool_authz.py` | F0-5 (PF-004/BV-C02, PF-227): fail-closed tool authz + path containment. |
| `test_tool_catalog.py` | BI-0211: tool/SDK/vendor catalog - decision table, gate, and read API. |
| `test_tool_settings_api.py` | BI-PF-0439: web_search settings API (API-first) + settings/secret store (key never returned). |
| `test_traceability.py` | Traceability Matrix Tests |
| `test_tracing.py` | Section D P1 (BI-PF-0244): trace context on events. |
| `test_validation_checkers.py` | BI-PF-0425: every validation-profile checker is implemented (no profile is permanently BLOCKED). |
| `test_vendor.py` | BI-0202: neutral vendored tools — resolution order, no .opencode default, clear hint. |
| `test_verbose.py` | BI-0229: verbose logging gate. |
| `test_video_generation.py` | Tests for Video Generation Engine |
| `test_web_search_tool.py` | BI-PF-0438: web_search tool - a client over a configurable backend (default disabled; no new dependency). |
| `test_workergrid_agent_e2e.py` | WorkerGrid worker agent end-to-end (BI-PF-0413, Stage 3c). |
| `test_workergrid_cli_config.py` | WorkerGrid CLI config + local claim (BI-PF-0417). |
| `test_workergrid_pf_client.py` | BI-PF-0423: WorkerGrid as a thin PF client - `/wg work` drives the PF assignment lifecycle. |
| `test_workergrid_pg_store.py` | WorkerGrid Stage 3b (BI-PF-0414): PostgreSQL coordination store end-to-end. |
| `test_workergrid_service_contract.py` | WorkerGrid coordinator service contract (BI-PF-0412) - one suite, two implementations. |
| `test_workflow_docs.py` | Tests for Workflow Documentation Generator |
| `test_write_safety.py` | Write Safety Tests |
