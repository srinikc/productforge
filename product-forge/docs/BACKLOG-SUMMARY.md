# Backlog Summary

> GENERATED 2026-10-09T15:46:00 by `scripts/dev/gen_backlog_summary.py`.
> Derived file - do not hand-edit. Truth: the backlog stores (core/backlog.py).

## Pipeline backend (product_forge) (`product_forge`)

- **Open:** 34  |  **Closed:** 418
- `new`: 34

### new, by category (34)
**API / reports / HIL / misc** (1)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-PF-0332 | Should | chore | API-5 deferred hardening: rate limiting + request/upload limits + tenant-isolation expansion + event streaming | API-5 deferred hardening: rate limiting + request/upload limits + tenant-isolation expansion + event streaming |

**Discovery / HIL / prompts** (1)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0218 | Should | feature | Backend: AI-era operations layer (evals + prompt/model/agent versioning + feedback loop + model-quality observability) | Add the AI-era lifecycle layer so the Product tab can show AI quality + the loop that keeps it good. |

**Knowledge / KB** (1)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0208 | Should | feature | Backend: sensor/IoT capability pack + ingest adapters (MQTT/serial/BLE/Modbus/CAN) + time-series/anomaly models | A `sensor` capability pack that, only when the idea needs it, enables device ingest, a time-series store, fore... |

**Licensing / tenancy** (2)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-PF-0390 | Should | epic | EPIC A: PF Commercial & IP Foundation (contracts, Go core, licensing, packaging, EAP, RDC, governance, vertical slice) | EPIC A — the needed-now foundation: A0 baseline freeze + ADR register; A1 thin contracts incl. Go<->Python con... |
| BI-PF-0396 | Should | feature | A2: capability registry + entitlement-at-boundary + asymmetric licensing | A2 — capability registry + entitlement checks at execution boundaries + asymmetric licensing (public-key verif... |

**Specs / cache / context / artifacts** (2)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0206 | Should | tech-debt | Backend: model downloader + local cache + license-acceptance gate + models.lock (open-weights) | One owner module that downloads only the weights a project's capability pack needs, into a gitignored local ca... |
| BI-0225 | Should | feature | Parallel section/feature generation | Run section/per-feature agent calls in parallel with a bounded worker pool and merge results deterministically... |

**Wiring / tech-debt / API** (27)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0185 | Should | feature | EPIC: Multi-modal / media orchestration (pluggable capability packs) | Make the pipeline modality-agnostic via PLUGGABLE capability packs, enabled per project when the idea needs th... |
| BI-0195 | Should | feature | EPIC: Pluggable/modular core + industry-standards adoption (MCP, A2A, AG-UI, OTel) | Everything variable is a plugin behind a port; the core depends only on ports. Adopt the open standards so we ... |
| BI-0209 | Should | feature | Backend: OCR/document capability pack + doc-parse kind + OCR generators/adapters | An `ocr` capability pack with a `ocr/doc-parse` kind, permissive self-host defaults, and paid API options -- e... |
| BI-0220 | Should | feature | EPIC: pipeline E2E reliability - events, readiness checklist, model registry/capability gate, lock/status fixes | EPIC: pipeline E2E reliability - events, readiness checklist, model registry/capability gate, lock/status fixe... |
| BI-PF-0331 | Should | chore | OS/shell neutrality: remove PowerShell-only scripting/doc workarounds | Make every scripted workflow and documented command cross-platform: pure Python entrypoints, a single shell-ne... |
| BI-PF-0360 | Should | epic | EPIC: Backlog SSOT + Work Scheduler + Pluggable Worker Orchestration (doc: PF-Backlog-SSOT-Scheduler-Pluggable-Workers) | EPIC: Backlog SSOT + Work Scheduler + Pluggable Worker Orchestration (doc: PF-Backlog-SSOT-Scheduler-Pluggable... |
| BI-PF-0374 | Should | feature | PFSSOT-P12: optimization (only after correctness) | PFSSOT-P12: optimization (only after correctness) |
| BI-PF-0386 | Should | feature | PF platform: IP-value assessment of all modules (rewrite-by-value ranking: high-value -> Go/Rust, low-value -> compiled) | PF platform: IP-value assessment of all modules (rewrite-by-value ranking: high-value -> Go/Rust, low-value ->... |
| BI-PF-0387 | Should | feature | PF platform delivery baseline: ONE source for all editions; new shipped/sensitive logic -> Go; existing -> compiled (Nuitka); no raw .py at customer; migrate by value later | PF platform delivery baseline: ONE source for all editions; new shipped/sensitive logic -> Go; existing -> com... |
| BI-PF-0388 | Should | task | ADR: PF platform shipped editions use compiled artifacts (Go core + compiled-Python), never raw .py; one source, many editions | ADR: PF platform shipped editions use compiled artifacts (Go core + compiled-Python), never raw .py; one sourc... |
| BI-PF-0391 | Should | epic | EPIC B: PF Scale & Editions (gateways, persistence, OEM, Rust, WASM, decomposition, migration) | EPIC B — B1 PF Go core (compiled host, architectural/mandatory); B2 gateways (Model/Tool/Memory/Infra); B3 per... |
| BI-PF-0393 | Should | feature | A1: canonical contracts (thin) + Go<->Python contract | A1 — thin canonical contracts: ProductSpec, TechnologyProfile, RuntimeProfile, DeploymentProfile, LicenseProfi... |
| BI-PF-0394 | Should | feature | B1: PF Go core (Go<->Python seam) | B1 — a minimal native Go host: new shipped/sensitive logic lands here. The host COMPILES (go build); it never ... |
| BI-PF-0395 | Should | feature | A6: change classifier + drift guard + language rule + no-undeclared-dep | A6 — governance: classify every change; enforce the language rule (shipped+sensitive -> Go); fail on undeclare... |
| BI-PF-0397 | Should | feature | A4: EAP delivery manifest + validator/registry + compatibility | A4 — EAP (manifest) composes contracts; validator/registry; versioning + compatibility. Executor role is parke... |
| BI-PF-0398 | Should | feature | A3: PF platform build->package->deploy + compiled packaging + signing + SBOM/LBOM + NO-RAW-.py gate (absorbs BI-PF-0383) | A3 — build->package->deploy pipeline: compiled packaging (Nuitka for Python + go build for Go) + signing + SBO... |
| BI-PF-0399 | Should | feature | A5: Runtime Dependency Compiler | A5 — Runtime Dependency Compiler: composes EAP + profiles + OS/arch + license/entitlement into the runtime pac... |
| BI-PF-0400 | Should | feature | A7: vertical slice (Requirement->Tech->Factory->EAP->RDC->compiled+signed package) | A7 — vertical slice: Requirement -> Tech -> Factory -> EAP -> RDC -> compiled + signed package, containing no ... |
| BI-PF-0401 | Should | feature | B2: gateways (Model/Tool/Memory/Infrastructure) | B2 — gateways for Model / Tool / Memory / Infrastructure so core depends on ports, not concrete providers. |
| BI-PF-0402 | Should | feature | B3: persistence adapters (SQLite/JSON/PostgreSQL) | B3 — persistence adapters (SQLite / JSON / PostgreSQL) behind one persistence port. |
| BI-PF-0403 | Should | feature | B4: OEM / white-label profiles (no forks) | B4 — OEM / white-label profiles (no forks): one source -> per-OEM edition profile. |
| BI-PF-0404 | Should | feature | B5: Rust protected components | B5 — Rust protected components behind the contract seam. |
| BI-PF-0405 | Should | feature | B6: WASM plugins | B6 — WASM plugins (sandboxed) behind the plugin contract. |
| BI-PF-0406 | Should | feature | B7: service decomposition | B7 — service decomposition behind contracts. |
| BI-PF-0407 | Should | feature | Bmig: migrate high-value legacy Python -> Go (by value) | Bmig — migrate high-value legacy Python -> Go (replace, not duplicate), then the remainder as an aspiration. |
| BI-PF-0408 | Should | change | /pf command: build mode only (not orchestrator) + global /pf for all opencode sessions | - `/pf ...` always executes in build mode (`agent: build`), with no model pin so the session's model is inheri... |
| BI-PF-0765 | Should | feature | Canonical artifact->owner->consumer map (PRD/tech/app-flow/design/schema/impl-plan) - registry + generated doc + gate | a canonical, validated artifact->owner->consumer map is generated and gate-checked |

---

## Dashboard (ProductForge-Dashboard) (`project:ProductForge-Dashboard`)

- **Open:** 146  |  **Closed:** 3
- `new`: 141
- `parked`: 5

### parked (5)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0011 | Could | feature | Deferred: voice AI companion (TTS/STT + wake word) for the dashboard | Deferred: voice AI companion (TTS/STT + wake word) for the dashboard |
| BI-0012 | Could | feature | Deferred: mobile app companion for the dashboard | Deferred: mobile app companion for the dashboard |
| BI-0013 | Could | feature | Deferred: non-English i18n (dashboard UI + prompts) | the UI and prompts can render in non-English locales |
| BI-0014 | Could | feature | Deferred: ops / post-production console (stage 13 + incidents) | Deferred: ops / post-production console (stage 13 + incidents) |
| BI-0022 | Could | enhancement | Deferred (designed): reply-by-email control actions (approve / answer / act) | Deferred (designed): reply-by-email control actions (approve / answer / act) |

### new, by category (141)
**API / reports / HIL / misc** (18)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0009 | Must | feature | API access endpoints | API access endpoints |
| BI-0016 | Must | feature | MVP: full test creation/execution/reporting/storage via our test framework - for the dashboard AND every created project | MVP: full test creation/execution/reporting/storage via our test framework - for the dashboard AND every creat... |
| BI-0035 | Must | feature | MVP: artifact registry browser + audit trail + project journal + agent ledger | MVP: artifact registry browser + audit trail + project journal + agent ledger |
| BI-0057 | Must | feature | Operator console: tenants/licenses/trials/tiers/pricing/usage | Operator console: tenants/licenses/trials/tiers/pricing/usage |
| BI-0058 | Must | feature | Customer (tenant) admin UI: members/teams/roles/seats/billing | Customer (tenant) admin UI: members/teams/roles/seats/billing |
| BI-0066 | Must | feature | MVP: project Git check-ins page (commits: date/time/#/PR/details, tags, branches, develop merges) | MVP: project Git check-ins page (commits: date/time/#/PR/details, tags, branches, develop merges) |
| BI-0070 | Must | feature | API Reuse and Extension Analysis | API Reuse and Extension Analysis |
| BI-0074 | Must | feature | MVP: dashboard/API blueprint instancing - Product Forge instance + one per generated project | MVP: dashboard/API blueprint instancing - Product Forge instance + one per generated project |
| BI-0075 | Must | feature | MVP: HIL approval dialog with full decisions + notes + snooze/wait controls | MVP: HIL approval dialog with full decisions + notes + snooze/wait controls |
| BI-0076 | Should | feature | MVP: telemetry + metrics view (JSON telemetry + Prometheus /metrics scrape target) | MVP: telemetry + metrics view (JSON telemetry + Prometheus /metrics scrape target) |
| BI-0091 | Should | feature | AI-Integration recommendation view (+ optional implement toggle) | AI-Integration recommendation view (+ optional implement toggle) |
| BI-0096 | Must | feature | Project page: final report link + live PROJECT-STATUS (content/frequency) | Project page: final report link + live PROJECT-STATUS (content/frequency) |
| BI-0116 | Must | feature | Test results reporting | Test results reporting |
| BI-0124 | Must | feature | API surface for dashboard data | API surface for dashboard data |
| BI-0125 | Must | feature | API reuse analysis & design | API reuse analysis & design |
| BI-0129 | Should | feature | Traceability view + API over the id hub (keeps id-only data; consumes backend index) | Traceability view + API over the id hub (keeps id-only data; consumes backend index) |
| BI-0130 | Should | feature | Dashboard logs: dashboard/logs/dashboard.log + per-run streaming/API of agent logs | Dashboard logs: dashboard/logs/dashboard.log + per-run streaming/API of agent logs |
| BI-0135 | Should | feature | Tier-creation UI: show all model attributes + per-agent fit while creating/assigning; auto-create | Tier-creation UI: show all model attributes + per-agent fit while creating/assigning; auto-create |

**Discovery / HIL / prompts** (7)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0017 | Must | feature | MVP: intake follow-up + parked management + full intake lifecycle in the dashboard | MVP: intake follow-up + parked management + full intake lifecycle in the dashboard |
| BI-0020 | Must | feature | MVP: webhooks - inbound intake signatures + outbound alert/notification webhooks | MVP: webhooks - inbound intake signatures + outbound alert/notification webhooks |
| BI-0025 | Must | feature | MVP: live 360-degree multi-agent discovery meeting in the project ideation/discovery round | MVP: live 360-degree multi-agent discovery meeting in the project ideation/discovery round |
| BI-0052 | Must | feature | UI: entitlement-aware navigation (locked features + upgrade prompts) | UI: entitlement-aware navigation (locked features + upgrade prompts) |
| BI-0073 | Must | feature | MVP: Ideas workspace - idea-only intake, review/follow-up, promote-to-project, consolidate multiple ideas | MVP: Ideas workspace - idea-only intake, review/follow-up, promote-to-project, consolidate multiple ideas |
| BI-0090 | Should | feature | Agent Builder UI (create/add dynamic MAIN agent: capabilities, model, prompts, inputs, artifacts, deps) | Agent Builder UI (create/add dynamic MAIN agent: capabilities, model, prompts, inputs, artifacts, deps) |
| BI-0126 | Should | feature | Discovery review UI: id + question + recommendation + per-question text box (add/discard), scrollable dialog | Discovery review UI: id + question + recommendation + per-question text box (add/discard), scrollable dialog |

**Dynamic pipeline / agents** (7)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0064 | Must | feature | MVP: project creation wizard E2E (idea, dir, tiers/per-agent models, git, localization, branding, target, budget, integrations, template, team) | MVP: project creation wizard E2E (idea, dir, tiers/per-agent models, git, localization, branding, target, budg... |
| BI-0069 | Must | feature | API-First Access | API-First Access |
| BI-0089 | Should | feature | Pipeline Tailoring UI (recommendation + select stages/agents) | Pipeline Tailoring UI (recommendation + select stages/agents) |
| BI-0092 | Should | feature | Template gallery & selection UI (pipeline_templates) | Template gallery & selection UI (pipeline_templates) |
| BI-0094 | Should | feature | Model-tier editor: new agents | Model-tier editor: new agents |
| BI-0095 | Should | feature | Agent capability-binding view (per-agent prompt + knowledge/skills/MCP/domain/business bindings) | Agent capability-binding view (per-agent prompt + knowledge/skills/MCP/domain/business bindings) |
| BI-0102 | Must | feature | Interaction templates | Interaction templates |

**Knowledge / KB** (5)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0032 | Must | feature | MVP: onboard/analyze an EXISTING product (product analyzer + ingestion) | MVP: onboard/analyze an EXISTING product (product analyzer + ingestion) |
| BI-0040 | Must | feature | MVP: dashboard surfaces knowledge graph + agent memory as first-class views/management | MVP: dashboard surfaces knowledge graph + agent memory as first-class views/management |
| BI-0093 | Should | feature | Knowledge & Skills browser (incl. business-models pack + what was learned) | Knowledge & Skills browser (incl. business-models pack + what was learned) |
| BI-0098 | Should | feature | Tech-stack & knowledge catalog browser (staleness + refresh status + approve new entries) | Tech-stack & knowledge catalog browser (staleness + refresh status + approve new entries) |
| BI-0136 | Should | feature | Knowledge/skills registry UI: add/modify/view knowledge, skills, techstack, domain, MCP | Knowledge/skills registry UI: add/modify/view knowledge, skills, techstack, domain, MCP |

**Licensing / tenancy** (10)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0045 | Must | feature | MVP: Platform Operator console - tenants, licenses/keys, trials, tiers, pricing, provisioning | MVP: Platform Operator console - tenants, licenses/keys, trials, tiers, pricing, provisioning |
| BI-0046 | Must | feature | MVP: Customer (tenant) admin - users, teams, roles, seats, quotas, billing/usage | MVP: Customer (tenant) admin - users, teams, roles, seats, quotas, billing/usage |
| BI-0047 | Must | feature | MVP: License tiers + feature-group entitlements (categorize all modules into logical groups) | MVP: License tiers + feature-group entitlements (categorize all modules into logical groups) |
| BI-0048 | Must | feature | MVP: Customer engagement/licensing portal (self-service signup, buy, activate, manage) | MVP: Customer engagement/licensing portal (self-service signup, buy, activate, manage) |
| BI-0050 | Must | feature | Operator UI: manage tiers/entitlements/subscriptions data (list/edit) | Operator UI: manage tiers/entitlements/subscriptions data (list/edit) |
| BI-0051 | Must | feature | Operator UI: issue/revoke/extend license keys | Operator UI: issue/revoke/extend license keys |
| BI-0053 | Must | feature | UI: seat + quota usage and limits | UI: seat + quota usage and limits |
| BI-0054 | Must | feature | Operator UI: configure + monitor trials | Operator UI: configure + monitor trials |
| BI-0055 | Must | feature | Onboarding UI: activate license / provision tenant | Onboarding UI: activate license / provision tenant |
| BI-0140 | Should | feature | Multi-modal: model & kind strategy view (chosen kind/provider/model, free/paid, license badge, override) | Multi-modal: model & kind strategy view (chosen kind/provider/model, free/paid, license badge, override) |

**Model fit** (1)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0062 | Must | feature | MVP: tier/model capability-fit view (per-agent required vs supported, at-risk/incompatible callouts) | MVP: tier/model capability-fit view (per-agent required vs supported, at-risk/incompatible callouts) |

**Phases (new)** (2)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0087 | Should | feature | Business/Market/Monetization views (stages 0b-0e) | Business/Market/Monetization views (stages 0b-0e) |
| BI-0088 | Should | feature | Operate/Grow/Engage views (stages 13-13b) | Operate/Grow/Engage views (stages 13-13b) |

**Specs / cache / context / artifacts** (11)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0019 | Must | feature | MVP: alerts + notifications - portfolio-wide, project-specific, and intake-related | MVP: alerts + notifications - portfolio-wide, project-specific, and intake-related |
| BI-0042 | Must | feature | MVP: add views for stores with no route/item (qa-weights, supervisor_state, ports, initial-context, BOM, design-spec, llm-errors, kit, adaptive_reasoning, generation-state, system_config, .agent.json) | MVP: add views for stores with no route/item (qa-weights, supervisor_state, ports, initial-context, BOM, desig... |
| BI-0065 | Must | feature | MVP: pipeline workflow page with interactive diagram (stages/agents/sub-agents/roles/artifacts/models) + embedded PDF | MVP: pipeline workflow page with interactive diagram (stages/agents/sub-agents/roles/artifacts/models) + embed... |
| BI-0077 | Must | feature | MVP: per-feature Spec & Traceability page (spec + embedded diagrams + review status) | MVP: per-feature Spec & Traceability page (spec + embedded diagrams + review status) |
| BI-0079 | Should | feature | MVP: spec diagram viewer - embedded mermaid + draw.io + PDF | MVP: spec diagram viewer - embedded mermaid + draw.io + PDF |
| BI-0080 | Must | feature | MVP: per-feature Functional spec (stage 1) + Design spec (stage 1a) pages, F-keyed, cross-linked, with diagrams viewer | MVP: per-feature Functional spec (stage 1) + Design spec (stage 1a) pages, F-keyed, cross-linked, with diagram... |
| BI-0081 | Should | feature | MVP: diagram viewer (mermaid + draw.io + PDF/SVG) | MVP: diagram viewer (mermaid + draw.io + PDF/SVG) |
| BI-0083 | Must | feature | Cache controls + hit/miss surfacing (clear cache, bypass/regenerate toggle, per-agent input-cache view) | Cache controls + hit/miss surfacing (clear cache, bypass/regenerate toggle, per-agent input-cache view) |
| BI-0084 | Should | feature | Context Inspector: per-agent assembled context + per-phase handoff snapshot | Context Inspector: per-agent assembled context + per-phase handoff snapshot |
| BI-0085 | Should | feature | Run view: concurrent/parallel agent execution + speedup indicator | Run view: concurrent/parallel agent execution + speedup indicator |
| BI-0144 | Should | feature | Multi-modal: providers & models management (keys, allowlist, cost caps, model download cache) | Multi-modal: providers & models management (keys, allowlist, cost caps, model download cache) |

**Wiring / tech-debt / API** (80)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0001 | Must | feature | Project creation workflow | a user can create a project that enters the pipeline with its idea captured |
| BI-0002 | Must | feature | Multi-project portfolio view | Multi-project portfolio view |
| BI-0004 | Must | feature | Model tier selection and customization | Model tier selection and customization |
| BI-0005 | Must | feature | Pipeline monitoring and logging | Pipeline monitoring and logging |
| BI-0006 | Must | feature | AI chat companion | AI chat companion |
| BI-0007 | Must | feature | Mobile responsive design | Mobile responsive design |
| BI-0008 | Must | feature | Auto mode pipeline execution | Auto mode pipeline execution |
| BI-0010 | Must | feature | Theme/customization options | Theme/customization options |
| BI-0015 | Must | feature | MVP: dashboard must surface ALL 176 backend modules + their workflows with designed UI/UX (E2E) | MVP: dashboard must surface ALL 176 backend modules + their workflows with designed UI/UX (E2E) |
| BI-0018 | Must | feature | MVP: depict backend configs + script parameters (inputs/outputs) and control operations in the UI | MVP: depict backend configs + script parameters (inputs/outputs) and control operations in the UI |
| BI-0021 | Must | feature | MVP: email facility - pipeline/project status + alerts, configurable frequency | MVP: email facility - pipeline/project status + alerts, configurable frequency |
| BI-0023 | Should | feature | MVP: PWA support for the dashboard web app (installable, offline shell, push) | MVP: PWA support for the dashboard web app (installable, offline shell, push) |
| BI-0024 | Must | feature | Dashboard build depends on backend changes first - dual backlog tracking (backend + dashboard) | Dashboard build depends on backend changes first - dual backlog tracking (backend + dashboard) |
| BI-0026 | Must | feature | MVP: agent status + per-agent control UI (start/stop/pause/resume/cancel) once backend supports it | MVP: agent status + per-agent control UI (start/stop/pause/resume/cancel) once backend supports it |
| BI-0027 | Must | feature | MVP: dashboard must depict the canonical E2E pipeline workflow + orchestrate all CLI parameters in UI | MVP: dashboard must depict the canonical E2E pipeline workflow + orchestrate all CLI parameters in UI |
| BI-0028 | Must | feature | MVP: E2E pipeline view shows all stages/phases, agents + grouped sub-agents, selected tier and model per agent | MVP: E2E pipeline view shows all stages/phases, agents + grouped sub-agents, selected tier and model per agent |
| BI-0029 | Must | feature | MVP: delegation + agent-messaging console (records, budgets, signals, handoffs) | MVP: delegation + agent-messaging console (records, budgets, signals, handoffs) |
| BI-0030 | Must | feature | MVP: insights view + promote-to-backlog action | MVP: insights view + promote-to-backlog action |
| BI-0031 | Must | feature | MVP: BYOT + model registry/recommendation + tier proposal/apply | MVP: BYOT + model registry/recommendation + tier proposal/apply |
| BI-0033 | Must | feature | MVP: cost modeling + FinOps views | MVP: cost modeling + FinOps views |
| BI-0034 | Must | feature | MVP: feature tracker + traceability matrix + requirement links | MVP: feature tracker + traceability matrix + requirement links |
| BI-0036 | Must | feature | MVP: build/version/release + VCS views | MVP: build/version/release + VCS views |
| BI-0037 | Must | feature | MVP: resilience controls - circuit breakers, run breaker, stop conditions, DLQ, checkpoints, loop modes | MVP: resilience controls - circuit breakers, run breaker, stop conditions, DLQ, checkpoints, loop modes |
| BI-0038 | Must | feature | MVP: compliance + security + schema/signing views | MVP: compliance + security + schema/signing views |
| BI-0039 | Should | feature | SHOULD: customer onboarding package view | SHOULD: customer onboarding package view |
| BI-0041 | Must | feature | MVP: explicit dashboard coverage for remaining backend capability families (beyond BI-0015 generic) | MVP: explicit dashboard coverage for remaining backend capability families (beyond BI-0015 generic) |
| BI-0043 | Must | change | MVP is a TOTAL REWRITE - build the dashboard from scratch (take NOTHING from pipeline_dashboard) | MVP is a TOTAL REWRITE - build the dashboard from scratch (take NOTHING from pipeline_dashboard) |
| BI-0044 | Must | feature | MVP: user-selectable deployment target (Vercel / managed cloud / self-hosted / remote Linux or Windows host) | MVP: user-selectable deployment target (Vercel / managed cloud / self-hosted / remote Linux or Windows host) |
| BI-0049 | Must | feature | MVP: instance-role UI gating - operator pages only on operator instance; hidden+blocked for customers | MVP: instance-role UI gating - operator pages only on operator instance; hidden+blocked for customers |
| BI-0056 | Must | feature | Public customer portal: signup / plan / buy / activate | Public customer portal: signup / plan / buy / activate |
| BI-0059 | Must | feature | UI gating: operator pages only on operator instance | UI gating: operator pages only on operator instance |
| BI-0060 | Must | feature | Frontend: separate builds - operator app excluded from the customer package (not just hidden) | Frontend: separate builds - operator app excluded from the customer package (not just hidden) |
| BI-0061 | Must | feature | MVP: delete project -> 7-day restorable archive + reminder before permanent deletion | MVP: delete project -> 7-day restorable archive + reminder before permanent deletion |
| BI-0063 | Must | feature | MVP: unified backlog console - ALL scopes (each project, pipeline/product_forge, dashboard) + full management | MVP: unified backlog console - ALL scopes (each project, pipeline/product_forge, dashboard) + full management |
| BI-0067 | Must | feature | Mobile Dashboard Companion | Mobile Dashboard Companion |
| BI-0068 | Must | feature | Test Management | Test Management |
| BI-0071 | Must | feature | Deployment Options | Deployment Options |
| BI-0072 | Must | feature | Voice Reference Alignment | Voice Reference Alignment |
| BI-0078 | Must | feature | MVP: Reviews & Feedback tracking (project page + portfolio process-health widget + inline on artifact) | MVP: Reviews & Feedback tracking (project page + portfolio process-health widget + inline on artifact) |
| BI-0082 | Must | feature | Review backend<->dashboard capability reciprocity (record a dashboard_impact decision; dashboard item only when needed) | Review backend<->dashboard capability reciprocity (record a dashboard_impact decision; dashboard item only whe... |
| BI-0097 | Must | feature | Run view: implementation iterations (dynamic count + feature batch) + orchestrate controls | Run view: implementation iterations (dynamic count + feature batch) + orchestrate controls |
| BI-0099 | Must | feature | Stage/agent gating visibility | Stage/agent gating visibility |
| BI-0100 | Could | feature | Cost/token analytics | Cost/token analytics |
| BI-0101 | Must | feature | Reusable component library | Reusable component library |
| BI-0103 | Must | feature | Notification & alert center | Notification & alert center |
| BI-0104 | Must | feature | Theming | Theming |
| BI-0105 | Must | feature | Responsive web layout | Responsive web layout |
| BI-0106 | Could | feature | Keyboard shortcuts / command palette | Keyboard shortcuts / command palette |
| BI-0107 | Must | feature | Global AI chat companion | Global AI chat companion |
| BI-0108 | Must | feature | Chat-driven control & orchestration | Chat-driven control & orchestration |
| BI-0109 | Must | feature | Voice support — TTS/STT | Voice support — TTS/STT |
| BI-0110 | Must | feature | Wake-word activation | Wake-word activation |
| BI-0111 | Must | feature | Voice activation guard | Voice activation guard |
| BI-0112 | Must | feature | Mobile app | Mobile app |
| BI-0113 | Must | feature | Mobile monitoring & light control | Mobile monitoring & light control |
| BI-0114 | Must | feature | Push notifications | Push notifications |
| BI-0115 | Must | feature | Test framework integration | Test framework integration |
| BI-0117 | Must | feature | Issue tracking | Issue tracking |
| BI-0118 | Must | feature | Multi-type test coverage | Multi-type test coverage |
| BI-0119 | Must | feature | UI for every pipeline feature/config | UI for every pipeline feature/config |
| BI-0120 | Could | feature | Config change history | Config change history |
| BI-0121 | Must | feature | Deployable from public sites | Deployable from public sites |
| BI-0122 | Must | feature | Combined or split deployment | Combined or split deployment |
| BI-0123 | Must | feature | Deployment configuration options | Deployment configuration options |
| BI-0127 | Should | feature | Analytics view consumes backend run-lifecycle events | Analytics view consumes backend run-lifecycle events |
| BI-0128 | Should | feature | Adopt external project UI (scan + import/reference + manage) | Adopt external project UI (scan + import/reference + manage) |
| BI-0132 | Should | feature | Agents window UI: edit agent card (instructions + per-agent MODEL via model browser); stop agent -> re-run with updated model (whole pipeline) | - See and control the model each agent actually runs. - Browse/search ALL models by capability / behaviour / r... |
| BI-0133 | Should | feature | Backlog orchestration UI: triage/accept/execute/schedule/manage backlogs (both scopes) | Backlog orchestration UI: triage/accept/execute/schedule/manage backlogs (both scopes) |
| BI-0134 | Should | feature | Multi-modal I/O UI: upload/capture image/audio/video, preview/play generated media, manage assets | Multi-modal I/O UI: upload/capture image/audio/video, preview/play generated media, manage assets |
| BI-0137 | Should | feature | Dashboard: run a backlog item (scoped amend run) + surface the quality gate (block on failure) | From a backlog item, trigger a scoped (amend) run and surface the backend quality-gate result; block applying ... |
| BI-0138 | Should | feature | EPIC: multi-modal support surfaces (packs, model/kind selection, assets, media QA, cost, providers) | Surface the whole multi-modal layer in the ProductForge dashboard so a media/IoT project is transparent and co... |
| BI-0139 | Should | feature | Multi-modal: capability packs view (detected modalities, enable/disable, pack contents) | Multi-modal: capability packs view (detected modalities, enable/disable, pack contents) |
| BI-0141 | Should | feature | Multi-modal: asset library + media preview (image/video/audio/3D viewers, transcripts, provenance) | Multi-modal: asset library + media preview (image/video/audio/3D viewers, transcripts, provenance) |
| BI-0142 | Should | feature | Multi-modal: media QA results view (probe/loudness/phash/A-V sync, per-artifact pass/fail) | Multi-modal: media QA results view (probe/loudness/phash/A-V sync, per-artifact pass/fail) |
| BI-0143 | Should | feature | Multi-modal: per-unit cost view (per image/second/char/track/mesh; budget vs actual) | Multi-modal: per-unit cost view (per image/second/char/track/mesh; budget vs actual) |
| BI-0145 | Should | feature | Multi-modal: dashboard e2e (visual) - packs/models/assets/QA/cost for a media project | Multi-modal: dashboard e2e (visual) - packs/models/assets/QA/cost for a media project |
| BI-0146 | Should | feature | Multi-modal: feasibility triage view - build-host feasibility (ideation) + destination runtime & shipping mode (post-build) | Surface the two-phase feasibility triage: - PHASE 1 (ideation): the build host's hardware (GPU/VRAM/RAM/disk) ... |
| BI-0147 | Must | feature | EPIC: Product one-stop page (Project Management + Product modes) - per-product dynamic page | One route per product with TWO tabs (Project Management / Product), default driven by lifecycle, that is DERIV... |
| BI-0148 | Must | feature | Product page: Project Management tab (progress %, features+status, artifacts, quality summary, blockers, cost, activity) | The build-time view: overall progress % by phase; feature (F-x) table with status; artifacts by stage; quality... |
| BI-0149 | Must | feature | Product page: Product tab (details, launch, docs/guides, install/deploy, BOM/footprint, links, releases, maintenance) | The post-build view: what it is; launch link + status; docs/guides; install/deploy brief; BOM/footprint (runti... |

---

## Totals
- backend: 34 open / 418 closed
- dashboard: 146 open / 3 closed
