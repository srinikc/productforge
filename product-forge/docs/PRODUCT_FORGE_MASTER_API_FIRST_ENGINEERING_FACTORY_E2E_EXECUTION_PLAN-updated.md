# Product Forge — Master API-First → Engineering Factory → E2E Execution Plan

**Status:** Governing master execution plan  
**Date:** 2026-10-01  
**Purpose:** Define the complete, ordered implementation and execution flow for Product Forge, starting with API-first contracts and continuing through engineering-worker orchestration, Git/GitHub lifecycle, validation, dogfood, release, packaging, deployment, and future UI clients.

---

# 1. Executive Decision

Product Forge will be implemented and operated in this order:

```text
API-FIRST FOUNDATION
        ↓
PRODUCT FORGE CORE RUNTIME CONTRACTS
        ↓
ENGINEERING WORKER / TASK ORCHESTRATION
        ↓
GIT / WORKTREE / BRANCH ORCHESTRATION
        ↓
GITHUB / PR / CI ORCHESTRATION
        ↓
COMMON VALIDATION FACTORY
        ↓
FEATURE_PR
        ↓
INTEGRATION
        ↓
DOGFOOD
        ↓
RELEASE
        ↓
PACKAGE / ENTITLE / DEPLOY
        ↓
FUTURE DASHBOARD / ADDITIONAL CLIENTS
```

The API-first program is therefore the **contract and control-plane foundation**, not the entire Product Forge engineering factory.

The engineering factory then consumes those contracts.

The final system is:

```text
                         PRODUCT FORGE
                              |
                  +-----------+-----------+
                  |                       |
             API / Control           Runtime /
               Contracts            Application Services
                  |                       |
                  +-----------+-----------+
                              |
                    Engineering Orchestrator
                              |
          +-------------------+-------------------+
          |                   |                   |
       Workers             Git/GitHub          Validation
          |                   |                   |
      OpenCode            Branch/PR/CI       4 common modes
      PF-native           Integration        FEATURE_PR
      Other agents                          INTEGRATION
      Human-assisted                         DOGFOOD
                                             RELEASE
                              |
                         Evidence / Gates
                              |
                 Package / Release / Deploy
                              |
             +----------------+----------------+
             |                                 |
        OpenCode TUI                    Future Dashboard
        / CLI / MCP                     / AG-UI / clients
```

---

# 2. Governing Architecture Principles

## 2.1 Product Forge owns the system

Product Forge has **separate control-plane entry paths with different semantics**. They must remain distinct throughout MASTER-0 through ENG-4 and beyond:

```text
EXTERNAL INGESTION
External client → Intake API → requirement/change normalization → backlog/change package → engineering task

ENGINEERING EXECUTION
OpenCode / CLI / coding agent / human terminal → Task/Work API → run → scheduler → worker

VALIDATION
Commit / branch / PR / run → Validation API → Validation Engine
```


Product Forge owns:

- contracts
- APIs
- orchestration
- task lifecycle
- worker lifecycle
- validation
- evidence
- gates
- governance
- lifecycle
- Git/GitHub integration policy
- defect/RCCA integration
- backlog integration
- packaging/release policy
- deployment policy
- auditability

OpenCode, Claude, Gemini, coding agents, MCP clients, or future worker frameworks are adapters.

Canonical rule:

> **Product Forge owns the contracts, orchestration, validation, evidence, governance and lifecycle. Agent frameworks are replaceable execution adapters.**

---

## 2.2 OpenCode is not the engineering brain

OpenCode may provide:

- coding worker execution
- interactive TUI
- agent session
- repository interaction
- implementation assistance

OpenCode must not become the authoritative source for:

- Product Forge state
- validation truth
- task truth
- worker truth
- evidence truth
- GitHub lifecycle truth
- API contracts
- orchestration architecture
- quality gates

Target:

```text
Product Forge
    |
    +-- PF APIs
    +-- PF Events
    +-- PF Application Services
    |
    +-- OpenCode Adapter
    +-- PF-native Worker
    +-- Future Worker Adapter
    +-- Human-assisted Worker
```

---

## 2.3 Future Dashboard is a client, not the architecture

The legacy Dashboard is explicitly excluded from this implementation.

Do not use it as:

- architecture authority
- API authority
- state authority
- orchestration authority
- validation authority

Future Dashboard:

```text
Future Dashboard
       |
       +--> PF REST APIs
       +--> PF Event API
       +--> AG-UI projection
```

The backend must not be redesigned for the future Dashboard.

---

## 2.4 Archive is excluded

`product-forge/archive/` is historical.

It must not be:

- inspected for current architecture
- reused
- treated as current capability
- used as validation evidence
- used as a gap baseline

If a capability exists only there, it is **not implemented in current Product Forge**.

---

# 2A. Entry-Path Contract and Retroactive Reconciliation

**Intake is one external requirement-ingestion path; all executable engineering work uses the canonical Task/Work contract regardless of origin.**

This separation is normative and must be retroactively reconciled across **MASTER-0 through ENG-4**. Preserve completed work, audit existing/in-progress implementation for violations, correct any routing that makes Intake a prerequisite for direct engineering, test both entry paths, and continue from the current phase. Do not restart unless a real dependency or contradiction is discovered.

# 3. Current Authoritative Product Forge Components

The implementation must reuse the existing current components before creating anything new.

Important current components include:

```text
core/backlog.py
core/run_entry.py
core/pipeline_executor.py
core/orchestrator/*
core/orchestrator/agent_runner.py
core/orchestrator/agent_execution.py
core/verification_runner.py
core/verification_policy.py
core/pr_gate.py
core/defect_loop.py
core/vcs.py
core/git_manager.py
core/events.py
core/agui.py
core/artifact_store.py
core/agent_ledger.py
core/control_plane.py
core/run_status.py
core/issue_tracker.py
config/store-registry.json
scripts/run_pipeline.py
.github/workflows/*
.opencode/*
```

Important consolidation rule:

- reuse `backlog.py` as canonical backlog
- reuse `run_entry.py` as canonical run entry
- reuse `pipeline_executor.py` as canonical pipeline engine
- reuse existing orchestrator components
- reuse `verification_runner.py` as validation execution foundation
- reuse `verification_policy.py` for validation policy
- reuse existing defect/RCCA bridge
- consolidate `vcs.py` and `git_manager.py`; do not create a third Git manager
- reuse `events.py` as event foundation
- reuse `artifact_store.py`
- reuse `agent_ledger.py`
- reuse `config/store-registry.json`
- do not create duplicate engines/stores

---

# 4. Master Execution Dependency Graph

The complete implementation order is:

```text
MASTER-0
Current-state / architecture truth
        |
        v
API-0
API discovery
        |
        v
API-0.1
API contract reconciliation
        |
        v
API-1
API foundation
        |
        v
API-2
Core PF APIs
        |
        v
API-3
Engineering / validation APIs
        |
        +--------------------------+
        |                          |
        v                          v
ENG-0                        API-4
Engineering architecture    Enterprise/SaaS/OEM
        |                    APIs
        v                          |
ENG-1                              |
Worker/task contracts              |
        |                          |
ENG-2                              |
Work planner/scheduler             |
        |                          |
ENG-3                              |
Git/worktree/branch                |
        |                          |
ENG-4                              |
Worker adapters/OpenCode           |
        |                          |
ENG-5                              |
GitHub/PR/CI                       |
        |                          |
        +-------------+------------+
                      |
                      v
API-5
API hardening + event + contract CI
                      |
                      v
ENG-6
Validation Factory
                      |
                      v
ENG-7
FEATURE_PR lifecycle
                      |
                      v
ENG-8
INTEGRATION lifecycle
                      |
                      v
ENG-9
DOGFOOD lifecycle
                      |
                      v
ENG-10
RELEASE lifecycle
                      |
                      v
REL-0
Package / entitlement / deployment
                      |
                      v
MASTER-1
Full Product Forge dogfood
                      |
                      v
MASTER-2
Final audit / production readiness
```

### Important parallelism rule

`API-4` may proceed in parallel with engineering work once its prerequisites are satisfied.

It must not unnecessarily block engineering orchestration.

However:

```text
API-1 → API-2 → API-3
```

is the critical dependency chain for the engineering factory.

`API-5` hardening should be completed before declaring the overall API surface production-ready, even if selected engineering work begins earlier.

---

# 5. MASTER-0 — Current-State Architecture Truth

## Objective

Create one authoritative current-state map before changing architecture.

## Inspect

Current non-archived:

```text
core/
config/
scripts/
products/
docs/
.github/
.opencode/
current PF API layer
test-framework/
```

Exclude:

```text
product-forge/archive/
legacy Dashboard implementation
```

## Determine

- current API server and entrypoint
- current API routes
- application services
- runtime execution path
- pipeline execution path
- agent execution path
- validation path
- Git/VCS path
- GitHub integration
- event path
- artifact path
- issue/defect path
- backlog path
- current OpenCode adapter
- current engineering-session entry path
- current Task/Work API or equivalent application service
- current Run/Worker/Scheduler entry path
- current CI
- existing E2E tests
- duplicate mechanisms
- missing mechanisms
- stale/deprecated code
- unresolved architecture contradictions

## Gate

Do not implement architecture changes until:

- current paths are traced
- canonical components are identified
- duplicates are mapped
- unknowns are recorded
- archive is excluded
- legacy Dashboard is excluded
- no hidden assumption remains

---

# 6. API-0 — API Discovery

Follow the existing API implementation plan.

Required output:

```text
Current API server
Current API entrypoint
Current direct engineering-session entry path
Current Task/Work API or equivalent engineering application service
Current Run/Worker/Scheduler path
Current API consumers by entry type
Existing contracts
Existing tests
Existing application services
Duplicate mechanisms
Unknowns
Required changes
Affected files
Dependencies
Risks
```

Verify the actual FastAPI wiring, OpenAPI, application services, tests, and API consumers.

Do not assume that a documented API is externally runnable until the actual server wiring is verified.

---

# 7. API-0.1 — Contract Reconciliation

Establish:

- canonical `/api/v1`
- resource naming
- request envelope
- response envelope
- error model
- request ID
- correlation ID
- idempotency
- authentication
- authorization
- tenant context
- audit
- versioning
- compatibility
- deprecation
- event correlation
- OpenAPI ownership
- entry-path semantics
- client-to-resource authorization rules

Canonical request:

```yaml
request_id:
correlation_id:
tenant_id:
actor:
authorization:
idempotency_key:
api_version:
resource:
operation:
payload:
```

Canonical response:

```yaml
request_id:
correlation_id:
status:
resource:
resource_id:
data:
links:
warnings:
error:
```

Canonical error:

```yaml
code:
message:
category:
retryable:
details:
request_id:
correlation_id:
```

Gate:

- naming fixed
- security boundary fixed
- compatibility policy fixed
- idempotency fixed
- error contract fixed
- OpenAPI ownership fixed
- migration sequence fixed

---

# 8. API-1 — API Foundation

Implement/reuse:

- API application boundary
- `/api/v1`
- request context
- request/correlation IDs
- auth boundary
- authz boundary
- tenant context
- common errors
- idempotency
- audit
- logging
- health/readiness
- OpenAPI foundation
- pagination/filter conventions

Establish or reuse the direct engineering control surface:

```text
OpenCode / CLI / Coding Agent / Human Terminal
        ↓
Task / Work API
        ↓
Task / Run / Worker application services
```

Gate:

```text
API starts
API reachable
auth works
authz works
tenant isolation works where applicable
errors conform
IDs propagate
idempotency works
OpenAPI validates
API tests pass
```

---

# 9. API-2 — Core Product Forge APIs

Implement in dependency order:

```text
Project
   ↓
Run
   ↓
Pipeline
   ↓
Stage
   ↓
Task
   ↓
Artifact
   ↓
Evidence
   ↓
Backlog
```

The API must expose Product Forge application capabilities rather than direct file-store manipulation.

Required behavior:

- create/read/update project
- create/start/stop/resume run
- inspect pipeline
- inspect stages
- inspect tasks
- inspect artifacts
- inspect evidence
- inspect/update backlog through canonical services
- resolve/create engineering tasks through the canonical Task/Work service
- start/continue engineering work through the canonical Task/Work path

Long-running actions must return a run/operation identity and use events for progress.

### Task API boundary

The Task API is the direct engineering entry point.

```text
Existing task
   ↓
Task API
   ↓
Resolve / claim / assign
   ↓
Run
```

or:

```text
New engineering request
   ↓
Task API
   ↓
Create engineering task
   ↓
Run
```

The Task API must not manufacture an alternate conversation record merely to start engineering work.

---

# 10. API-3 — Engineering / Validation APIs

This phase creates the control surface required by the engineering factory.

Implement/reuse:

```text
Validation API
Evidence API
Defect/RCCA API
Test API
Gate API
Git/VCS API
Task API
Worker API
Agent API
```

These APIs must map to existing internal systems.

Do not create shadow databases merely because an API exists.

---

# 11. API-4 — Enterprise / SaaS / OEM APIs

Implement according to deployment/commercial requirements:

```text
Tenant
Organization
User
Role
Permission
License
Entitlement
Subscription
Usage
Quota
Billing
Deployment
Release
```

These are required for:

```text
Community
Enterprise
SaaS
On-prem
OEM / White-label
```

API-4 may proceed in parallel with engineering orchestration once its direct dependencies are available.

---

# 12. ENG-0 — Engineering Factory Architecture

Once API-3 contracts exist, define the engineering factory over those contracts.

Target:

```text
External requirement path (when applicable)
      ↓
Requirement normalization
      ↓
Product Plan
      ↓
Architecture
      ↓
Epic
      ↓
Feature
      ↓
Task

OR, for an existing/direct engineering request:

Existing Feature / Bug / Task
      ↓
Task / Work API
      ↓
Task
      ↓
Task Contract
      ↓
Scheduler
      ↓
Worker
      ↓
Worktree
      ↓
Implementation
      ↓
Tests
      ↓
Commit
      ↓
PR
      ↓
CI
      ↓
FEATURE_PR
      ↓
Review/Gates
      ↓
Merge
      ↓
INTEGRATION
      ↓
DOGFOOD
      ↓
RELEASE
      ↓
PACKAGE
      ↓
DEPLOY
```

The engineering factory must be capable of executing this with one worker or many workers.

---

# 13. ENG-1 — Engineering Task Contract

A task is not merely a backlog title.

Minimum conceptual task contract:

```yaml
task_id:
project_id:
epic_id:
feature_id:
parent_task_id:
title:
description:
objective:
acceptance_criteria:
dependencies:
blocked_by:
affected_components:
affected_files:
allowed_paths:
restricted_paths:
required_capabilities:
required_worker_type:
risk:
priority:
validation_profile:
test_requirements:
security_requirements:
performance_requirements:
expected_artifacts:
branch_policy:
repair_policy:
owner:
status:
run_id:
```

A task must be executable by any compatible worker.

A task may originate from an external requirement flow or directly from an engineering client. The worker receives the same canonical task contract regardless of origin. A task must not depend on a particular upstream ingestion mechanism in order to be executable.

---

# 14. ENG-2 — Work Planner and Parallel Scheduler

The scheduler becomes a first-class PF capability.

Responsibilities:

```text
worker registration
worker availability
task discovery from canonical Task/Work service
direct engineering request resolution
task decomposition
task decomposition
dependency graph
prioritization
capability matching
assignment
worktree allocation
branch allocation
file-overlap detection
ownership
change requests
rebase scheduling
PR sequencing
conflict detection
integration queue
failure/recovery
retry/reassignment
resource limits
validation scheduling
reporting
```

Elastic model:

```text
N = available/authorized workers
K = workers safely scheduled
K <= N
```

Never assume a fixed worker count.

Scheduler decisions consider:

- dependency
- file overlap
- module ownership
- shared-core changes
- security sensitivity
- resource availability
- worker capabilities
- integration risk
- task criticality

---

# 15. ENG-3 — Git / Worktree / Branch Orchestration

Git is the source-control execution layer.

GitHub is the remote source/PR/CI system of record.

For every active engineering worker:

```text
Engineering request or existing task
 ↓
Task / Work API
 ↓
canonical task
 ↓
worker assignment
 ↓
fresh worktree
 ↓
feature branch
 ↓
implementation
 ↓
tests
 ↓
commit
 ↓
push
```

Example conceptual branch:

```text
feature/<project-or-area>/<task-id>
```

Validation branches:

```text
validation/<RUN_ID>
```

Do not directly modify:

```text
develop
main
```

unless the repository's controlled merge mechanism performs the merge.

Worktree isolation:

```text
ProductForge/
    .git/

ProductForge-worktrees/
    worker-a/
    worker-b/
    worker-c/
```

Workers must never share a mutable working directory.

---

# 16. ENG-4 — Worker Runtime and OpenCode Adapter

ENG-4 must implement the **direct engineering-session path** through the canonical Task/Work contract.

### Required OpenCode routing

```text
User
 ↓
OpenCode Session
 ↓
PF Task / Work API
 ↓
Resolve existing task OR create engineering task
 ↓
Run
 ↓
Scheduler / Worker
 ↓
OpenCode Worker
 ↓
Worktree
 ↓
Implementation / Tests
```

Before declaring ENG-4 complete, verify and test the direct engineering-session path and confirm that both external and direct origins converge on the canonical Task/Work contract.

Worker abstraction:

```text
WorkerProvider
    |
    +-- OpenCodeWorker
    +-- ProductForgeNativeWorker
    +-- FutureCodingWorker
    +-- HumanAssistedWorker
```

Worker lifecycle:

```text
AVAILABLE
   ↓
ASSIGNED
   ↓
INITIALIZING
   ↓
WORKING
   ↓
TESTING
   ↓
PR_READY
   ↓
INTEGRATING
   ↓
DONE
```

Failure states:

```text
BLOCKED
FAILED
NEEDS_REVIEW
CONFLICT
```

Worker output must normalize into a PF-owned `WorkerResult`.

Conceptually:

```yaml
worker_result:
  task_id:
  worker_id:
  provider:
  run_id:
  worktree_id:
  branch:
  base_commit:
  final_commit:
  status:
  files_changed:
  tests:
  artifacts:
  evidence:
  issues:
  warnings:
  error:
```

OpenCode may produce the implementation, but PF records the normalized result.

---

# 17. ENG-5 — GitHub / PR / CI Orchestration

GitHub owns:

```text
repository
branches
commits
PRs
reviews
CI status
checks
merge state
```

PF orchestrates the lifecycle.

Flow:

```text
Task
 ↓
PF Scheduler
 ↓
Worker
 ↓
Worktree
 ↓
Feature branch
 ↓
Implementation
 ↓
Commit
 ↓
Push
 ↓
PR
 ↓
CI
 ↓
FEATURE_PR validation
 ↓
Review
 ↓
Required gates
 ↓
Merge
 ↓
develop/integration branch
```

PR evidence must include:

```text
RUN_ID
task_id
commit SHA
base SHA
tests
validation result
security result
issues
RCCA
backlog reference
artifacts
```

Never:

- force-push shared branches
- bypass required CI
- disable tests for a pass
- overwrite another worktree
- silently retarget a validation run
- alter evidence after the fact

---

# 18. API-5 — API Hardening and Event Layer

Before production-grade operation:

## Contract governance

- canonical OpenAPI
- schema validation
- compatibility
- breaking-change detection
- versioning
- deprecation

## Security

- authentication
- authorization
- tenant isolation
- validation
- path validation
- request limits
- upload limits
- secret redaction
- replay protection
- rate limiting
- audit
- CORS/CSRF where applicable

## Contract tests

Cover:

```text
request schema
response schema
error schema
authz
idempotency
pagination
compatibility
events
MCP
CLI
external adapters
```

## Event API

Formalize `core/events.py`.

Event envelope:

```yaml
event_id:
event_type:
event_version:
occurred_at:
tenant_id:
project_id:
run_id:
stage_id:
task_id:
worker_id:
actor:
correlation_id:
causation_id:
payload:
```

Events:

```text
run started/completed/failed
stage started/completed/failed
task started/completed/failed
worker started/completed/failed
artifact created
validation started/completed
defect created/resolved
approval requested
human input required
```

REST remains command/query interface.

Events support long-running execution and clients.

---

# 19. ENG-6 — Common Validation Factory

There must be **one Validation Engine**, not separate validation architectures.

```text
                    Validation Factory
                           |
                 Common Validation Engine
                           |
        +----------+-------+-------+----------+
        |          |               |          |
   FEATURE_PR  INTEGRATION     DOGFOOD     RELEASE
```

Same:

- evidence model
- test execution foundation
- policy
- defect/RCCA integration
- GitHub integration
- reporting
- gate framework

Different:

- target
- scope
- depth
- trigger
- repair policy
- promotion gate

---

# 20. Validation Profile Matrix

| Mode | Target | Primary purpose | Default repair |
|---|---|---|---|
| FEATURE_PR | exact PR/branch/commit | validate change before merge | false |
| INTEGRATION | combined integration branch/merge candidate | validate cross-workstream integration | false |
| DOGFOOD | approved PF baseline + real product idea | prove complete E2E product-building capability | controlled, only when authorized |
| RELEASE | release candidate | qualify release | false |

---

# 21. ENG-7 — FEATURE_PR Execution

Exact flow:

```text
PR / branch / commit
        ↓
Resolve exact SHA
        ↓
Resolve base branch
        ↓
Calculate merge-base
        ↓
Fresh validation worktree
        ↓
RUN_ID
        ↓
Changed-file analysis
        ↓
Impact analysis
        ↓
Baseline health
        ↓
Build
        ↓
Unit tests
        ↓
API/contract tests
        ↓
Affected integration tests
        ↓
Security
        ↓
PF-specific checks
        ↓
Regression
        ↓
GitHub checks/evidence
        ↓
PR gate
        ↓
PASS / FAIL / BLOCKED
```

Default:

```yaml
auto_repair: false
```

Feature validation must not modify the developer branch.

If a defect is found:

```text
Validation
   ↓
Issue Tracker
   ↓
RCCA
   ↓
Backlog
   ↓
optional separately authorized repair branch/PR
```

---

# 22. ENG-8 — INTEGRATION Execution

Purpose:

> Validate that independently developed changes work together.

Flow:

```text
Merged candidate / integration branch
        ↓
Exact SHA
        ↓
Fresh worktree
        ↓
Baseline checks
        ↓
Cross-workstream contract checks
        ↓
Integration tests
        ↓
Shared/core regression
        ↓
Security
        ↓
Build/package
        ↓
Required gates
        ↓
INTEGRATION result
        ↓
Promotion decision
```

This is not simply rerunning every FEATURE_PR test.

It emphasizes:

- cross-component contracts
- shared infrastructure
- dependency interactions
- merged behavior
- regression
- integration risks

---

# 23. ENG-9 — DOGFOOD Execution

The existing Product Forge Dogfood & Continuous Validation Runbook remains the detailed execution specification.

Purpose:

> Prove that Product Forge can build a real product end-to-end.

Dogfood validates both:

```text
A. Product Forge as a platform
B. Product generated by Product Forge
```

Flow:

```text
Approved PF baseline
        ↓
Fresh isolated worktree
        ↓
RUN_ID
        ↓
Product idea
        ↓
Deployment target
        ↓
PF baseline health
        ↓
Full PF pipeline
        ↓
Observe every stage
        ↓
Generated product validation
        ↓
Evidence
        ↓
Defect classification
        ↓
Controlled repair if authorized
        ↓
Retest
        ↓
Regression
        ↓
Final report
```

Never obtain a green result by:

- hiding failures
- weakening security
- changing tests only to pass
- bypassing CI
- deleting evidence

Final states:

```text
PASS
PARTIAL_SUCCESS
FAIL
BLOCKED
```

---

# 24. ENG-10 — RELEASE Execution

Release flow:

```text
Release candidate
        ↓
Exact commit/tag
        ↓
Fresh worktree/environment
        ↓
Build
        ↓
Full regression
        ↓
Security
        ↓
NFR/performance as required
        ↓
Packaging
        ↓
SBOM/provenance as required
        ↓
Deployment validation
        ↓
Upgrade/rollback validation
        ↓
Release gates
        ↓
Release evidence
        ↓
Approved release
```

Release must validate the actual artifact intended for distribution, not merely source tests.

---

# 25. REL-0 — Packaging / Licensing / Entitlement / Deployment

This phase consumes the commercial/deployment architecture defined by API-4.

Product Forge must be capable of producing deployment-specific outputs for:

```text
Community
Enterprise
SaaS
On-prem
OEM / White-label
```

The product build pipeline must distinguish:

```text
source
build
artifact
package
license
entitlement
configuration
deployment target
runtime policy
```

The engineering factory should generate or validate:

- package metadata
- version
- build provenance
- dependencies
- SBOM
- license metadata
- entitlement requirements
- deployment manifest
- upgrade path
- rollback path
- installation validation
- runtime configuration

Commercial/licensing decisions remain human-governed.

---

# 26. Full E2E Product Forge Lifecycle

Once all required phases are implemented, the complete operating lifecycle is:

```text
ENGINEERING TASK / WORK
        ↓
PRODUCT PLAN / ARCHITECTURE CONTEXT (when applicable)
        ↓
ARCHITECTURE
        ↓
EPICS
        ↓
FEATURES
        ↓
TASK DECOMPOSITION
        ↓
DEPENDENCY GRAPH
        ↓
SCHEDULER
        ↓
WORKER ASSIGNMENT
        ↓
ISOLATED WORKTREE
        ↓
FEATURE BRANCH
        ↓
IMPLEMENTATION
        ↓
UNIT/API/CONTRACT TESTS
        ↓
COMMIT
        ↓
PUSH
        ↓
PR
        ↓
CI
        ↓
FEATURE_PR
        ↓
REVIEW / GATES
        ↓
MERGE
        ↓
INTEGRATION
        ↓
DOGFOOD
        ↓
RELEASE
        ↓
PACKAGE
        ↓
ENTITLEMENT
        ↓
DEPLOY
        ↓
POST-DEPLOY VALIDATION
        ↓
EVIDENCE / TELEMETRY
        ↓
LEARNING / BACKLOG
```

---

# 27. Evidence Chain

Every engineering action must be traceable.

Canonical relationship:

```text
Requirement
   ↓
Product Plan
   ↓
Epic
   ↓
Feature
   ↓
Task
   ↓
Worker
   ↓
Worktree
   ↓
Branch
   ↓
Commit
   ↓
PR
   ↓
CI Run
   ↓
Validation Run
   ↓
Evidence
   ↓
Gate
   ↓
Merge
   ↓
Release
   ↓
Deployment
```

Minimum correlation fields should include where applicable:

```text
tenant_id
project_id
run_id
stage_id
task_id
worker_id
worktree_id
branch
commit_sha
pr_number
ci_run_id
validation_id
artifact_id
evidence_id
issue_id
rcca_id
backlog_id
```

The existing Product Forge principle remains:

```text
run_id · stage · agent · attempt_id · content_hash
```

for immutable run-bound provenance where applicable.

---

# 28. Source-of-Truth Boundaries

| Domain | System of record |
|---|---|
| Source / branches / commits / PR / CI | GitHub/Git |
| Product Forge task/work item | Backlog |
| Durable issue identity | Issue Tracker |
| Root cause / corrective action | RCCA |
| Validation execution evidence | Validation Run / Evidence |
| Product Forge runtime state | Canonical PF runtime stores |
| Artifacts | Artifact Store |
| Agent execution ledger | Agent Ledger |
| Run lifecycle events | Events |
| API contract | Canonical OpenAPI |
| Commercial entitlement | Entitlement/Licensing system |
| Worker execution | Worker adapter + PF Worker contract |
| UI state | UI projection, never canonical |

Never create a competing source of truth.

---

# 29. User vs Product Forge vs OpenCode

## 29.1 User does

Human decisions:

- provide product intent
- resolve genuine ambiguity
- approve major architecture choices
- approve irreversible migrations
- decide commercial/licensing policy
- approve security-policy changes
- approve destructive operations
- approve exceptions where governance requires it
- provide credentials/secrets through approved mechanisms
- review business/product decisions

The user should not have to manually orchestrate every worker.

---

## 29.2 Product Forge does

Product Forge autonomously:

- normalize external requirements where applicable
- create plans
- maintain requirements
- create backlog
- decompose tasks
- calculate dependencies
- schedule workers
- allocate worktrees
- create branches
- dispatch workers
- track execution
- collect evidence
- trigger tests
- trigger validation
- orchestrate GitHub
- manage PR lifecycle
- apply gates
- create defect/RCCA/backlog handoffs
- perform safe bounded repair where policy permits
- run integration
- run dogfood
- run release validation
- produce packages
- enforce entitlements
- produce audit/evidence
- request human decisions only when necessary

---

## 29.3 OpenCode does

When selected as a worker, or when used as the engineering session through which a user starts/resumes engineering work:

```text
Receive engineering instruction
        ↓
Resolve/create task through PF Task/Work API
        ↓
Receive task contract / run context
        ↓
Inspect repository
        ↓
Read relevant PF rules/contracts
        ↓
Implement
        ↓
Test
        ↓
Commit
        ↓
Report normalized result
```

If an engineering instruction refers to an existing task, OpenCode resolves that task; if no task exists, it requests task creation through the canonical Task/Work API. It must not create a second task/backlog system.

The same rule applies to any future coding-agent or terminal adapter.

OpenCode TUI may also provide:

```text
/pf
/pf feature
/pf integration
/pf dogfood
/pf release
/pf evidence
```

But those commands must invoke Product Forge contracts.

---

# 30. OpenCode TUI Architecture

Target:

```text
OpenCode TUI
      |
      v
PF API / PF Event API
      |
      v
PF Application Services
      |
      +--> Scheduler
      +--> Worker Runtime
      +--> Validation
      +--> GitHub
      +--> Evidence
```

Do not make:

```text
OpenCode TUI
    ↓
direct PF store manipulation
```

The `.opencode` directory is an adapter/client integration surface.

Its files must never become validation truth.

---

# 31. MCP Architecture

MCP integrations:

```text
Claude / Gemini / Other MCP Client
            ↓
        PF MCP Adapter
            ↓
        PF REST/API
            ↓
    PF Application Service
            ↓
      Canonical PF Store
```

Never:

```text
MCP
 ↓
direct store mutation
```

---

# 32. Future Dashboard Architecture

Later:

```text
Future Dashboard
      |
      +--> REST APIs
      +--> SSE/WebSocket
      +--> AG-UI
      |
      v
Product Forge
```

Dashboard capabilities may include:

- projects
- requirements
- plans
- task board
- worker status
- pipeline status
- validation status
- evidence
- GitHub PR state
- defects
- releases
- deployments
- licensing
- usage
- tenant administration

But the Dashboard is only a client.

No backend redesign should be required to add it.

---

# 33. Automation and Event Flow

Long-running operations must not depend on polling only.

Example:

```text
Task assigned
   ↓ event
Worker started
   ↓ event
Implementation progress
   ↓ event
Tests started
   ↓ event
Commit created
   ↓ event
PR created
   ↓ event
CI started
   ↓ event
Validation started
   ↓ event
Validation completed
   ↓ event
Gate evaluated
   ↓ event
Merge completed
```

Clients consume events through:

```text
SSE
WebSocket
AG-UI
future event infrastructure
```

Events are projections/history mechanisms, not replacement for canonical state.

---

# 34. Repair / RCCA / Revalidation Loop

When a failure occurs:

```text
Failure
  ↓
Preserve original evidence
  ↓
Classify
  ↓
Issue Tracker
  ↓
RCCA
  ↓
Backlog
  ↓
Repair decision
  ↓
Repair branch/worktree
  ↓
Implement
  ↓
Test
  ↓
Commit
  ↓
PR
  ↓
Validation
  ↓
Regression
  ↓
Close/continue issue
```

Default feature validation:

```text
auto_repair = false
```

Controlled autonomous repair may be enabled for Dogfood only under explicit policy and bounded safety rules.

No false-green behavior.

---

# 35. Concurrency and Failure Rules

The system must handle:

- worker crash
- worker timeout
- provider outage
- model failure
- Git conflict
- PR conflict
- CI failure
- validation failure
- task reassignment
- duplicate execution
- stale worker
- orphaned worktree
- partial pipeline completion
- event delivery failure
- network failure
- quota exhaustion

Required properties:

```text
idempotency
fencing
atomicity
lease/ownership
retry policy
bounded retries
resume/reconciliation
single-writer state
immutable evidence
failure classification
safe cleanup
```

A failed worker must not lose:

- branch
- commit
- artifacts
- evidence
- run state

---

# 36. Phase-Gate Model

Every phase follows:

```text
DISCOVER
   ↓
PLAN
   ↓
IMPLEMENT
   ↓
TEST
   ↓
AUDIT
   ↓
SELF-REVIEW
   ↓
GATE
   ↓
NEXT PHASE
```

A phase cannot pass with unresolved:

- architecture contradiction
- broken state integrity
- mandatory test failure
- duplicate engine/store
- security violation
- incompatible public API
- missing required evidence
- unexplained unknown affecting correctness

---

# 37. Human Escalation

Do not stop for routine findings.

Escalate only when genuinely necessary:

```text
breaking public API decision
irreversible data migration
security policy decision
authentication/authorization policy
licensing/commercial decision
major architecture contradiction
destructive operation
conflicting authoritative requirements
```

Escalation must contain:

```text
Finding
Evidence
Why repository rules cannot resolve it
Options
Impact
Exact decision required
```

---

# 38. CI / GitHub Enforcement

CI should progressively enforce:

## API changes

```text
compile
static checks
wired_audit
workflow_matrix_check
unit
API
contract
integration
security
OpenAPI
breaking-change detection
```

## Feature PR

```text
FEATURE_PR
required checks
review
security
contract
impact-based regression
```

## Integration

```text
INTEGRATION
cross-workstream checks
regression
security
build/package
```

## Dogfood

```text
DOGFOOD
full PF E2E
generated product validation
evidence
repair/retest policy
```

## Release

```text
RELEASE
full regression
security
NFR
package
deployment
rollback/upgrade
release gate
```

---

# 39. Final Master Execution Order

This is the order a fresh Product Forge engineering session should execute.

```text
PHASE 0
CURRENT-STATE TRUTH
        |
        v
PHASE 1
API-0 DISCOVERY
        |
        v
PHASE 2
API-0.1 CONTRACT RECONCILIATION
        |
        v
PHASE 3
API-1 FOUNDATION
        |
        v
PHASE 4
API-2 CORE PF APIs
        |
        v
PHASE 5
API-3 ENGINEERING + VALIDATION APIs
        |
        +--------------------+
        |                    |
        v                    v
PHASE 6                API-4 ENTERPRISE
ENG-0 ENGINEERING      /SAAS/OEM
ARCHITECTURE
        |
        v
PHASE 7
ENG-1 TASK CONTRACT
        |
        v
PHASE 8
ENG-2 SCHEDULER
        |
        v
PHASE 9
ENG-3 GIT/WORKTREE
        |
        v
PHASE 10
ENG-4 WORKERS / OPENCODE ADAPTER
        |
        v
PHASE 11
ENG-5 GITHUB / PR / CI
        |
        +--------------------+
        |                    |
        v                    v
PHASE 12
API-5 HARDENING
        |
        v
PHASE 13
ENG-6 VALIDATION FACTORY
        |
        v
PHASE 14
ENG-7 FEATURE_PR
        |
        v
PHASE 15
ENG-8 INTEGRATION
        |
        v
PHASE 16
ENG-9 DOGFOOD
        |
        v
PHASE 17
ENG-10 RELEASE
        |
        v
PHASE 18
PACKAGE / ENTITLEMENT / DEPLOY
        |
        v
PHASE 19
FULL PRODUCT FORGE DOGFOOD
        |
        v
PHASE 20
FINAL AUDIT / PRODUCTION READINESS
```

---

# 40. End-to-End Runtime Flow After Implementation

Once the platform is complete, Product Forge has **two normal entry flows**.

### 40.1 External idea / requirement flow

```text
EXTERNAL USER / CLIENT
 |
 | product idea / requirement / change request
 v
INTAKE API
 |
 v
REQUIREMENT
 |
 v
PRODUCT PLAN
 |
 v
ARCHITECTURE
 |
 v
EPIC
 |
 v
FEATURE
 |
 v
TASKS
 |
 v
DEPENDENCY GRAPH
 |
 v
SCHEDULER
 |
 +-------------------------------+
 |               |               |
 v               v               v
Worker A       Worker B        Worker C
 |               |               |
WT-A            WT-B            WT-C
 |               |               |
Branch A        Branch B        Branch C
 |               |               |
Commit A        Commit B        Commit C
 |               |               |
PR A            PR B            PR C
 |               |               |
CI              CI              CI
 |               |               |
FEATURE_PR      FEATURE_PR      FEATURE_PR
 +---------------+---------------+
                 |
                 v
          INTEGRATION
                 |
                 v
             DOGFOOD
                 |
                 v
              RELEASE
                 |
                 v
             PACKAGE
                 |
                 v
             ENTITLE
                 |
                 v
             DEPLOY
                 |
                 v
          POST-DEPLOY TEST
                 |
                 v
        EVIDENCE / TELEMETRY
                 |
                 v
        LEARNING / BACKLOG
```

---

### 40.2 Direct engineering-session flow

```text
USER
 |
 | "Implement Feature X" / "Fix Bug Y" / "Continue Task Z"
 v
OpenCode / CLI / Coding Agent
 |
 | Task / Work API
 v
Resolve or create Engineering Task
 |
 v
Run / Scheduler / Worker Assignment
 |
 v
Isolated Worktree + Feature Branch
 |
 v
Implementation
 |
 v
Tests
 |
 v
Commit
 |
 v
PR / CI
 |
 v
FEATURE_PR
 |
 v
INTEGRATION → DOGFOOD → RELEASE as applicable
```

This direct engineering path is the normal path for the current **single OpenCode session** use case. It must remain valid when the worker count later increases from one to many.


---

# 41. What Must Not Be Built

Do not create:

```text
second pipeline executor
second validation engine
second backlog
second defect database
second artifact store
second event source of truth
third Git manager
OpenCode-dependent architecture
Dashboard-dependent architecture
archive-dependent architecture
direct MCP-to-store mutation
direct Dashboard-to-store mutation
worker-specific state as canonical PF state
validation-specific shadow Git state
```

---

# 42. Acceptance Criteria for the Entire Program

The master program is complete only when:

## API

- [ ] Canonical API server verified
- [ ] `/api/v1` operational
- [ ] canonical OpenAPI exists
- [ ] auth/authz implemented
- [ ] request/correlation IDs work
- [ ] idempotency works
- [ ] API contract tests pass
- [ ] event API works
- [ ] API compatibility policy enforced

## Runtime

- [ ] canonical run entry works
- [ ] canonical pipeline executor works
- [ ] task lifecycle works
- [ ] artifact/evidence lifecycle works
- [ ] state ownership is unambiguous

## Engineering factory

- [ ] task contract exists
- [ ] scheduler works
- [ ] dependency graph works
- [ ] elastic worker model works
- [ ] worktree isolation works
- [ ] branch orchestration works
- [ ] worker result normalized
- [ ] worker failure/recovery works

## GitHub

- [ ] PR creation works
- [ ] exact commit validation works
- [ ] CI integration works
- [ ] PR evidence is linked
- [ ] merge gates work
- [ ] integration queue works

## Validation

- [ ] one common Validation Engine exists
- [ ] FEATURE_PR works
- [ ] INTEGRATION works
- [ ] DOGFOOD works
- [ ] RELEASE works
- [ ] no-false-green policy works
- [ ] evidence is immutable/run-bound
- [ ] RCCA/Backlog integration works

## Release

- [ ] package generation works
- [ ] provenance/evidence works
- [ ] licensing/entitlement path works where applicable
- [ ] deployment validation works
- [ ] rollback/upgrade path is tested where applicable

## Clients

- [ ] OpenCode is an adapter/client
- [ ] MCP is an adapter/client
- [ ] CLI is an adapter/client
- [ ] future Dashboard can consume the same API/event contracts
- [ ] no client owns canonical state

---

# 43. Fresh OpenCode Master Instruction

Use this as the execution instruction for a fresh engineering session:

```text
You are the Product Forge Engineering Orchestrator.

Execute the Product Forge Master API-First → Engineering Factory → E2E Execution Plan sequentially.

Start with current-state truth and API-0 discovery.

Do not immediately start coding.

Follow every phase gate.

Do not inspect or reuse product-forge/archive.

Do not use the legacy Dashboard as architecture authority.

Do not make OpenCode a Product Forge dependency.

Reuse existing canonical Product Forge engines, stores, APIs, evidence, backlog, defect, Git and runtime components.

Do not create duplicate engines, stores, APIs or validation systems.

API-0 through API-3 establish the control and execution contracts required by the engineering factory.

Then implement the engineering factory:
task contract,
scheduler,
worker abstraction,
worktree/branch orchestration,
OpenCode adapter,
GitHub/PR/CI orchestration,
and common Validation Engine integration.

Use one Validation Engine with:
FEATURE_PR,
INTEGRATION,
DOGFOOD,
RELEASE.

Use exact commit SHAs for validation.

Use isolated worktrees.

Never modify develop/main directly.

Default FEATURE_PR auto-repair is false.

Preserve original failure evidence.

Use existing Issue Tracker, RCCA and Backlog systems.

Do not create a competing issue or defect system.

Use Product Forge APIs and events as the interface for OpenCode, MCP, CLI and future Dashboard clients.

Continue autonomously through the phases when gates pass.

Escalate only for:
breaking public API decisions,
irreversible migrations,
security policy decisions,
authentication/authorization policy,
licensing/commercial decisions,
major architecture contradictions,
destructive operations,
or conflicting authoritative requirements.

When escalating, provide evidence, impact, options and the exact decision required.

At every phase:
discover,
plan,
implement,
test,
audit,
self-review,
gate,
then continue.

The final objective is a working Product Forge engineering factory with the two entry paths shown in the architecture and runtime diagrams. Both paths converge at the canonical engineering lifecycle only after an engineering task/work item exists:

ENGINEERING TASK / WORK
→ DEPENDENCIES
→ SCHEDULER
→ WORKER
→ WORKTREE
→ IMPLEMENT
→ TEST
→ COMMIT
→ PR
→ CI
→ FEATURE_PR
→ REVIEW / GATES
→ MERGE
→ INTEGRATION
→ DOGFOOD
→ RELEASE
→ PACKAGE
→ ENTITLE
→ DEPLOY
→ POST-DEPLOY VALIDATION
→ EVIDENCE
→ LEARNING / BACKLOG.

```

---

# 44. Final Architecture Statement

The final Product Forge architecture is therefore:

```text
                         USER / CLIENTS
                              |
        +---------------------+----------------------+
        |                     |                      |
      CLI                  OpenCode                 MCP
        |                   TUI                     clients
        |                     |                      |
        +---------------------+----------------------+
                              |
                       PRODUCT FORGE API
                              |
                +-------------+-------------+
                |                           |
        Application Services          Event API
                |                           |
                +-------------+-------------+
                              |
                    PRODUCT FORGE CORE
                              |
       +----------+-----------+-----------+-----------+
       |          |                       |           |
    Intake     Runtime              Engineering   Validation
       |          |                   Factory       Factory
       |          |                       |           |
       |       Pipeline              Scheduler      Profiles
       |       Runs                  Workers        |
       |       Stages                Worktrees      +-- FEATURE_PR
       |       Artifacts             Branches       +-- INTEGRATION
       |       Evidence              GitHub         +-- DOGFOOD
       |                             PR/CI           +-- RELEASE
       +----------+--------------------+-------------+
                  |
            Canonical Stores
                  |
       +----------+----------+----------+
       |          |          |          |
    Backlog    Artifacts   Ledger     Events
       |          |          |          |
    Issues/RCCA  Evidence  Run State  Audit
                  |
                  v
             PACKAGE/RELEASE
                  |
                  v
              DEPLOYMENT
                  |
                  v
          FUTURE DASHBOARD
          / AG-UI CLIENT
```

**This is the governing execution order:** API contracts first; engineering orchestration second; validation is a shared factory rather than separate implementations; GitHub is the source-control/PR/CI system of record; OpenCode is replaceable; and the future Dashboard is simply another client of the same stable Product Forge contracts.
