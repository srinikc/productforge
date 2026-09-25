# Pipeline Change Plan — Single Source of Truth

> **Created:** 2026-09-10
> **Purpose:** Consolidate every change identified across our discussions into one
> place — what's done, what the current major change is, what's pending, and what
> is a separate backlog to handle *after* the major change.
>
> **Context:** Many capabilities already existed in the codebase as **placeholders,
> scattered and unwired** (e.g. `compliance_verifier` prompts, `phase3_advanced`,
> `AgentMessenger`, `ProductPlan`, `AgentLedger`, `StateMachine`, the 48
> `.opencode/agent/*.md` cards). This plan wires what matters and records the rest.

Legend: ✅ DONE · 🟡 PARTIAL · ⬜ PENDING · ⏸️ DEFERRED/SEPARATE

---

## PART 1 — THE MAJOR CHANGE (in progress)
**Theme:** make agents actually *build* (tools + real files + real verification)
and govern cost — generic, not framework-locked.

### 1A. Agent execution model 🟡
| # | Change | Status | Where | Notes |
|---|---|---|---|---|
| 1A.1 | Neutral **`AgentSpec`** (id, instructions, tools, contract, tier, allowed_inputs, decision_logic, knowledge_layers, memory, completion) | ✅ | `core/agent_spec.py` | Single definition per agent |
| 1A.2 | **`ToolRegistry`** (`write_file/read_file/list_dir/run_command/http_get`) + path sandbox + command allow-list | ✅ | `core/tool_registry.py` | Sandbox + allow-list verified |
| 1A.3 | **Agent tool loop** (provider-neutral text protocol; native function-calling later) | ✅ | `core/agent_tool_loop.py`, `_generate_with_tools` | Works with any chat model |
| 1A.4 | **Hybrid rollout** — code agents write files; planners stay markdown | ✅ | executor (`enable_tools`, default **ON**) | Per-agent gated by `spec.tools`; **E2E verified** |
| 1A.5 | Convert 48 `.opencode/agent/*.md` → specs (union) + author 5 missing (`design_critic, discovery, product-design-spec, ux-ia, visual_qa`) | ✅ | `core/agent_spec.py`, `scripts/dev/build_agent_specs.py`, `agents/` | 53 specs generated |
| 1A.6 | Render prompts from specs (replace 4 templates + generic fallback) | ✅ | `_build_agent_prompt` | Spec instructions preferred; template fallback kept |
| 1A.7 | **Real verification** — `validate` runs tests/build; skipped when no project files | ✅ | `core/verification_runner.py` + executor | Kills "phantom tests" |
| 1A.8 | **No-mock/no-stub gate** (scan real source for `TODO/FIXME/placeholder/stub`) | ✅ | `core/code_quality_gate.py` + executor | Enforces AGENTS.md rule |
| 1A.9 | **Unify paths** — `/pipeline` is now a thin adapter to the generic orchestrator | ✅ | `.opencode/command/pipeline.md`, `scripts/run_pipeline.py` | No Task-based orchestration |
| 1A.10 | opencode adapter — generate `.opencode/agent/*.md` from `AgentSpec` | ✅ | `scripts/dev/generate_agent_cards.py` | Applied (53/53, 0–8 standard) |
| 1A.11 | **Decompose `pipeline_executor.py`** into `core/orchestrator/*` | ✅ | Composition modules: `storage, types, llm_client, prompt_builder, model_router, compliance, phasing, checkpoint, reporting, delegation_coord`; mixins (verbatim, self=executor): `agent_runner, stage_runner, agent_execution`. **executor ~3490 → 1186 lines**. Remaining in file: `execute_pipeline` orchestration + HITL/budget/config glue (cohesive, intentional) |

### 1B. Governance (mostly ✅)
| # | Change | Status | Where |
|---|---|---|---|
| 1B.1 | Telemetry module + agent→stage→phase→pipeline rollups + API | ✅ | `core/pipeline_telemetry.py`, `api/telemetry.py` |
| 1B.2 | Contract-driven output cap + auto-continue + token ceiling | ✅ | `pipeline_executor._call_llm*` |
| 1B.3 | Budget spec (soft/hard/±variance) + tier proposal + approval | ✅ | `core/budget_planner.py`, `api/budget.py` |
| 1B.4 | Run breaker (cost/token/rate loop) + alerts | ✅ | `core/run_breaker.py`, `api/alerts.py` |
| 1B.5 | Token budget reconciliation (pipeline + stage) | ✅ | executor |
| 1B.6 | Compaction net-cost tracking | ✅ | executor + telemetry |
| 1B.7 | Cross-project cost history | ✅ | telemetry + `api/telemetry.py` |
| 1B.8 | Dynamic iteration planner (feature subsets) + skip unused | ✅ | `core/iteration_planner.py` |
| 1B.9 | Template fallback = hard failure (no stub artifact) | ✅ | executor |
| 1B.10 | Feed project idea → Stage 0 | ✅ | executor `project_idea` |
| 1B.11 | Compliance retry loop (actually re-runs) | ✅ | executor |
| 1B.12 | Real `KnowledgeComplianceChecker._check_pattern` | ✅ | `core/knowledge_compliance_checker.py` |
| 1B.13 | Live journal (StateMachine + AgentLedger + `PROJECT-STATUS.md`) + API | ✅ | `core/project_journal.py`, `api/journal.py` |
| 1B.14 | Delegation router + budget + records (opt-in) + API | ✅ | `core/delegation.py`, `api/delegation.py` |
| 1B.15 | API-first endpoints (all governance domains) | ✅ | `pipeline_dashboard/api/*` |
| 1B.16 | Fix `compliance_check.py` `__main__` IndentationError (line 1296) that silently disabled all rule compliance | ✅ | `core/compliance_check.py` |
| 1B.17 | **Free-trial model tier** — config-driven profile mixing OpenCode Zen + OpenRouter free models; all 53 agents mapped with role-appropriate primary + cross-provider fallbacks; selectable via `PIPELINE_MODEL_TIER` / `project.json:model_tier` / `run_pipeline.py --tier` | ✅ | `model-tier.json` profiles, `ModelRouter`, `run_pipeline.py` |
| 1B.18 | `LLMClient` actually iterates `fallback_models`/`candidates` (was ignored); **fast-fail on non-200/429** so fallback engages immediately instead of 5s/10s same-model sleeps | ✅ | `core/orchestrator/llm_client.py` |
| 1B.19 | Never cache template/fallback results; template fallback returned as hard failure (no stub success) | ✅ | `core/orchestrator/llm_client.py` |
| 1B.20 | Knowledge budget no longer hardcoded 12000 → `KNOWLEDGE_BUDGET_TOKENS` env / `project.json:knowledge_budget_tokens`; suppress the misleading CRITICAL alert for fill-to-budget knowledge loads | ✅ | `core/pipeline_executor.py`, `core/budget_protection.py` |
| 1B.21 | `BudgetManager.create_budget` no longer double-counts `total_max` when an id is re-created per agent run | ✅ | `core/budget_protection.py` |
| 1B.22 | Cross-process pipeline control (stop/pause/resume) via `control.json` + real start/restart API | ✅ | `core/pipeline_executor.py`, `api/pipeline.py` |
| 1B.23 | Tier selection + details (`--tier-list`/`--tier-info`, `GET /api/tiers`, `/api/tier/<name>`) | ✅ | `model_router.describe_tiers`, `run_pipeline.py`, `api/router.py` |
| 1B.24 | Operations/state/API reference | ✅ | `docs/PIPELINE-OPERATIONS.md` |
| 1B.25 | Interactive tier prompt at start + `actual-balanced` quality profile | ✅ | `run_pipeline.py` (TTY prompt, persists `model_tier`), `model-tier.json` profile |
| 1B.26 | Standardized status + dependency model across phase/stage/agent; selective rerun with downstream invalidation; resume restores stage states | ✅ | `core/orchestrator/status.py` (pending/blocked/running/completed/failed/skipped/stale/needs_retry/escalated), `dag_executor` (blocked/stale, restore, invalidate_downstream), `invalidate_for_rerun`, `--agent`/`--only-stage`/`--from-stage`, `GET /api/pipeline/status` |
| 1B.27 | Agent-level operations (run/rerun/retry a specific agent) + persistent run-scope + control API | ✅ | `invalidate_for_rerun(agents=...)` agent-mode with within-stage `agent_dependencies` closure; `run-scope.json`; `POST /api/pipeline/rerun|retry`, `GET /api/agents/status`; doc §10 |
| 1B.28 | Deployment provider registry (docker/local/command + k8s/terraform/ansible/... aliases); production-deploy in Stage 11; post-deploy apply->verify->teardown | ✅ | `core/deploy_providers.py`, `deploy_smoke.py`, `stage_runner`, `report.post_deploy` |

---

## PART 2 — DONE (reference)
- **Tech-stack decision flow:** architect emits a structured `docs/tech-stack.json` (kind/languages/frameworks + requested/changed/rationale); `core/tech_stack.py` parses it, detects requested stack from the idea, maps stack → knowledge layers (knowledge follows the decision), scope-guards by the chosen stack, **gates when the architect changes the user's request**, and a **stack-compliance check** flags unrequested frameworks.
- Framework-agnostic agent layer: `AgentSpec` + `ToolRegistry` + native tool loop; specs for 53 agents; prompts from specs.
- Output requirements restored (F-n features / FR- / ADR-) + explicit "write real files" guidance.
- Tool-loop hardening: `require_write_first` (only `write_file` exposed until a write), **deny** disallowed tools with a corrective error, repeat detection, per-agent tool-token cap, fail code agents with **0 writes**.
- Tool-agent prompts use a focused directive (not the opencode card) to avoid `Task`/sub-agent confusion; rate-breaker default raised to 400k/min.
- Verification runner + no-mock gate wired into `execute_agent`.
- Iteration naming ("Implementation Iteration N") + realistic stage budgets; delegation messenger wired; `core/orchestrator/{storage,types}.py` extracted.
- Model routing config-driven (shared `model-tier.json`), removed hardcoded models.
- DAG dependency fix (`runs_after`/`depends_on`) + `1b∥1c`, `5∥6` parallel groups + thread-safe.
- Per-agent/per-stage start/end/duration in audit + report + live log.
- Knowledge domain map + guideline loading fix.
- Canonical compliance artifacts (`docs/*.md`, `project-config.json`, `agent-audit.md`).
- Contracts recalibrated; prior truncation eliminated on normal outputs.
- Iteration stages extended to `4a–4f`; feature-subset planning; skip-unused.
- New config docs in `docs/HOW-TO-START-NEW-PROJECT.md`.
- Scratch scripts moved to `scripts/dev/`.

---

## PART 3 — PENDING within / right after the major change
| # | Item | Status |
|---|---|---|
| 3.1 | Wire `compliance_verifier` (LLM-as-verifier) | ✅ | Opt-in (`enable_llm_verification` / `ENABLE_LLM_VERIFICATION`); routed through `ModelRouter` (no hardcoded endpoint/key/model), JSON-first parsing, artifact contents embedded, high-confidence failures merged into compliance. E2E verified on free tier (`[LLM-VERIFY] design: 3 high-confidence failure(s)`) |
| 3.2 | Feature-status tracking per feature (`ProductPlan`) + `feature-status.md` | ✅ | `FeatureTracker` (`core/orchestrator/feature_tracker.py`) seeds features and updates status across stages (planned->completed->verified); persists `product-plan.json` + `architecture/product-plan.md` |
| 3.3 | Compact per-stage summaries (salvage from `/pipeline`) | ✅ | `ProjectJournal.write_compact_summary` wired via `CheckpointWriter.write_stage` |
| 3.4 | `agent-context.md` maintenance (journal) | ✅ | `ProjectJournal.write_agent_context` wired via `CheckpointWriter.write_stage` |
| 3.5 | Pass a messenger to `DelegationRouter` | ✅ (safe enable pending) |
| 3.6 | Wire `prompt_cache` / `tool_cache` | ✅ | `ToolResultCache` wired into `execute_agent_tool` (read-only cached; write invalidates; `run_command` marked non-cacheable). `prompt_cache` superseded by existing `LLMCache` (same role) |
| 3.7 | Cost-per-successful-outcome KPI (`cost_kpi`/`finops`) | ✅ | `CostKPITracker` records each agent task (success/tokens/cost); CPS included in `pipeline-execution-report.json` + printed in summary |
| 3.8 | Wire reliability: `llm_error_handler`, `dead_letter_queue`, `lock_manager`, `notification_system` | ✅ | DLQ + LLM error log on agent failure; notifications on stop/time/emergency/failure/completion; `LockManager` prevents concurrent runs (entrypoint) |
| 3.9 | `ProductPlan` feature-level tracking across the run | ✅ | Wired in `stage_runner._track_features_for_stage` (implement/validate/security/code-review); health in report + summary; fixed metadata to count `verified` |
| 3.10 | **Standardize agent cards** from `AgentSpec` → 0–8 standard | ✅ **applied** (53/53 conform, tier-based `model:`, verified instructions retained; originals backed up at `.opencode/agent_backup_pre_std`) |
| 3.11 | Align executor outputs to schemas; add `project.v1` | ✅ audit entry (entry_id/agent/stage/action) + `audit-log-entry.v1` extended; `pipeline-state.json` → `pipeline-state.v1`; compliance report `spec_version`; **`project.v1` added** |
| 3.12 | Standardize checkpoint docs (`agent-context.md`, `feature-status.md`, compact per-stage summaries) + wire them | ✅ `ProjectJournal.write_agent_context/write_feature_status/write_compact_summary` wired into stage completion |

---

## PART 4 — SEPARATE BACKLOG (after the major change)
These come from the `.md` plans and are **not** part of the current change set.

| # | Item | Source |
|---|---|---|
| 4.1 | Test Framework integration (run suites per phase) | ✅ | `core/test_framework_bridge.py` reads `test-framework/config/test-suites.yaml`; maps stage->mode/categories; `verification_runner.run_verification(stage_id, use_suites=True)` selects per-category test dirs. Opt-in via `enable_test_suites` / `ENABLE_TEST_SUITES` |
| 4.2 | Multi-model review for architecture/design | ✅ | `core/multi_model_review.py` sends design/architecture artifacts to up to 3 tier models and aggregates majority verdict + issues; wired into compliance for `design`/`architect` (opt-in `enable_multi_model_review` / `ENABLE_MULTI_MODEL_REVIEW`) |
| 4.3 | NFR strategy + coverage execution | ✅ | `core/nfr_coverage.py` extracts NFR ids from requirements/design/architecture and checks test references; coverage in report + summary. NFR-mode suites run via 4.4-4.6 |
| 4.4 | Real Security scan execution (SAST/DAST/SCA) | ✅ | `core/nfr_runner.run_security` runs `npm audit`, `bandit`, `pip-audit` when present (run-if-present, allow-listed); invoked for nfr-mode verification |
| 4.5 | Packaging execution (real build artifacts) | ✅ | `core/nfr_runner.run_packaging` runs npm build/pack, `python -m build`, `docker build` (Dockerfile) for packaging-mode verification |
| 4.6 | a11y / performance execution as gates | ✅ | `core/nfr_runner.run_gates` runs `test:a11y` / `test:perf|test:load` package.json scripts when present; results feed compliance |
| 4.7 | Port configuration + state-file ownership | ✅ | `_derive_ports` writes `docs/ports.json` from the agreed tech stack (`core/port_config.py`) at architect finalize; checkpoint writes are now atomic (`os.replace`) and `pipeline-state.json` is single-writer (orchestrator) + LockManager |
| 4.8 | Architecture completeness checklist | ✅ | `core/architecture_checklist.py` verifies the architect output covers all required sections (fuzzy heading match); wired into compliance for `architect` |
| 4.9 | Wire `phase3_advanced` + `loop_modes` (reasoning/tool-compression) | ✅ | `ToolResultCompressor` (tool results), `AdaptiveReasoningController` (tool-loop depth), `SemanticCache` (opt-in), `KnowledgeGraph` (opt-in `ENABLE_KNOWLEDGE_GRAPH`, knowledge augmentation), `LoopController` (exposed via `executor.run_loop`) |
| 4.10 | Epic/Scrum planning layer (epics -> iterations, `planning_mode`) | ✅ | `extract_features` parses epics (heading or `[epic: X]`); `plan_iterations(group_by_epic=...)` groups by epic; `planning_mode` (`epic`|`feature`) via project.json |
| 4.11 | Dashboard UI rebuilt from scratch (via the pipeline itself) | ⏸️ | Deferred — separate project (build the dashboard by running the pipeline on it), not a pipeline fix |
| 4.12 | Decide fate of unwired modules + legacy orchestrators | ✅ | Scan (`scripts/dev/find_unused_modules.py`) + decisions in `docs/UNWIRED-MODULES-TRIAGE.md` (wire-next / optional-lib / deprecate / housekeeping) |
| 4.13 | Large `PIPELINE-IMPLEMENTATION-PLAN.md` gap backlog (64 gaps) | ✅ triaged | See `docs/4.13-GAP-TRIAGE.md`: most gaps DONE/superseded by current work; shortlist of high-value remaining (layered impl, AGENTS.md, test traceability, secrets validation, docs, deploy smoke, uiux-theme); rest NO/OPTIONAL |

---

## PART 5 — COMPLETE `.md` INVENTORY (all folders)
One truth for every markdown doc. Legend: **ACT** = feeds the current major change / pending · **SEP** = separate backlog · **REF** = research/reference/notes · **SUP** = superseded · **GEN** = generated artifact · **CARD/CMD/SKILL** = framework definitions · **SPEC** = spec/standard.

### 5.1 Root (grouped — moved 2026-09-10)
Root now contains only:
| File | Class | Relation |
|---|---|---|
| `README.md` | REF | project overview |
| `agent-audit.md` | GEN | audit log |
| `pipeline_execution_report_analysis.md` | GEN | sample run report |

**Moved to `docs/plans/`** (plans / backlogs / status):
| File | Class | Relation |
|---|---|---|
| `FOLLOWUP-Phase3-Wiring.md` | SEP | PART 4.9 (phase3/loop_modes) |
| `pending.md` | SUP | model-switch tasks (superseded) |
| `PRODUCT-FORGE-IMPROVEMENTS.md` | REF | history |
| `Multi-Agent-Enhancement-Roadmap.md` | SEP | roadmap backlog |
| `Multi-Agent-workflow.md` | REF | workflow notes |
| `product_factory_complete_orchestration_model_strategy.md` | REF/ACT | strategy (feeds tiers/budgets) |
| `product_factory_conversation_ingestion_architecture.md` | REF | ingestion design |
| `loopmode.md` | SEP | loop modes (4.9) |
| `factory-mcp-and-tools.md` | ACT | feeds ToolRegistry/tools (1A.2) |
| `factorychecklist(1).md` | REF | checklist |
| `AUTOMATION_GUIDE.md` | REF | usage guide |

**Moved to `docs/research/`** (research / reference):
| File | Class | Relation |
|---|---|---|
| `LLM_MultiAgent_Token_Resource_Optimization.md` | REF/ACT | feeds cost work (1B.x) |
| `compiled_second_brain_autonomous_agent_team.md`, `multi_agent_system_lessons.md`, `Auto-Company - Adoptable Patterns for AI Product Forge.md` | REF | research |
| `ai-agent-book-multi-agent-leverage.md`, `anthropic_cybersecurity_skills_multi_agent_leverage.md`, `one_person_ai_company_multi_agent_leverage.md`, `product-on-purpose-multi-agent-leverage.md`, `spec-kit-multi-agent-leverage.md`, `system-design-academy-multi-agent-leverage.md` | REF | research |
| `LLM_Models_Benchmark.md` | REF | model benchmark |
| `ruflo_ai_control_os_analysis.md`, `AIrepos.md`, `knowledgecourse.md`, `vibe-coding-prompt-template-summary.md` | REF | notes/links |

### 5.2 docs/
| File | Class | Relation |
|---|---|---|
| `CHANGE-PLAN.md` | ACT | **this file — master tracker** |
| `PIPELINE_IMPROVEMENT_PLAN.md` | SEP | source of PART 4.1–4.8 (linked) |
| `PIPELINE-IMPLEMENTATION-PLAN.md` | SEP | 64-gap backlog (4.13) |
| `AGENT_CONTRACT_STANDARD.md` | ACT | feeds `AgentSpec` (1A.1/1A.5) |
| `Agent-LLM-PromptHandling.md` | ACT | feeds prompt rendering (1A.6) |
| `token-audit.md` | ACT | feeds cost work (1B.x) |
| `HOW-TO-START-NEW-PROJECT.md` | ACT | updated with new configs |
| `Failure-Recovery-System.md` | SEP | reliability (3.8) |
| `DEVOPS-WORKFLOW-ANALYSIS.md` | SEP | devops/packaging (4.5) |
| `NFR-PIPELINE-STRATEGY.md` | SEP | NFR (4.3) |
| `NFR-COVERAGE-PLAN.md` | SEP | NFR (4.3) |
| `CONSTITUTION.md` | REF | rules/enforcement |
| `pipeline-architecture.md` | SPEC | architecture |
| `PIPELINE-TEMPLATE-SPEC.md` | SPEC | template schema |
| `SCHEMA-GUIDE.md` | SPEC | schemas |
| `Diagram-Generation-Spec.md` | SPEC | diagrams |
| `PIPELINE_WORKFLOW.md`, `PIPELINE-WORKFLOW-CORRECTED.md` | REF | workflow |
| `pipeline-quick-reference.md`, `pipeline-openflowkit.md`, `pipeline-diagrams-reference.md` | REF | reference |
| `Multi-Agent-Multi-Project-Unique-Features.md` | REF | roadmap notes |
| `input_needed.md`, `test.md`, `todo.md` | REF | scratch/notes |
| `agent-audit.md`, `agent-context.md`, `pipeline-state.md`, `feature-status.md` | GEN | runtime state (salvage 3.2/3.3/3.4) |
| `architecture.md`, `design.md`, `requirements.md`, `review.md`, `product-plan.md` | GEN | myworld artifacts |

### 5.3 core/
| File | Class | Relation |
|---|---|---|
| `core/orchestrator.md` | ACT | orchestrator rules (keep in sync with executor) |

### 5.4 .opencode/
| Path | Class | Relation |
|---|---|---|
| `.opencode/agent/*.md` (48) | CARD | source for `AgentSpec` (1A.5) |
| `.opencode/command/pipeline.md` | CMD | target of `/pipeline` adapter (1A.9) |
| `.opencode/command/models.md` | CMD | model tier command |
| `.opencode/skills/**/SKILL.md` | SKILL | skills catalog |
| `.opencode/model-tiers.md` | REF | tier reference |
| `.opencode/docs/product-type-classification.md` | REF | classification |

### 5.5 Other folders
| File | Class | Relation |
|---|---|---|
| `pipeline_dashboard/FOOTPRINT.md` | REF | dashboard notes |
| `pipeline_dashboard/LICENSE_ANALYSIS.md` | REF | licenses |
| `pipeline_dashboard/pipeline_overallreview.md` | REF | review |
| `pipeline_dashboard/updated_workflow.md`, `WORKFLOW_WALKTHROUGH.md` | REF | workflow |
| `adapters/*/README.md`, `adapters/instructions.md` | REF | adapter notes |
| `pipeline_templates/README.md` | REF | templates |
| `test-framework/README.md` | REF | test framework (4.1) |
| `reports/*.md`, `security/*.md` | GEN | myworld reports |

> Excludes `node_modules/`, `.backups/`, `.git/`, `products/` generated docs beyond the ones listed.

### 5.6 Grouping (done 2026-09-10)
Root docs grouped into **`docs/plans/`** (plans/backlogs/status) and **`docs/research/`**
(research/reference). Root now holds only `README.md` + generated artifacts.
Reference check: no code referenced the moved files (the `loopmode` grep hit was a
`LoopMode` class, not a file link). If any doc-to-doc links break, fix relpaths.

---

## PART 6 — UNWIRED MODULE INVENTORY (103 modules; 35 wired)
**Wired indirectly (fine):** `agent_ledger`, `state_machine` (via journal), `pipeline_telemetry` (via journal/API), `budget_planner` (via API).

**Not wired — real gaps:** `compliance_verifier`, `code_executor`, `build_utility`, `git_manager`, `docker_compose_generator`, `release_manager`, `mobile_tester`, `version_manager`, `port_config`, `prompt_cache`, `tool_cache`, `llm_error_handler`, `dead_letter_queue`, `lock_manager`, `queue_manager`, `notification_system`, `cost_kpi`, `finops`, `cost_modeling`, `budget_allocator`, `phase3_advanced`, `loop_modes`, `skills_registry`, `business_skills_selector`, `model_recommendation`, `service_catalog`, `byot_integration`, `product_plan`, `traceability`, `workflow_docs`, `audit_trail`, `change_registry`.

**Legacy / parallel (decide fate):** `global_orchestrator`, `factory_supervisor`, `pipeline_engine`, `product_analyzer`, `product_ingestion`, `intake_api`, `intent_router`, `conversation_*`.

---

## PART 7 — DEFINITION OF DONE (major change)
The major change is complete when:
1. Agents produce **real files** (no markdown-only) for implementation/devops/validate.
2. `validate` **runs** tests/build and fails if artifacts/tests are missing.
3. A **no-mock/no-stub gate** blocks scaffolding.
4. Every pipeline agent has an **`AgentSpec`** (prompt + tools + contract) — union of opencode + Python.
5. `/pipeline` drives the **generic** orchestrator (no prompt-embedded orchestration).
6. One fresh E2E (with a real `idea`) shows: real files, tests executed, no truncation, budget within soft, iterations skipped correctly, journal + telemetry + alerts populated.


---

## PART 8 — FOLLOW-UP SESSIONS (reminders)

> These are **intentionally deferred to dedicated sessions**. Do not lose them.

### 8.1 🎯 Model / tier tuning session (PRIORITY — separate session)
**Why:** the run profiles need a deliberate, evidence-based decision (not ad-hoc).
**Inputs to use:** `docs/modelanalysis.md` (capability matrix + per-tier recommendations),
health-check results (throttled free models), `products/pipeline_dashboard/model-tier.json`.
**Do:**
- Decide the correct **models per agent** for each tier: `actual-balanced` (quality),
  a **cheap paid** tier, **OpenCode Go paid**, **OpenRouter paid**, and `free-trial`.
- Confirm `active_tier` default and whether `actual-balanced` should replace `actual`.
- Validate each tier end-to-end (free-tier already 100%; run paid tiers when funded).
- Keep every referenced model in the profile `models` map (correct provider/endpoint).
**Deliverable:** finalized tier profiles + updated `docs/modelanalysis.md`.

### 8.2 Implementation E2E (DoD #1–3/#6)
Run `3 → 4-0 → 4a → 4a-vqa` and confirm: real files written, tests executed,
no-mock gate, feature tracking, iteration skip, governance/report populated.

### 8.3 PART 6 "wire-next" modules + housekeeping
Wire: `schema_validator`, `audit_trail`, `techstack_guidelines`, `business_skills_selector`,
`code_analyzer`, `service_catalog`, `agent_migrator`. Move stray `core/test_*.py` to `tests/`;
deprecate legacy modules (see `docs/UNWIRED-MODULES-TRIAGE.md`).

### 8.4 Optional: selective reruns
### 8.4 Selective reruns | ✅ implemented | `--agent` / `--only-stage` / `--from-stage` + downstream `stale` invalidation. (Optional follow-up: POST API for rerun; live per-agent `running` mid-agent)
Stage-level `--from-stage` / `--only-stage` and agent-level `--agent` re-run (the only
agent-level ops worth having; full per-agent lifecycle ops are overkill).
