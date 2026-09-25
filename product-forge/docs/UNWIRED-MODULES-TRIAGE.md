# Unwired Modules — Triage & Disposition (4.12)

> Generated from `scripts/dev/find_unused_modules.py` (direct-reference scan over
> `core/`, `pipeline_dashboard/`, `scripts/`, `adapters/`).
> **Decision record** — dispositions below are the agreed fate; removal happens
> only after a re-scan shows no importers and tests pass.

## Method
`python scripts/dev/find_unused_modules.py` lists `core/*.py` modules never
imported anywhere. Result at time of writing: **119 core modules, 21 unreferenced**.

## Dispositions

### A. Wire next (real gaps — high value)
| Module | Why wire |
|---|---|
| `schema_validator` | validate artifacts against `docs/schemas/*` at stage completion |
| `audit_trail` | durable, queryable audit stream (complements `agent-audit-log.json`) |
| `techstack_guidelines` | feed stack-specific guidance into prompts (complements `core/tech_stack.py`) |
| `business_skills_selector` | select skills per product/business type (skills registry already seeded) |
| `code_analyzer` | static analysis for the `code-review` / `fix` agents |
| `service_catalog` | map architecture services → infra/tooling |
| `agent_migrator` | migrate legacy agent cards → `AgentSpec` (tooling) |

### B. Keep as optional libraries (wire on demand)
| Module | When |
|---|---|
| `build_utility`, `docker_compose_generator` | packaging/devops stages (partly covered by `nfr_runner`) |
| `code_executor` | sandboxed execution in tool loop |
| `mobile_tester` | mobile stack detected |
| `websocket_manager` | realtime stacks |
| `version_manager` | release/versioning flow |
| `marketing` | marketing agent runtime (spec exists; runtime module optional) |

### C. Legacy / parallel — deprecate (do not build on)
`intake_api`, `main`, `global_orchestrator`, `factory_supervisor`,
`pipeline_engine`, `product_analyzer`, `product_ingestion`, `intent_router`,
`conversation_*` — superseded by `PipelineExecutor` + `core/orchestrator/*`.
**Action:** mark deprecated in a header comment; remove after confirming no
external callers (dashboard/adapters).

### D. Housekeeping (not runtime modules)
`test_batch345`, `test_budget_protection`, `test_e2e_pipeline`,
`test_e2e_real_pipeline`, `test_integration`, `test_new_modules` — stray test
files living in `core/`. **Action:** move to `tests/` (or `scripts/dev/tests/`)
in a dedicated commit; not part of the pipeline runtime.

## Notes
- "Unreferenced" ≠ "dead": some are imported dynamically or referenced by docs.
- Re-run the scan after any wiring/removal; treat the list as the source of truth.

## Update (2026-09-12) — PART 6 wire status
- schema_validator — **WIRED** (executor _validate_state_schemas; report field schema_validation; added project schema mapping).
- udit_trail — **redundant** with gent-audit-log.json + gent-audit.md (keep as optional exporter).
- 	echstack_guidelines — **overlaps** knowledge-layers-follow-stack (core/tech_stack.py + guideline loader).
- usiness_skills_selector — overlaps skills_registry; wire when a skills layer is needed.
- code_analyzer / service_catalog — need external tooling / infra mapping; optional.
- gent_migrator — one-off dev tool (AgentSpec migration).

## Update — reachability re-triage (BI-0028 / BI-0029)

Earlier scans measured **references** (is `core.X` mentioned?), which reports an unused
`# noqa: F401` import as wired. The new **`scripts/dev/invocation_audit.py`** measures
**reachability** from the real entrypoints and is now part of `wired_audit.py`
(+ CI / `pr_gate.structure_contract`). Result: 157/179 reachable, 22 unreachable = **4 real
orphans + 18 allowlisted**.

### Wired in this pass (were imported-but-never-invoked)
| Module | Wired into | Artifact |
|---|---|---|
| `discovery_engine` | Stage `0a` (`_run_design_augmentations`) | `discovery-questions.json` (18 questions, 3 perspectives) |
| `product_design_spec` | Stage `1a` | `docs/design-spec.json` (`save_spec`) |
| `dashboard_archetypes` | Stage `1`/`2` | `docs/dashboard-archetype.md` |
| `design_tokens` | Stage `1c` | `docs/design-tokens.json` + CSS custom props |

### Allowlisted (not reachable; reason recorded in `invocation_audit.ALLOW`)
- **Removed (BI-0032):** `forge_supervisor`, `human_controls`, `pipeline_engine` — dead,
  superseded by `PipelineExecutor` + `core/orchestrator/*`.
- **Legacy, still reachable by tooling/CLI:** `global_orchestrator`, `agent_rules`,
  `agent_structure` (candidates for removal once their tooling callers go).
- **Tooling / CLI / entrypoint:** `main`, `pdf_generator`, `workflow_docs`, `intake_api`,
  `memory_api`, `agent_migrator`, `agent_card_loader`.
- **Optional (wire on demand):** `code_executor`, `build_utility`, `marketing`,
  `websocket_manager`, `docker_compose_generator`.

> Rule going forward: a new core module with no invocation path fails CI until it is wired
> or added to `ALLOW` **with a reason**. "Imported" is no longer accepted as "wired".

