# Implemented Features & Modules — Wiring Reference

> Purpose: for every feature/module we built, know **what it does, why it exists,
> whether it is WIRED into the pipeline, who calls it, and when it triggers**.
>
> Verify anytime with: `python scripts/dev/wired_audit.py` (exit 0 = no orphan modules).

## Legend
- **WIRED** = invoked on the runtime path (default-on).
- **OPT-IN** = wired but gated by a feature flag (default off) — see `core/feature_flags.py`.
- **GATE** = runs at a specific pipeline stage and can block.
- **TOOLING** = used by CLI/CI, not the pipeline runtime.
- **REPORT-ONLY** = computed and reported, not gating.
- **STUB** = interface present, backend not implemented.

`build.<n>`/version come from `core/build_manager.py` (single source of truth).

---

## 1. Test & QA system (P1–P9)

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `core/test_matrix.py` + `config/test-matrix.json` | Canonical test catalogue: requirement-type × layer → category → framework/path/runner; product-kind profiles; kits merge; FR/NFR spec-id extraction; BDD scaffolding | **WIRED** | `test_framework_integration.run_cycle`, `agent_runner` prompts, `qa_report`, `qir`, `verification_policy` | per cycle; per implement/validate prompt |
| `core/test_adapters.py` | Stack-agnostic test commands (python/node/go/rust/java/dotnet/php/ruby/flutter/desktop/command) | **WIRED** | `test_matrix`, `test_framework_integration` | when building the test command |
| `core/test_framework_integration.py` | Framework bridge: register project, run cycle, record results, log defects, app up/down, per-category runs, build gate | **WIRED** | `compliance` (11f), `pipeline_executor._run_test_cycle` | validate stages (4a–4f, 6, 7, 10a, 11) |
| `core/test_framework_bridge.py` | Stage → test mode/categories (smoke/feature/nfr/packaging/full) | **WIRED** | `test_framework_integration` | per stage |
| `core/nfr_runner.py` | Security/CVE, a11y/perf gates, packaging, install, **BOM**, smoke | **WIRED** | `test_framework_integration`, `deploy_providers`, `verification_runner` | nfr/packaging modes; deploy verify |
| `core/nfr_coverage.py` | FR/NFR id → test references (traceability + gaps) | **WIRED** | `compliance` (11h), `qa_report`, `qa_manifest` | validate stage |
| `core/qa_cycles.py` | QA-owned suites/cycles from the matrix per product kind; persists them | **WIRED** | `test_framework_integration.ensure_suites` | start of each cycle |
| `test-framework/kits/*/kit.json` | Extra test areas (usability, media, social, cloud, compliance, i18n, …) | **WIRED** | `test_matrix.load/register_kit` | when resolving categories |
| `test-framework/dashboard/*` | QA console (14 tabs) + summary APIs incl. `/api/quality/status` | **TOOLING** | served on port 3011 | when the console runs |
| `core/verification_policy.py` | Classify verification internal/external/not-run | **GATE** (Go/No-Go row "Verification coverage") | `qa_report.go_no_go`, `qa_manifest` | 10a gate + delivery |

## 2. Defect → fix → RCCA loop

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `core/defect_loop.py` | Open defects + RCCA → fix prompt; `reconcile` auto-closes on pass; `generate_tests` scaffolds | **WIRED** | `agent_runner` (defect brief), `run_cycle`, `pipeline_executor`, `qa_report/qir` | validate fail/pass; fix prompt |
| `test-framework/core/{defect_tracker,rcca}.py` | Defect store + root-cause analysis | **WIRED** | `run_cycle`, `defect_loop` | when a test fails |
| `pipeline_executor._review_fix` | Reviewer (`code-review`) must approve a fix; else `needs_retry` | **GATE** | `agent_execution.execute_agent` | when `fix` completes |
| `pipeline-definition.json` `fix` flow | `fixed → code-review → validate` | **WIRED** | orchestrator routing | after a fix |

## 3. Platform testing & deployment

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `core/deploy_providers.py` | Providers: docker/local/command/**kubernetes/helm/terraform/ansible**/cloud + **vendor targets**; apply→verify→destroy; `run_deploy_up/down`; runs vendor/lab steps | **WIRED** | `test_framework_integration` (lifecycle), `stage_runner` post-deploy, CI templates | UI/e2e suites; deploy stage |
| `core/vendor_adapters.py` | Vendor integration adapters + **lab handles** (vmware/dell/hp/cisco/netapp/s3/aws/azure/gcp/postgres/oracle); command-driven; external verification | **WIRED** | `deploy_providers` (`run_deploy_up`, `select_provider`) | deploy step (when `docs/infra.json` lists vendors) |
| `core/signing.py` | GPG signing — **both** key sources (org secret env / HIL-provided); signs tags + artifacts; graceful fallback | **WIRED** | `vcs.tag`, `build_manager` (artifact signing) | RC/release tags; every build |
| `core/architecture_diagram.py` | Emits `architecture.mermaid` + `.drawio` from `architecture.md` (5.5) | **WIRED** | `stage_runner` | after stage `2` (architect) |
| `nfr_runner` security pack | `run_zap` (6.3), `run_tls` (6.7), `run_dos` (6.8, opt-in), `run_installers` (7.1), `package_contents`+`run_bom` (7.2/7.3), `write_footprint` (7.4), `run_install_verify` (7.5–7.7) | **WIRED** | `run_security`/`run_packaging` | security/packaging modes |
| plan docs enforcement | `uiux-theme.md` (5.6), `INSTALL/USER_GUIDE/API_GUIDE` (9.1–9.3), in-app help (9.4) | **WIRED** | `prompt_builder`, `config/agent-requirements.json`, `output_checklist` | architect/ux-ia/document/implement-ui |
| `--step` / `--control` | 1.3 per-agent pause; 1.7 exit/stop/pause/resume | **WIRED** | `run_pipeline.py` → executor, `stage_runner` | run/interactive; cross-process |
| `core/mobile_tester.py` | iOS/Android simulators/emulators + Stowaway/Vitest-mobile/Maestro | **WIRED** | `run_cycle` mobile block | mobile products |
| `core/qa_intelligence.py` | Evidence-based trends: clustering/aging/regression/instability/root-cause | **WIRED** | `run_cycle`; `pipeline_executor` notification | every cycle |
| `core/qir.py` | Project QIR: number + ISO 25010 profile + trend | **WIRED** | `qa_report.go_no_go`; console; manifest | GO/NO-GO; delivery |
| `core/qa_report.py` | Go/No-Go matrix (incl. Spec Review) + per-cycle coverage report | **GATE** | `compliance` (11j, stage **10a**) | before deploy |
| `core/qa_manifest.py` | Aggregates QA artifacts + static snapshot + delivery index | **WIRED** | `reporting.generate_final_report` | end of run |
| `core/spec_review.py` | QA review of design/architect artifacts; blocking/optional; resolution tracking | **GATE** | `pipeline_executor._run_spec_review` → `compliance` (11i, stage **3a**) | before implementation |

## 4. Build, versioning, git, CI/CD

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `core/build_manager.py` | SemVer + monotonic **build number**, release notes, changelog, artifact publish + **GPG signing** | **WIRED** | `run_cycle` (build gate), `vcs` tags, CI templates | every cycle/build |
| `core/artifact_registry.py` | Content-addressed artifacts (+sha256); **local + real external backends** (s3/gcs/azure/oci/http/custom cmd) | **WIRED** | `build_manager._publish_artifacts`, `get_registry` | on build (backend via `project.json → artifact_registry`) |
| `core/vcs.py` | Branch/commit/push/rebase/stash/merge/**tag**, WIP snapshot, **checkins()** — orchestrator-owned | **WIRED** | `pipeline_executor._vcs_*`, `stage_runner`, CI | stage start (branch), stage end (commit→develop, gated), staging (RC tag), 10a (release) |
| `core/pr_gate.py` | PR merge checklist: code_review, review_changes_done, **db_tests**, **api_tests**, unit_tests, lint, ui_e2e + **HIL-only override** | **GATE** | `vcs.merge`, CI, console `/api/pr-gate` | every merge |
| `templates/ci/{github-actions,gitlab-ci}.yml` | CI/CD pipeline (lint/static/secrets/unit → build/version/notes/SBOM/CVE → artifact+md5+GPG → staging+**RC tag** → tests → Go/No-Go → **release tag** on main) | **TOOLING** | CI platform | on push/merge |
| `scripts/dev/wired_audit.py` | Orphan-module audit; **CI gate** | **TOOLING** | CI + humans | every CI run |
| `scripts/dev/{migrate_agents,service_catalog}.py` | Dev CLIs | **TOOLING** | humans | on demand |

## 5. Repo/pipeline integration, gates & intelligence

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `core/feature_flags.py` | Governance precedence (HIL > project > choices > recommendation > env > default) | **WIRED** | `agent_runner`, `pipeline_executor`, `qa_manifest` | every gated decision |
| `core/integration_advisor.py` | Pipeline intelligence: recommends integrations in plain language; impact classification; HIL only when product-affecting | **WIRED** | `stage_runner._recommend_integrations` | first stage |
| `core/audit_trail.py` | Durable/queryable audit stream | **WIRED** | `agent_execution` (start/complete/fail) | each agent run |
| `core/integration_advisor` + flags | Opt-in integrations: `business_skills`, `service_catalog`, `code_analyzer`, `spec_llm` | **OPT-IN** | `agent_runner` directives | when enabled |

## 6. Extended capabilities (wired this pass)

Invoked once per run by `pipeline_executor._run_extended_capabilities` →
`core/pipeline_capabilities.run` (persists `docs/qa/extended-capabilities.json`).
`write_safety` is also used on the manifest/tool write path.

| Module | What it does / Why | Wiring | Trigger |
|---|---|---|---|
| `git_manager` | Git snapshot/status | **WIRED** | run start (when a repo exists) |
| `model_recommendation` | Suggest model for a task | **WIRED** | run start |
| `byot_integration` | Bring-your-own models/tools report | **WIRED** | run start |
| `domain_research` | Domain trends/best practices | **WIRED** | run start (when domain known) |
| `cost_modeling` | Infra cost estimate | **WIRED** | run start |
| `finops` | Budget/optimization report | **WIRED** | run start |
| `change_registry` | Change records/impact | **WIRED** | run start |
| `release_manager` | Release records/strategy | **WIRED** | run start / release |
| `traceability` | Traceability matrix object | **WIRED** | run start, manifest |
| `maintenance` | Health check/report | **WIRED** | run start |
| `customer_onboarding` | Onboarding package | **WIRED** | run start |
| `presentation_generator` | Presentation/marketing package | **WIRED** | run start |
| `video_generation` | Demo video script | **WIRED** | run start |
| `product_analyzer` / `product_ingestion` | Analyze/ingest an existing product | **WIRED** | run start (when `src/` exists) |
| `write_safety` | Atomic/safe writes (backup/lock) | **WIRED** | manifest/tool writes |

> All 16 capabilities are invoked and **succeed (16/16)** when their preconditions
> exist (e.g., a git repo for `git_manager`, a `src/` dir for analyze/ingest); failures
> are recorded per-capability (`ok`/`error`).

---

## 7. Gates in the pipeline (who blocks what)
| Gate | Stage | Blocks |
|---|---|---|
| QA **Spec Review** | `3a` | implementation (`4-0`) until blocking findings cleared |
| Build gate | validate stages | tests require a build (`build_manager`) |
| QA **Go/No-Go** | `10a` | deploy (`11`) on NO-GO (HIL override: `qa.override_gonogo`) |
| Reviewer (fix) | after `fix` | fix acceptance until `code-review` approves |
| Release HIL | `10a` | `develop → main` until HIL approved |
| Wired-audit | CI | merge on orphan modules |

## 8. Config & data contracts
- `config/test-matrix.json` (catalogue), `config/qa-weights.json` (QIR), `config/qa-status.json` (RAG rules).
- `products/<p>/{build-info.json,builds/,CHANGELOG.md,docs/releases/,docs/qa/,qa-manifest.json,recommendations.json,integration_choices.json}`.
- `test-framework/results/<p>/{metrics,trends,features,traceability,cycles,qir,qir-history,insights,spec-review,go-no-go,coverage-*}.json`; `test-framework/defects/<p>/{defects.json,rcca/}`.
- `docs/GIT-CI-CD.md` (git/CI/CD workflow + diagram), `docs/QA-QUALITY-SYSTEM.md` (QA system).

## 9. Wiring update (this task)
- **Newly wired:** `video_generation`, `video_script` (via `pipeline_capabilities`); extended-capabilities pass wired into the run; `write_safety` on the write path.
- **Previously wired this session:** `vcs` (4 triggers), `spec_review`/`qa_report` (gates 3a/10a), `build_manager`, `artifact_registry`, `qa_cycles`, `qa_intelligence`, `qir`, `qa_manifest`, `defect_loop`, `test_matrix`, `test_adapters`, `deploy_providers`, `mobile_tester`, `feature_flags`, `integration_advisor`, `audit_trail`, `nfr_runner(CVE/BOM)`.
- **Audit:** `scripts/dev/wired_audit.py` → **0 orphans** (not allowlisted).

## 10. Interactive prompt bridge (TTY-less) — BI-0026

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `core/interactive.py` | Relays runtime prompts to a file channel so the pipeline runs interactively without a TTY: `ask()` returns `input()` on a TTY, the **default** when off/non-TTY, or writes a pending prompt to `interactive/prompts.json` and polls the answer when `PIPELINE_INTERACTIVE=1` | **OPT-IN** (`run_pipeline.py --interactive` / `PIPELINE_INTERACTIVE=1`) | `scripts/run_pipeline.py:_ask` (project/idea/tier/enhance goal), `pipeline_executor._resolve_integrations`, `target_selector.select`, `enhance.enhance`, `stage_runner` (`--step` pause) | whenever an interactive prompt is reached |

- **Answer from a harness:** `python -m core.interactive --project <p> --list` · `--answer <id> "<value>"`.
- **Owner store:** `prompts.json` (kind=control; `products/<p>/interactive/`, or `products/.interactive/` before a project exists) — single writer = `core/interactive.py`.
- **Preserves terminal behaviour:** bridge off => identical defaults; TTY => `input()`. Additive only.
- **Test:** `test-framework/tests/pipeline/test_interactive_bridge.py`.

## 11. E2E progress banner — BI-0027

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `core/progress.py` | Prints "where are we" — phase (of 7), stage (of N), agent (of M) + overall agent count, status, gate, tokens, target, and **what's next** | **WIRED** | `pipeline_executor._show_progress` `<-` `stage_runner` (agent start + end) | every agent execution; also `python -m core.progress --project <p>` |

- **Reads only:** `pipeline-definition.json`, `<p>/agents-live.json`, `<p>/pipeline-state.json`, `<p>/budget.json`, `<p>/project.json`. No store owned.
- **Test:** `test-framework/tests/pipeline/test_progress.py`.

## 12. Invocation audit + design-phase wiring — BI-0028 / BI-0029

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `scripts/dev/invocation_audit.py` | **Reachability** audit: a core module must be reachable from the real entrypoints (direct calls **or** the `pipeline_capabilities` dispatch table). Catches "imported but never invoked" (unused `# noqa: F401` imports) that the substring scan reports as wired | **GATE** | `scripts/dev/wired_audit.py` (last check) → CI + `pr_gate.structure_contract` | every audit / PR |
| `core/discovery_engine.py` | 360° multi-role discovery: Product Analyst + Business Analyst + UX Researcher, 18 agent-specific questions | **WIRED** | `pipeline_executor._run_design_augmentations` (stage `0a`) | stage 0a |
| `core/product_design_spec.py` | Product design spec extracted from artifacts | **WIRED** | `_run_design_augmentations` (stage `1a`) | stage 1a |
| `core/design_tokens.py` | Design tokens (colors/type/spacing) + CSS custom properties | **WIRED** | `_run_design_augmentations` (stage `1c`) | stage 1c |
| `core/dashboard_archetypes.py` | Dashboard archetype selection + section/layout report | **WIRED** | `_run_design_augmentations` (stages `1`/`2`) | design + architect |

- **New artifacts:** `discovery-questions.json`, `docs/design-spec.json`, `docs/design-tokens.json`, `docs/dashboard-archetype.md`.
- **Allowlist (with reasons):** `scripts/dev/invocation_audit.py:ALLOW` — 18 modules (deprecated / tooling / optional).
- **Test:** `test-framework/tests/pipeline/test_invocation_audit.py`.
- **Triage record:** `docs/UNWIRED-MODULES-TRIAGE.md` → "reachability re-triage".
- **Status report:** `docs/MODULE-STATUS.md` (all 179 core modules, regenerated by `--report`).

### Wired to reach UNWIRED: 0 (BI-0030)
| Module | Wired at | Surface |
|---|---|---|
| `marketing`, `build_utility`, `docker_compose_generator`, `memory_api`, `agent_card_loader`, `code_executor` | `core/pipeline_capabilities.py` (extended-capabilities probes) | RUNTIME |
| `intake_api` (`/api/intake/instructions`), `websocket_manager` (`setup_ws_events` + `/api/ws/events`) | `dashboard/server.py` | CLI |

**Final classification (176 core modules):** UNWIRED **0** · RUNTIME 152 · CLI 20 ·
TOOLING 3 · ENTRYPOINT 1 · DEPRECATED **0**.

**Removed (BI-0032):** `forge_supervisor`, `human_controls`, `pipeline_engine` — superseded
by `PipelineExecutor` + `core/orchestrator/*`; references fixed in `core/__init__.py`,
`core/pipeline_executor.py`, `core/squad_manager.py`, `pipeline_dashboard/{core_bridge,api}`,
and the obsolete root tests (`tests/test_e2e_pipeline.py`, `tests/test_integration.py`).

**Agent-card validator (BI-0031):** `core/agent_card_loader.py` required frontmatter `name`,
but the opencode card contract uses `agent_id` → all 53 cards reported invalid. Validator now
accepts `name` **or** `agent_id`; **53/53 valid** (0 errors).

## 13. 360° discovery panel — BI-0035 / BI-0036

| Module | What it does / Why | Wiring | Called by | Trigger |
|---|---|---|---|---|
| `core/discovery_panel.py` | Builds the 360° panel: one clarifying-question group per major agent (each lead representing its sub-agents from `config/agent-hierarchy.json`), every question carrying the agent's **recommended** answer the human accepts or overrides. Offline fallback = curated questions. Owner of `discovery-panel.json`. | **WIRED** | `pipeline_executor._run_design_augmentations` (stage `0a`) → `_ask_panel` | stage 0a |
| `core/discovery_engine.py` | `run_discovery(answers=)` + `synthesize_refined_idea()` → crisp brief | **WIRED** | same (stage 0a) | stage 0a |
| `core/interactive.py` | `ask()` one-by-one, role-attributed (recommendation = default) | **WIRED** | `pipeline_executor._ask_panel` | stage 0a (interactive) |
| `core/orchestrator/stage_runner.py` | Injects the refined clarifications into the discovery agent task so Design/Architect consume the crisp brief | **WIRED** | `run_stage` (stage `0a`) | stage 0a |

- **Config:** `config/discovery-panel-settings.json` (19 lead agents, `include_sub_agents: true`, `max_questions_per_agent: 3`).
- **New artifacts:** `discovery-panel.json` (intake-raw), `docs/idea-refined.md`, refreshed `docs/product-plan.md`; `discovery-questions.json` now carries recommendations + answers.
- **Tests:** `test-framework/tests/pipeline/test_discovery_panel.py`.
- **Follow-ups:** BI-0037 (round-2 follow-ups), BI-0038 (dashboard dialogs), BI-0039 (prompt_builder/artifacts_map direct consume).
