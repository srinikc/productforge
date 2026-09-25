# Product Forge — Documentation

> Index + quickstart. Start here, then follow the links.

## What it is
Product Forge is a **generic, framework-agnostic pipeline**: you give it a product idea, and a
DAG of LLM **agents** produces a real, verified project (planning → design → architecture →
implementation → review/security → validation → docs/packaging → deploy), with cost/compliance
governance and resumable state.

## Quickstart
```bash
# list model tiers
python scripts/run_pipeline.py --project <name> --tier-list
# show a tier's per-agent models
python scripts/run_pipeline.py --project <name> --tier-info free-trial
# run (new project with an idea)
python scripts/run_pipeline.py --project myapp --idea "a CLI that converts CSV to JSON" --tier free-trial
# resume (same command, no --idea)
python scripts/run_pipeline.py --project myapp --tier free-trial
# selective rerun (agent or stage) + downstream invalidation
python scripts/run_pipeline.py --project myapp --agent architect --only
```

## Configuration reference
| File | Purpose |
|---|---|
| `project.json` | per-project: `idea`, `model_tier`, `enable_tools`, `enable_*` flags, `budget`, `deploy` block |
| `products/pipeline_dashboard/model-tier.json` | tier profiles (`actual`, `actual-balanced`, `free-trial`) → per-agent models + fallbacks |
| `config/agent-requirements.json` | verbose agents, continuation budgets, generation strategy, **required output sections** |
| `pipeline-definition.json` | the DAG (stages, agents, deps, approval gates, parallel groups) |
| `docs/tech-stack.json` | architect's agreed stack (languages/frameworks/deploy/runtime) |
| `docs/ports.json` | derived service ports (used by deploy health-check) |
| `AGENTS.md` | per-project rules for all agents (auto-generated) |
| `<project>/control.json` | cross-process stop/pause/resume |
| `<project>/run-scope.json` | one-shot selective run scope |
| `.env` | API keys / credentials (referenced by name only) |

## Key documents
| Doc | What |
|---|---|
| `docs/CHANGE-PLAN.md` | **master tracker** — everything done/pending/deferred |
| `docs/DEPLOY-INFRA-ARCHITECTURE.md` | deployment/infra/vendors architecture + can/can't + extension |
| `docs/ORCHESTRATION.md` | control plane (runtime) vs judgment plane (Coordinator); stage-by-stage E2E |
| `docs/PORTFOLIO-ORCHESTRATION-DESIGN.md` | portfolio (global) vs project controller; substrate A/B/C/D; naming; compatibility |
| `docs/ENTRYPOINTS.md` | which script to use (`run_pipeline.py` vs `pipeline.py`; `run_portfolio.py`) |
| `docs/PIPELINE-OPERATIONS.md` | run modes, control, state files, status model, control API |
| `docs/modelanalysis.md` | model capability matrix + per-tier recommendations |
| `docs/HOW-TO-START-NEW-PROJECT.md` | step-by-step to start a project |
| `docs/RE-RUN-IMPACT-ANALYSIS.md` | dependency/rerun invalidation model |
| `docs/SECTIONED-GENERATION-ANALYSIS.md` | long-output (sectioned) generation design |
| `docs/4.13-GAP-TRIAGE.md`, `docs/UNWIRED-MODULES-TRIAGE.md` | backlog/value triage |
| `docs/AGENT_CONTRACT_STANDARD.md` | AgentSpec / contracts |

## Implemented capabilities (highlights)
- **Agent execution**: `AgentSpec` (53 agents) + `ToolRegistry` tool loop (native function-calling) → real files; planners stay markdown.
- **Model tiers**: config-driven, multi-provider (OpenCode Zen + OpenRouter), free-trial tier; single-first with sectioned fallback; fallback iteration + fast-fail on 429.
- **Governance**: budgets, run-breaker, telemetry, cost KPI, journal/state, checkpoints, DLQ, notifications, locks.
- **Compliance**: no-mock/stub gate, secrets scan, knowledge/guideline, architecture/design/ideation completeness (essential vs recommended), stack compliance, LLM-as-verifier, multi-model review, real test verification.
- **Iterations & features**: dynamic iteration planner, epic grouping, feature tracking (`product-plan.json`).
- **Status & control**: standardized `pending/blocked/running/completed/failed/skipped/stale/needs_retry/escalated`; resume restores state; selective rerun with downstream invalidation; CLI + API.
- **Deploy**: provider registry (docker/local/generic-command + aliases); post-deploy apply→verify→teardown; packaging/security/smoke runners.
- **Platform testing**: stack-agnostic adapters (web/desktop/mobile + python/go/rust/java/dotnet/php/ruby/flutter + command fallback); app brought up/down around UI/e2e; iOS/Android simulators & device farms; test cycle + defects + traceability.
- **Test generation & traceability**: `implement`/`validate` prompts require real FR/NFR-tagged tests (no `pass`/`skip`); optional `TestGenerator` scaffolds are generated and flagged for the agent to fill (`test.generate`); validate computes FR/NFR test coverage and can fail on gaps (`test.enforce_coverage`).
- **Defect loop**: failing tests log defects (`DefectTracker`); RCCA derives root-cause + prevention; open defects + prevention are injected into the `fix` (and implement/code-review/validate) prompts; fixes must be **approved by the reviewer (`code-review`) agent** before acceptance; passing re-runs auto-`verify`/`close` defects.

## Where things live
| Area | Path |
|---|---|
| Orchestrator | `core/pipeline_executor.py` + `core/orchestrator/*` |
| Agent layer | `core/agent_spec.py`, `core/tool_registry.py`, `core/agent_tool_loop.py` |
| Agents (specs) | `agents/*.agent.json` |
| Tiers/models | `products/pipeline_dashboard/model-tier.json`, `core/orchestrator/model_router.py` |
| Governance | `core/{budget_planner,run_breaker,pipeline_telemetry,project_journal,delegation}.py` |
| Compliance/quality | `core/{compliance_check,knowledge_compliance_checker,code_quality_gate,output_checklist,architecture_checklist,multi_model_review,compliance_verifier}.py` |
| Verification/deploy | `core/{verification_runner,nfr_runner,nfr_coverage,deploy_providers,deploy_smoke}.py` |
| API/dashboard | `pipeline_dashboard/api/*`, `pipeline_dashboard/serve.py` |
| Entry points | `scripts/run_pipeline.py`, `scripts/pipeline.py` |

## Notes
- Some `docs/*.md` (e.g. `PIPELINE_WORKFLOW.md`, `PIPELINE_IMPLEMENTATION_PLAN.md`) are historical/reference; the **authoritative** trackers are `CHANGE-PLAN.md` and the analysis docs above.
- Legacy modules are marked deprecated (see `docs/UNWIRED-MODULES-TRIAGE.md`).
