# EDP-17 Canonical Schema — Domain & Relationship Model

**Owner:** EDP-17 (`BI-PF-1309`), epic `BI-PF-1292`. Migration: `product-forge/migrations/0002_core_schema.{up,down}.sql`.
**Derived from a full repository discovery** of `config/store-registry.json` (~170 stores, 24 kinds), `core/` owners, `api/routers/`, `config/*.json`, `agents/*.agent.json`. Citations = `file:line` in the codebase.

> This is the **model** (entities + relationships + ownership). The **DDL** lands in slices (`0002`, `0003`, …); domain tables owned by other EDP items attach by FK.

## A. Global conventions (must mirror PF's existing model)
1. **Two scopes** are pervasive: `product_forge` (repo `data/`) and `project` (`products/<project>/`) — model as `scope TEXT` + `project TEXT` discriminators (`core/backlog.py:111-123`).
2. **Id families are the PK namespaces** (opaque TEXT, app-allocated, no DB sequences): `BI-*` items, `IS-*` issues, `TC-*` task-contracts, `IN-*` intake, `AS-*` assets, `RV-*` reviews, `LN-*` learnings, `CHG-*` changes, `F-*` features, `REQ-*` requirements, `run-<epoch>`, `run_id`, `job_id`, `lease_id` (`config/spec-id-families.json`; `core/id_allocator.py`).
3. **Work traceability:** artifacts reference **`item_id`** (`BI-####`) and add **`feature_id`** (`F-x`) — soft refs (cross-scope), indexed (`store-registry.json:1624`; `core/agent_ledger.py:18-66`).
4. **Tenant-scoped rows:** `tenant_id` FK (+ index; RLS by EDP-09). **Mutable rows:** `version BIGINT` + `created_at`/`updated_at`. **Derived stores are VIEWS**, not base tables (open.json, run-status.json, manifests).
5. **Legacy/frozen EXCLUDED:** the legacy dashboard (`config/legacy-frozen.json`), `dashboard-blueprint.json`, deprecated `conversation_models`/`product_analyzer`/`views`, legacy test-framework aliases, migrated legacy budget files.

## B. Domains → entities → owner (all discovered)

| Domain | Key entities | Owner module (evidence) |
|---|---|---|
| **Identity / Tenancy / Security** | Tenant, User, Session, Setting, Member, LicenseKey, TenantSubscription, Tier, FeatureGroup/Entitlement, ProviderKeyRef, ToolSecret | `core/control_plane.py:36-111`, `core/licensing.py:1-117`, `core/tenancy.py:88-116`, `core/credentials.py:70-98` |
| **Products / Projects / Generated** | Project(+Config/InitialContext), Product, ProductPlan, **Feature(F-x)**, DesignSpec, TechStack, Infra/Ports, FeatureFlag, ArchiveEntry, ForgeRunState | `core/project_store.py:46-100`, `core/product_page.py:44-91`, `core/product_plan.py:15-95`, `core/product_design_spec.py:13-77`, `core/forge_store.py:56-90` |
| **Pipeline / Workflow / Stages** | PipelineDefinition, Stage(id,depends_on,sub_agents,approval_gate), PipelineState, PipelinePlan, RunPlan, PlanReview, Task(`<stage>:<agent>`), EngineeringStep, ArtifactPathMap | `pipeline-definition.json:64-1474`, `api/routers/pipeline.py:57-114`, `core/run_plan.py:61-70`, `config/engineering-flow.json:12-32` |
| **Runs / Jobs / Leases** | Run(`run-<epoch>`), Job, WorkerQueueItem, **Assignment/Lease**, PortfolioRegistry/State, RunStatus, Control, Reservation, WorkerRegistration, Capacity, RunManifest, TaskContract | `core/run_state.py:91-115`, `core/job_manager.py:21-118`, `core/portfolio.py:1-63`, `core/reservations.py`, `core/run_manifest.py:62-96` |
| **Agents / Runtime** | AgentCard/Spec/Contract, AgentHierarchy, AgentRequirements/CapabilityVector/Binding, AgentModelOverride, AgentReadiness, ModelGate, **AgentWork(item_id/feature_id)**, AgentMessage, Delegation, Checkpoint/Context, Skill, MCPServer, Plugin | `agents/implement.agent.json:1-49`, `core/agent_spec.py:42-64`, `core/agent_structure.py:34-100`, `core/agent_ledger.py:18-66`, `core/agent_runtime.py:31-63`, `core/skills_registry.py:23-80` |
| **Artifacts / Multimodal / Object-store** | ArtifactMeta(`stage/agent`,sha256,run_id), Stage/ProjectArtifacts, RunManifest, **Asset(AS-*,children[],item_id)**, GeneratorJob, MediaPart, ArtifactFormats, QIR/qa-manifest/quality-metrics/go-no-go, CrossReview/ReviewFeedback/ReviewLedger | `core/artifact_store.py:16-49,209-222`, `core/asset_store.py:99-142`, `core/multimodal.py:44-90`, `core/cross_review.py:23-68`, `core/review_ledger.py:30-76` |
| **Memory / RAG / Embeddings** | MemoryEntry(8 types), MemoryQuery/CompiledKnowledge, ExportBundle, KnowledgeIndex/graph, semantic cache | `core/agent_memory.py:62-190`, `core/memory_api.py:16-34` |
| **Events / Outbox / Cache** | Event(event_id,type,run_id,stage_id,task_id,worker_id,correlation/causation_id,payload), OrchestrationEvent, IdempotencyRecord, ToolCache, InputCache, OTelSpan | `core/events.py:43-63`, `core/event_bus.py:29-45`, `api/idempotency.py`, `core/orchestrator/storage.py:13-79` |
| **Audit** | AuditEntry(action,agent,stage,run_id), AgentAuditLog, Change(CHG-*), PIDLDecision, Escalation/StopCondition | `core/audit_trail.py:48-75`, `core/change_log.py:21-79`, `api/routers/engineering.py:196-257` |
| **Intake / Backlog / Epics / Links** | **BacklogItem**, BacklogIndex(derived), Counters, ItemHistory, Epic, **Issue(IS-*,backlog_ref 1:1)**, Intake(IN-*), Conversation, Idea, Requirement, Decision, ChangePackage, ImplementationPlan, GroomingGuidelines, IdBlock | `items/<ID>.json` (`core/backlog.py:20-28,814-827`), `core/issues.py:1-23`, `core/conversation_models.py:22-160`, `core/intake_channels.py` |
| **Usage / Quotas / Budget** | Budget(+SpendRecord/Window/Alert/StageAllocation), BudgetUsage, CallLedger, WorkEstimate, Capacity/quota, CostModel, ProviderHealth | `core/budget.py:40-130`, `core/budget_tracker.py:13-40`, `core/call_ledger.py:54-94`, `core/provider_health.py:47-50` |
| **Packaging / Deploy / Releases** | PackagingManifest, Edition, EAP, BOM, **Build**, Version, ReleaseEvidence, DeploymentEvidence, ReleaseManifest, DeployConfig/Provider, ToolCatalog, Generator | `core/packaging.py:57-120`, `core/bom.py:28-37`, `core/build_manager.py:66-67`, `core/release.py:29-77`, `core/deploy_providers.py:77-100` |
| **Tests / Evidence / Traceability** | TraceabilityMatrix, FeatureStatus(feature_id), TestCycle, TestComment/Entry, TestMatrix/Suite, **ValidationRun(profile,checks,result)**, ValidationProfile, VerificationPolicy, PRRecord, WorkerResult, QualityGate, CI/CD Gate | `core/traceability.py:76-120`, `core/validation_engine.py:90-105`, `api/routers/github.py:36-91`, `core/worker.py:30-34` |
| **Knowledge / Registry / Problems / Insights** | Defect, Insight(item_id), KnowledgeEntry/Skill/Techstack/Domain/Guideline/MCP, Learning(LN-*), LearningCandidate, BusinessModelKB, TechstackCatalog | `test-framework/core/defect_tracker.py:27-58`, `core/insights.py:54-67`, `core/knowledge_registry.py:33-89`, `core/learnings.py:83-90`, `core/learning_synth.py:50-67` |
| **Settings / Secrets** | ToolSettings, ToolSecret, ProviderKeyRef, EnvFlags, Persona, ApprovalPolicyRule, GuardrailPolicy, ModelPolicy, ContextPolicy, AgentOverlays, Notification | `core/tool_settings.py`, `core/credentials.py`, `config/approval-policy.json:1-21`, `core/alerts.py` |

## C. Cross-domain relationship graph (A —key→ B)
```
Tenant —tenant—< User —id—< Session ; Tenant —< Member ; Tenant —< LicenseKey —tier→ Tier —groups→ FeatureGroup
Project —product→ Product —versions—< Build ; Project —idea→ Conversation —< Idea —< Requirement/Decision/ChangePackage
BacklogItem —epic/parent→ Epic(BacklogItem) ; BacklogItem —blocked_by/unlocks/dependencies→ BacklogItem ; —paired_with→ BacklogItem
BacklogItem —links.feature_id→ Feature —backlog_id→ BacklogItem ; Feature —< Requirement  [Traceability requirement_id↔feature_id]
BacklogItem —links.conversation_id/idea_ids/cp_ids/iteration_ids→ Conversation/Idea/ChangePackage/Iteration
BacklogItem —links.issue→ Issue —backlog_ref→ BacklogItem (1:1) ; BacklogItem —links.defect_ids→ Defect
BacklogItem —execution.item_id/worker_id/assignment_id/lease_id→ Assignment —worker_id→ WorkerRegistration
TaskContract(TC-*) —epic_id/feature_id/parent_task_id/blocked_by→ Epic/Feature/TaskContract ; —run_id→ Run
Run(run_id) —< Stage —depends_on→ Stage ; Stage —sub_agents/depends_on→ Agent ; Attempt —stage_id→ Stage
Run —< Job(item_ids→BacklogItem, run_id, assignment_id/lease_id) ; Run —< Event/CallLedger/AgentWork/AgentReadiness/ValidationRun/ReleaseEvidence
Agent —parent→ Agent ; Agent —capability→ Knowledge/Skill/MCP ; AgentWork —item_id/feature_id→ BacklogItem/Feature
Artifact(stage/agent, sha256) —metadata.run_id→ Run ; Asset(AS-*) —children→ Asset ; —item_id→ BacklogItem ; —< GeneratorJob
Defect —affected_features→ Feature ; Defect —fix_commit→ git ; Insight —project→ Project ; Insight —item_id→ BacklogItem
LearningCandidate —scope→ project/area ; —applied→ Learning/AgentOverlay/KnowledgeEntry —agents[]→ Agent
PackagingManifest —edition→ Edition ; —sbom→ BOM ; —build→ Build ; —entitlement→ Tier ; DeploymentEvidence —provider→ DeployProvider
Event —correlation_id/causation_id→ Event (self) ; Reservation —holder_task/holder_worker/run_id→ Task/Worker/Run
Budget —history—< SpendRecord ; —> CallLedger/Usage ; IdBlock —(scope,project,session)—> BacklogItem.id allocation
```

## D. Ownership across EDP items (schema slices)
- **EDP-17 (slice 1, `0002`)**: Identity/Tenancy (tenants, memberships, + users/sessions/settings), Products/Projects, Pipeline/Stages defs, Runs/Attempts, Reservations, Usage/Quotas/Budget, Packaging/Builds.
- **EDP-17 (slice 2+)**: Agents/runtime, Events/Outbox/Jobs/Leases, Idempotency, Knowledge/Registry, Settings/Secrets.
- **EDP-15**: Artifacts/Asset/stored_objects + artifact_types + Review*.
- **EDP-18**: Intake/**Backlog/Epics/ItemLinks/ItemHistory/Issue** (+ cutover).
- **EDP-19**: Events/Outbox/Jobs/Leases (durable job store).
- **EDP-20**: Audit (audit_log, changes, PIDL decisions).
- **EDP-21**: Memory/RAG/embeddings (+ pgvector).
- **Dashboard / derived stores**: **views**, not tables.

## E. Status
Model is complete (full discovery). **Slice 1** (`0002_core_schema`) delivered = tenants/memberships/projects/runs/stages/attempts/usage/quotas. Next: expand `0002`+ add `0003`… per §D, then the Go DAL (`product-forge/go/store`). Order: `docs/EDP-EXECUTION-ORDER.md`.
