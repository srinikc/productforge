# Backlog Summary

> GENERATED 2026-10-25T23:34:35 by `scripts/dev/gen_backlog_summary.py`.
> Derived file - do not hand-edit. Truth: the backlog stores (core/backlog.py).

## Pipeline backend (product_forge) (`product_forge`)

- **Open:** 134  |  **Closed:** 595
- `blocked`: 1
- `executing`: 3
- `in_progress`: 1
- `new`: 129

### new, by category (129)
**API / reports / HIL / misc** (15)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-PF-0332 | Should | chore | API-5 deferred hardening: rate limiting + request/upload limits + tenant-isolation expansion + event streaming | API-5 deferred hardening: rate limiting + request/upload limits + tenant-isolation expansion + event streaming |
| BI-PF-1217 | Should | feature | C15: Security evaluation + red-team suite + security metrics (assurance) | C15: Security evaluation + red-team suite + security metrics (assurance) |
| BI-PF-1243 | Should | epic | EPIC: CI/CD & Gates - SSOT doc + model + read API (PF + generated products) | One place to understand and read (via API) how PF builds/verifies/ships and how generated products do: the CI/... |
| BI-PF-1245 | Should | feature | Orchestrator UI: small CI/CD view over the engineering ci-cd API (gates x tiers x status) | A small orchestrator UI view that renders the CI/CD + gates model from the read API (BI-PF-1239), so an operat... |
| BI-PF-1251 | Should | change | Unscoped triage: re-home 'Unscoped' children into real epics (grooming cadence + aging advisory) | Keep `Unscoped` small: an ongoing curation loop re-homes its children into real epics. |
| BI-PF-1274 | Should | feature | Eventing SSOT: API surface - SSE GET /events/stream + subscription CRUD (edge decision) | SSE stream + subscription CRUD exposed via edits to existing API routes; edge ownership decided in E1. |
| BI-PF-1286 | Should | change | Entitlement enforcement: cover remaining boundaries (pipeline/capability/API) + action->group mapping (beyond the worker-claim wired by A2) | Extend entitlement enforcement to the remaining execution boundaries with per-action group mapping. |
| BI-PF-1291 | Should | bug | Defect/RCCA: backlog.update() did not sync epic.children[] on epic/parent change -> chronic backlog residue that fails the residue gate on every branch (fixed; delivered with A4) | Keep epic.children[] in sync on every epic/parent membership change so the backlog-residue gate never drifts. |
| BI-PF-1316 | Must | task | api-governance gate red on develop: committed api/openapi.json drifted from the routers (BI-PF-0397 EAP endpoints) | api-governance gate red on develop: committed api/openapi.json drifted from the routers (BI-PF-0397 EAP endpoi... |
| BI-PF-1321 | Must | task | Auto-mode HIL proxy gate fails stage 0: human agent invoked without the product brief / artifacts | Auto-mode HIL proxy gate fails stage 0: human agent invoked without the product brief / artifacts |
| BI-PF-1322 | Must | task | Product run re-pointed the framework repo git remote (connect_remote walked up to the parent repo) | Product run re-pointed the framework repo git remote (connect_remote walked up to the parent repo) |
| BI-PF-1328 | Must | task | WG-O4: Merge-driver coverage for id-blocks.json (max-merge) + children[] regenerated | Extend the derived merge driver to id-blocks and children. |
| BI-PF-1331 | Should | bug | pre-commit lint_check crashes in git worktrees (WinError 206 long path) - blocks commits | Make the pre-commit lint_check work from a git worktree (no WinError 206 long-path crash). |
| BI-PF-1382 | Must | bug | Backlog API: POST /backlog/items returns empty resource_id (created id not surfaced) | Backlog API: POST /backlog/items returns empty resource_id (created id not surfaced) |
| BI-PF-1441 | Should | feature | Dynamic design-direction stage + HIL suggest gate | At the start of design, PF suggests ranked directions and the operator confirms one. |

**Bug fixes** (1)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-PF-1332 | Should | bug | Develop red: test pollution committed into data/learnings.json breaks test_global_render_unchanged (scratch loop-learning marker 0270) | Restore develop green: purge test pollution from data/learnings.json + prevent test writes to the real learnin... |

**Discovery / HIL / prompts** (8)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0218 | Should | feature | Backend: AI-era operations layer (evals + prompt/model/agent versioning + feedback loop + model-quality observability) | Add the AI-era lifecycle layer so the Product tab can show AI quality + the loop that keeps it good. |
| BI-PF-1208 | Should | feature | C6: Tool/Action Security Gateway + Tool-Result Guardrail (policy+risk+approval+sandbox per action; injection-scan results) | C6: Tool/Action Security Gateway + Tool-Result Guardrail (policy+risk+approval+sandbox per action; injection-s... |
| BI-PF-1214 | Should | feature | C12: Multi-agent delegation control (capability/delegated/resource/time/action/approval scope) | C12: Multi-agent delegation control (capability/delegated/resource/time/action/approval scope) |
| BI-PF-1216 | Should | feature | C14: Security gates S0-S6 across the factory pipeline (intake->planning->impl->test->release->runtime->improve) | C14: Security gates S0-S6 across the factory pipeline (intake->planning->impl->test->release->runtime->improve... |
| BI-PF-1236 | Should | change | Worker ops: worker charter (binding guidelines) + runtime prompt fix (no agent merge) + model pin | - workergrid/instructions.md: full worker charter (14 binding guidelines; manual-by-default, auto mode). - wor... |
| BI-PF-1242 | Should | feature | In-session manual/auto worker mode + /wg watch monitoring + 14-guidelines approval gates | - In-session manual worker mode (/wg work manual, default): 1. Claims assignment atomically from PF via /assig... |
| BI-PF-1442 | Should | feature | Skill/guideline prompt injection (SKILLS: block) | Agents receive applicable skills through PF's own prompt builder. |
| BI-PF-1486 | Should | hardening | Review tooling hardening: derived-doc content, material approval ordering, coverage edge cases | Harden review tooling after BI-PF-1484 post-merge findings: derived-doc content validation, per-breach materia... |

**Dynamic pipeline / agents** (5)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-PF-1390 | Should | task | Contract-driven agent prompts: deprecate the hardcoded templates (design 3.1-3.10, architect 6.1-6.21) + remove .opencode refs | Prompts state 'minimum sufficient' + the section plan/ids come from the contract; only relevant/required secti... |
| BI-PF-1400 | Must | feature | API-first standard (ADR-0007): assess API need per capability; where needed, expose a secured API for internal + external consumers | API-first standard (ADR-0007): every PF capability exposes a secured API; tooling is a client only |
| BI-PF-1404 | Should | defect | API-first is documented but not enforced: add an automated gate (every item declares an API-surface decision or a justified 'no need') | API-first is documented but not enforced: add an automated gate (every item declares an API-surface decision o... |
| BI-PF-1406 | Must | feature | API-first retrofit: add api-impact write endpoint + record api_impact decisions across open items + build missing API surfaces | API-first retrofit: add api-impact write endpoint + record api_impact decisions across open items + build miss... |
| BI-PF-1444 | Should | feature | Accessibility engine + fail-closed gate + templates | WCAG 2.2 AA becomes a real fail-closed ship gate. |

**Knowledge / KB** (6)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0208 | Must | feature | Backend: sensor/IoT capability pack + ingest adapters (MQTT/serial/BLE/Modbus/CAN) + time-series/anomaly models | A `sensor` capability pack that, only when the idea needs it, enables device ingest, a time-series store, fore... |
| BI-PF-1401 | Should | feature | Expose doc-driven backlog ingest via a Go capability service (generic surface); tooling becomes a client | Expose doc-driven backlog ingest via a Go capability service (generic surface); tooling becomes a client |
| BI-PF-1403 | Should | feature | Doc-ingest extraction: design Go extraction for .docx/.pdf (and future formats) in the capability service | Doc-ingest extraction: design Go extraction for .docx/.pdf (and future formats) in the capability service |
| BI-PF-1436 | Should | epic | Design System & UI/UX Knowledge (framework-agnostic) | Merge the UIUX/ corpus and the OpenCode skills into a PF-owned framework-agnostic knowledge+skills base, and l... |
| BI-PF-1438 | Should | feature | UIUX knowledge ingestion (guidelines, design-systems, samples) | Distill UIUX/ into PF guidelines + reference baselines the existing loader already injects. |
| BI-PF-1443 | Should | feature | Agent skill & knowledge-layer bindings | Bind the 8 skills + ui-ux/design-systems layers to the right agents. |

**Licensing / tenancy** (6)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-PF-0390 | Should | epic | EPIC A: PF Commercial & IP Foundation (contracts, Go core, licensing, packaging, EAP, RDC, governance, vertical slice) | EPIC A — the needed-now foundation: A0 baseline freeze + ADR register; A1 thin contracts incl. Go<->Python con... |
| BI-PF-1287 | Should | change | License issuance production: vendor keypair management + signing-env integration (A3 packaging) | Provision a vendor signing keypair for production issuance; ship only the public key with the product; integra... |
| BI-PF-1292 | Must | epic | EPIC: Enterprise Data Plane (DB & Storage) - PostgreSQL system of record + object store + tenant isolation + data residency | Build the provider-neutral enterprise data plane from docs/Product_Forge_Enterprise_Performance_Security_DB_St... |
| BI-PF-1317 | Could | feature | EDP-24: Scale-out & enterprise isolation tiers (read replicas / partitioning / tenant isolation tiers / additional region cells / region-migration workflow) [EVIDENCE-GATED] | Provide scale-out and enterprise isolation tiers including read-replica support, DB partitioning, tenant isola... |
| BI-PF-1415 | Should | defect | RCCA: config/derived stores classified by kind heuristic (not reviewed) - 78 project/tenant-scoped stores likely belong in DB (views/tables) | RCCA: config/derived stores classified by kind heuristic (not reviewed) - 78 project/tenant-scoped stores like... |
| BI-PF-1478 | Must | feature | EDP: per-tenant authentication + hard per-tenant quota isolation for the data-plane service | Give go/edpsvc a real per-tenant principal so per-tenant quotas/concurrency are bound to the authenticated ten... |

**Specs / cache / context / artifacts** (10)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0206 | Should | tech-debt | Backend: model downloader + local cache + license-acceptance gate + models.lock (open-weights) | One owner module that downloads only the weights a project's capability pack needs, into a gitignored local ca... |
| BI-0225 | Should | feature | Parallel section/feature generation | Run section/per-feature agent calls in parallel with a bounded worker pool and merge results deterministically... |
| BI-PF-1212 | Should | feature | C10: Security-event audit/evidence (evidence-grade) + durable SecurityContext propagation | C10: Security-event audit/evidence (evidence-grade) + durable SecurityContext propagation |
| BI-PF-1241 | Should | feature | Per-item token/cache/cost usage (execution.usage) + runtime usage capture + rollup | - backlog execution: + usage{} (input/output/reasoning/cache_read/cache_write/total/cost_usd/model/cost_source... |
| BI-PF-1273 | Should | feature | Eventing SSOT: migrate existing consumers (event_bus/context/ops/capabilities/parked/notifications/alerts) behind shims | Migrate each consumer to the subscriber/transport API with a compatibility shim so behavior is identical durin... |
| BI-PF-1314 | Should | feature | EDP-22: Benchmarks/SLOs + EXPLAIN(ANALYZE,BUFFERS) tuning + observability + quotas + graceful degradation (DB/object/cache/queue) | Establish performance benchmarks/SLOs, EXPLAIN(ANALYZE,BUFFERS)-based tuning, observability, quotas, and grace... |
| BI-PF-1329 | Should | feature | WG-O5: Assign a SPECIFIC backlog item to a session/worker (claim-by-id + operator assignment) with lease semantics | Support claiming/assigning a specific item id (not just next-eligible). |
| BI-PF-1385 | Must | bug | Backlog API: no deterministic endpoint to author item context fields (objective/acceptance_criteria/affected_files/approach) | Backlog API: no deterministic endpoint to author item context fields (objective/acceptance_criteria/affected_f... |
| BI-PF-1392 | Should | task | Enforce per-feature FR/US caps + max_lines in the Go artifact engine (scaled by the profile) and reconcile the three section sources | Per-feature FR/US caps + max_lines enforced NUMERICALLY (scaled by profile); sections have ONE source. |
| BI-PF-1425 | Should | feature | Migrate orchestrator cache + evidence/summarizer (and remaining audit logic) from Python to Go (Go-first alignment) | Migrate orchestrator cache + evidence/summarizer (and remaining audit logic) from Python to Go (Go-first align... |

**Wiring / tech-debt / API** (78)
| ID | MoSCoW | Type | Title | Objective |
|---|---|---|---|---|
| BI-0185 | Should | feature | EPIC: Multi-modal / media orchestration (pluggable capability packs) | Make the pipeline modality-agnostic via PLUGGABLE capability packs, enabled per project when the idea needs th... |
| BI-0195 | Should | feature | EPIC: Pluggable/modular core + industry-standards adoption (MCP, A2A, AG-UI, OTel) | Everything variable is a plugin behind a port; the core depends only on ports. Adopt the open standards so we ... |
| BI-0209 | Should | feature | Backend: OCR/document capability pack + doc-parse kind + OCR generators/adapters | An `ocr` capability pack with a `ocr/doc-parse` kind, permissive self-host defaults, and paid API options -- e... |
| BI-0220 | Should | feature | EPIC: pipeline E2E reliability - events, readiness checklist, model registry/capability gate, lock/status fixes | EPIC: pipeline E2E reliability - events, readiness checklist, model registry/capability gate, lock/status fixe... |
| BI-PF-0331 | Should | chore | OS/shell neutrality: remove PowerShell-only scripting/doc workarounds | Make every scripted workflow and documented command cross-platform: pure Python entrypoints, a single shell-ne... |
| BI-PF-0360 | Must | epic | EPIC: Backlog SSOT + Work Scheduler + Pluggable Worker Orchestration (doc: PF-Backlog-SSOT-Scheduler-Pluggable-Workers) | EPIC: Backlog SSOT + Work Scheduler + Pluggable Worker Orchestration (doc: PF-Backlog-SSOT-Scheduler-Pluggable... |
| BI-PF-0374 | Could | feature | PFSSOT-P12: optimization (only after correctness) | PFSSOT-P12: optimization (only after correctness) |
| BI-PF-0386 | Should | feature | PF platform: IP-value assessment of all modules (rewrite-by-value ranking: high-value -> Go/Rust, low-value -> compiled) | PF platform: IP-value assessment of all modules (rewrite-by-value ranking: high-value -> Go/Rust, low-value ->... |
| BI-PF-0387 | Should | feature | PF platform delivery baseline: ONE source for all editions; new shipped/sensitive logic -> Go; existing -> compiled (Nuitka); no raw .py at customer; migrate by value later | PF platform delivery baseline: ONE source for all editions; new shipped/sensitive logic -> Go; existing -> com... |
| BI-PF-0391 | Should | epic | EPIC B: PF Scale & Editions (gateways, persistence, OEM, Rust, WASM, decomposition, migration) | EPIC B — B1 PF Go core (compiled host, architectural/mandatory); B2 gateways (Model/Tool/Memory/Infra); B3 per... |
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
| BI-PF-1202 | Should | epic | EPIC: Security / Privacy / Compliance (CISO view) - posture doc, privacy controls, provable compliance, no false claims | A CISO-grade posture: one security-architecture doc (data flow, trust boundaries, controls, risk register, fra... |
| BI-PF-1204 | Should | feature | C2: Privacy controls (DPDP/GDPR) - data-subject rights, retention, DPIA, consent as a gate + artifacts | C2: Privacy controls (DPDP/GDPR) - data-subject rights, retention, DPIA, consent as a gate + artifacts |
| BI-PF-1207 | Should | feature | C5: AI Security Control Plane - Risk engine + Policy engine (+ policy versioning) | C5: AI Security Control Plane - Risk engine + Policy engine (+ policy versioning) |
| BI-PF-1209 | Should | feature | C7: Secret broker (model sees credential_ref, never the secret; inject only into the authorized runtime) | C7: Secret broker (model sees credential_ref, never the secret; inject only into the authorized runtime) |
| BI-PF-1210 | Should | feature | C8: Sandbox + Network/Egress policy for code/autonomous execution | C8: Sandbox + Network/Egress policy for code/autonomous execution |
| BI-PF-1211 | Should | feature | C9: RAG/Document guardrail + trust levels (untrusted content can never gain authority) | C9: RAG/Document guardrail + trust levels (untrusted content can never gain authority) |
| BI-PF-1213 | Should | feature | C11: Kill switch (independent of the LLM) - stop workflow/agent/tool/schedule/deploy/connectors | C11: Kill switch (independent of the LLM) - stop workflow/agent/tool/schedule/deploy/connectors |
| BI-PF-1215 | Should | feature | C13: Per-generated-product Security Profile/Manifest derived from product capabilities | C13: Per-generated-product Security Plan/Guidelines + Profile/Manifest, GENERATED from the PF guidelines SSOT ... |
| BI-PF-1218 | Should | feature | C16: Fail-safe behaviour policy (+ controlled security-policy improvement, never model-autonomous) | C16: Fail-safe behaviour policy (+ controlled security-policy improvement, never model-autonomous) |
| BI-PF-1219 | Should | feature | C17: security_impact review decision on every work item + advisory validator (per-work security impact analysis) | Make "security impact for every work" first-class and enforced at the same boundary as api/dashboard impact: e... |
| BI-PF-1220 | Should | feature | C18: PF security plan/guidelines SSOT (global, enforceable) - for PF itself and its agents | ONE PF-level security plan/guidelines SSOT that governs **PF itself and its agents** (the enforcing plane). Th... |
| BI-PF-1221 | Should | feature | C19: Security implementation agent (review from guidelines SSOT + IMPLEMENT controls per iteration) + S3 gate | Security becomes an IMPLEMENTER, per iteration, not a post-hoc reviewer. Each implementation iteration reviews... |
| BI-PF-1237 | Should | feature | Per-item time tracking: execution.duration_seconds + attempt + time rollup | - job_manager.complete()/fail(): record execution.duration_seconds (wall-clock from started_at) + increment at... |
| BI-PF-1240 | Should | feature | Graceful orphan/stuck recovery: reap expired+stuck assignments, clean worktrees, wg recover | - job_manager: renew_lease/claim set execution.last_heartbeat_at; recover_expired also reaps STUCK assignments... |
| BI-PF-1246 | Should | feature | Delivery lane reconciliation + auto-issue/auto-RCCA on validation FAIL + app_boot checker fix | - delivery.reconcile(): remote truth (PR state + origin/develop tip) vs item state; hooks on worker start + wg... |
| BI-PF-1247 | Should | feature | Worker-delivered PRs satisfy FEATURE_PR gates: review/lint/structure run-bound records on work complete | - work complete (manual + auto) runs the gate recorders in the worktree before handing to the lane: lint recor... |
| BI-PF-1248 | Should | epic | EPIC: Tech Debt & Repo Hygiene (generated artifacts, script drift, gate gaps) | One home for repo-hygiene / tech-debt work that is not a product feature: generated-artifact freshness, script... |
| BI-PF-1252 | Should | epic | Unscoped | Unscoped |
| BI-PF-1259 | Should | change | CI/CD review & optimization: clear change-based gate/test/profile mapping (de-ambiguate commit/merge/push/CI) | A reviewed, optimized CI/CD that is explicit and change-aware: - One authoritative mapping: change type -> whi... |
| BI-PF-1265 | Should | epic | EPIC: Eventing & Alerting SSOT - Go-first event bus + subscriber/alert transports | One SSOT event+alert bus used by all of PF. Producers emit once; consumers subscribe through stable contracts ... |
| BI-PF-1269 | Should | feature | Eventing SSOT (Go): subscriber registry + dispatcher (cursor, at-least-once, dedupe, retry->DLQ) | Persisted subscriber registry (single writer, store-registry entry) + a dispatcher that fans out with at-least... |
| BI-PF-1270 | Should | feature | Eventing SSOT (Go): transports - inproc callbacks, webhook (HMAC+idempotency), notify/email | Pluggable transports behind one interface: inproc (callbacks), webhook (HTTP POST, HMAC signature, idempotency... |
| BI-PF-1271 | Should | feature | Eventing SSOT (Go): alert policy - rules, throttle, escalation | A policy engine mapping event type/severity -> channels with throttle and escalation (reusing the policy map). |
| BI-PF-1272 | Should | feature | Eventing SSOT: Python thin-client cutover of core/events.py over the A1 wire seam (edit-only) | core/events.py (edit-only, no new module) delegates emit to the Go core via core/go_host while keeping its pub... |
| BI-PF-1275 | Should | feature | Eventing SSOT: bus daemon/service run model + ops (start/stop/status) | A Go bus daemon run model with start/stop/status (reuse the portfolio supervisor pattern) invoked via API. |
| BI-PF-1276 | Should | feature | Eventing SSOT: retire legacy websocket push (frozen dashboard -> SSE) | Stop extending the legacy WS; migrate its consumers to SSE; retain (never delete) until the new UI lands. |
| BI-PF-1277 | Should | epic | EPIC: Product-generation run (dogfood) execution + monitoring correctness | dogfood drives the same engine to completion (all stages/agents), then validates the generated product and ret... |
| BI-PF-1278 | Should | feature | dogfood: drive pipeline to completion + correct post-run validation + fail-closed verdict | Wait for the run to finish (bounded), validate the GENERATED product dir, and map terminal states fail-closed. |
| BI-PF-1280 | Should | feature | dogfood: monitoring - wait/poll + terminal event/webhook + status aggregation | Expose progress via the shared bus: poll (run_status/events) + subscribe (SSE/webhook) + aggregate status. |
| BI-PF-1281 | Should | task | core/contracts.py imports jsonschema but it was not a declared dependency | core/contracts.py imports jsonschema but it was not a declared dependency |
| BI-PF-1288 | Must | task | Issue id collision: a local session minted IS-PF-0038 already present on develop | Issue id collision: a local session minted IS-PF-0038 already present on develop |
| BI-PF-1304 | Must | feature | EDP-12: Generated-product residency manifest (data_classes/home_region/allowed_regions/backup/kms/egress/retention) + build/deploy gate | Generate a per-product residency manifest (data_classes, home_region, allowed_regions, backup, kms, egress, re... |
| BI-PF-1323 | Must | chore | Harden sync_develop on a dirty/noisy working tree (untracked collisions; merge refused; generated-file hygiene) | A sync that just works on a realistic (noisy) working tree, so "sync often" stays reliable. |
| BI-PF-1324 | Should | chore | Concurrent sessions: uniquely-name scratch/temp files (avoid shared temp-dir collision) | Concurrent sessions never collide on scratch files. |
| BI-PF-1326 | Must | feature | WG-O2: Start-from-anywhere wrapper (fetch -> pull --ff-only clean-guard -> shared token -> start) + periodic fetch-only thread | Add a start wrapper (sync + token + start) and a periodic fetch-only background thread. |
| BI-PF-1330 | Should | task | Failed stage blocks all re-runs: checkpoint restore keeps the failed stage (new/--from-stage fail immediately) | Failed stage blocks all re-runs: checkpoint restore keeps the failed stage (new/--from-stage fail immediately) |
| BI-PF-1333 | Should | task | Design stage over-proportions output: 19 FRs + 15 NFRs for one trivial feature; 314KB partial blows run time/cost | Design stage over-proportions output: 19 FRs + 15 NFRs for one trivial feature; 314KB partial blows run time/c... |
| BI-PF-1370 | Should | feature | Session isolation guard: never write outside the session's own working folder (hard ACL long-term + single-account alternative now) | A session can only affect its OWN working folder: cross-folder writes are prevented (long-term, hard) or at le... |
| BI-PF-1371 | Must | feature | Session isolation guard: never write outside the session's own working folder (hard ACL long-term + single-account alternative now) | A session can only affect its OWN working folder: cross-folder writes are prevented (long-term, hard) or at le... |
| BI-PF-1374 | Should | feature | precheck: a derived/bookkeeping-only tier (docs-fresh + compile only) so doc/backlog regeneration never runs the full gate | Add a derived/bookkeeping-only precheck tier (docs-fresh + compile) and stop doc-regen running the full gate. |
| BI-PF-1388 | Should | epic | EPIC: Generation Proportionality - artifact contract + project profile drive generation (bounded by construction) | Bounded by construction: ONE lever (artifact contract x project-size profile x kind) drives each agent's secti... |
| BI-PF-1389 | Should | task | Wire the artifact contract + project-size profile into generation (single source for the section plan) | The resolved contract (required vs optional sections per profile + counts + size) becomes the single source fo... |
| BI-PF-1391 | Should | task | Project-size profile lever: small/medium/large selects required vs optional sections + counts bands + size budget | One lever scales depth: small -> required sections only, low counts, small budgets; medium -> recommended; lar... |
| BI-PF-1393 | Should | task | Verify small/medium/large profiles on MyToDo (no over-scope) + close BI-PF-1333 | Prove a trivial run stays proportionate per profile and close BI-PF-1333. |
| BI-PF-1410 | Must | feature | Hard DoD gate: every item needs detailed Acceptance Criteria + independent verification (verifier != implementer) before close/merge | Hard DoD gate: every item needs detailed Acceptance Criteria + independent verification (verifier != implement... |
| BI-PF-1414 | Should | defect | RCCA: schema designed without field-level reconciliation vs the owning port (artifact schema mismatched datastore.Artifact) - found only at C1b | RCCA: schema designed without field-level reconciliation vs the owning port (artifact schema mismatched datast... |
| BI-PF-1416 | Should | feature | Automate PF persistence setup: one-command provisioning + roles + migrations + storage config + secrets + verify (dev and SaaS) | Automate PF persistence setup: one-command provisioning + roles + migrations + storage config + secrets + veri... |
| BI-PF-1424 | Must | feature | Consolidate Python orchestrator audit (AgentAuditLog) into the DB AuditStore - single audit truth via /audit | Consolidate Python orchestrator audit (AgentAuditLog) into the DB AuditStore - single audit truth via /audit |
| BI-PF-1426 | Should | change | Harden auto-loaded config against schema mixing + tooling writes outside the repo (residency-profiles vs residency-cells) | Make schema-mixing in auto-loaded dirs and out-of-repo tooling writes fail loudly, repo-wide. |
| BI-PF-1431 | Must | feature | Design & implement the PF server/service + token model (sharing for internal/external callers) | Design & implement the PF server/service + token model (sharing for internal/external callers) |
| BI-PF-1433 | Should | feature | ObjectStore adapter: Azure Blob (on go/objstorerest) | ObjectStore adapter: Azure Blob (on go/objstorerest) |
| BI-PF-1434 | Should | feature | ObjectStore adapter: Google Drive (design key<->fileID model first) | ObjectStore adapter: Google Drive (design key<->fileID model first) |
| BI-PF-1435 | Should | feature | GCS ObjectStore adapter: streaming/resumable upload + wire buildObjectStore (production-qualification) | Remove the GCS adapter's memory buffering/5 MB ceiling and wire it on the runtime path. |
| BI-PF-1437 | Should | feature | Framework-agnostic skills home + resolver | PF owns the skill bodies; .opencode is a legacy fallback only. |
| BI-PF-1439 | Should | feature | Design-system catalog store + selection engine (Go) | PF can SELECT a ranked design direction from the idea. |
| BI-PF-1440 | Should | feature | Design-token engine upgrade (3-tier OKLCH, light+dark) | Generate real design tokens from the selected direction. |
| BI-PF-1445 | Should | feature | design_critic / visual_qa integration (anti-patterns + catalog + aesthetics) | QA validates against the chosen direction, non-negotiables and anti-patterns. |

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
- backend: 134 open / 595 closed
- dashboard: 146 open / 3 closed
