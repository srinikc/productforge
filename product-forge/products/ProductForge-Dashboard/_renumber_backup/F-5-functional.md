## F-5: Multi-Project Runs
**Feature ID:** F-5  
**Summary:** F-5 covers coordinated execution of the same or compatible pipeline across many projects at once. It introduces a parent “multi-project run group” that resolves a project scope, materializes child pipeline runs per project using the run initiation and pre-flight rules of F-3, applies shared and overridden parameters, enforces execution policy, aggregates monitoring and human-in-the-loop gates, and retains a complete parent-child audit trail. Projects come from the registry and portfolio surfaces of F-1 and F-4; project creation and model-tier rules from F-2 are respected but not redefined here.  
**Boundary note:** F-5 does not own project records (F-1), individual run/stage execution (F-3), portfolio membership rules (F-4), or model-tier definitions (F-2). F-5 reads those authoritative resources, issues scoped child-run commands, and aggregates their outcomes.

### Requirements

#### Functional Requirements

| ID | Requirement | Description | Priority |
|---|---|---|---|
| FR-101 | Multi-project run group creation | Create a durable parent run group that targets multiple projects. The group has a name, owner, optional portfolio context, scope definition, execution mode, failure policy, shared parameters, concurrency limits, and state. | Must-have |
| FR-102 | Scope source selection | Allow a group’s project scope to be defined by explicit project IDs, one portfolio, a saved project filter, one or more tags, or a saved query. Multiple scope sources may be combined with include/exclude rules. | Must-have |
| FR-103 | Scope resolution and preview | Resolve the scope into a concrete, deterministic list of projects before launch. Return counts and a preview of included, excluded, duplicate, inaccessible, archived, and ineligible projects with reasons. | Must-have |
| FR-104 | Multi-project run plan materialization | Expand the resolved scope into a parent plan containing one child run specification per eligible project. Each child specification references the project, pinned pipeline definition/version, model tier, parameters, overrides, and readiness prerequisites. | Must-have |
| FR-105 | Child run creation and linkage | For each eligible project, initiate a child run using F-3 run initiation. Every child run stores a durable parent group reference. A child run may not be detached from its parent except by an audited administrative action. | Must-have |
| FR-106 | Shared parameters and inheritance | Support group-level parameters that are inherited by every child run, including pipeline inputs, model tier defaults, gate policy overrides, labels, and notification settings. Inherited values are resolved before child launch. | Must-have |
| FR-107 | Per-project and per-stage overrides | Allow overrides at project, child-run, and stage level. Overrides take precedence over group defaults in a documented order: stage > project > child-run > group > platform default. Every override is recorded with actor and reason. | Must-have |
| FR-108 | Execution modes and ordering | Support parallel, sequential, wave-based, and dependency-ordered execution modes. The mode determines whether child runs start independently, in fixed order, in user-defined waves, or according to declared dependencies. | Must-have |
| FR-109 | Dependency and wave execution | Allow dependencies between child runs or between waves. A dependent child run does not start until all declared predecessors reach a configured terminal or successful state. Cycle detection is mandatory. | Should-have |
| FR-110 | Concurrency, throttling, and queueing | Enforce global, per-portfolio, per-owner, per-model-tier, and per-group concurrency limits. Excess child runs are queued with a visible queue reason and position. Limits are configurable and may be tightened at launch but not silently loosened. | Must-have |
| FR-111 | Group lifecycle control | Support start, pause, resume, cancel, and archive for the whole group, a selected wave, a selected project set, or a single child run. Commands are recorded as auditable group commands and propagate according to the group policy. | Must-have |
| FR-112 | Failure policy and isolation | Support fail-fast, continue-on-error, retry-failed-only, and quarantine modes. A failing child must not corrupt sibling children by default; sibling execution continues unless the policy explicitly stops the group. | Must-have |
| FR-113 | Retry, skip, and resume semantics | Allow retrying failed children, skipping selected children, and resuming a paused or partially failed group. Retry reuses the same child run unless the operator explicitly requests a fresh child run. Skipped children are marked terminal and excluded from success calculations. | Must-have |
| FR-114 | HIL gate aggregation | Aggregate human-in-the-loop gates across all child runs into one group gate queue. Show which project, stage, child run, and gate produced each pending decision. | Must-have |
| FR-115 | Bulk gate decisions | Allow approve, reject, request changes, and delegate decisions across selected pending gates. Bulk decisions apply only to gates the actor is authorized to decide and are recorded per child run, not only at group level. | Must-have |
| FR-116 | Live monitoring and aggregation | Provide an always-current aggregate view of group state: child counts by status, completed/failed/running/queued counts, gate backlog, failure reasons, progress percentage, ETA where computable, and last activity timestamp. | Must-have |
| FR-117 | Drill-down and filtering | From the aggregate view, allow drill-down to wave, project, child run, stage, and gate. Filter by status, portfolio, tag, model tier, failure class, and time window. | Must-have |
| FR-118 | Notifications and webhooks | Emit group-level events for created, started, paused, resumed, child failed, gate pending, completed, cancelled, and budget threshold reached. Support in-app, email digest, and webhook delivery. | Should-have |
| FR-119 | Scheduling and delayed start | Allow a group to be scheduled for a future start time, optionally recurring by a defined calendar rule. Scheduled groups remain editable until launch and are validated again at launch time. | Should-have |
| FR-120 | Reusable run templates | Allow saving a group configuration as a reusable template containing scope rules, execution mode, failure policy, parameters, concurrency limits, and notification settings. Templates may be applied to new groups without copying child-run history. | Should-have |
| FR-121 | Bulk operations on members | Support bulk pause, resume, cancel, retry, skip, approve gate, reject gate, and re-evaluate readiness across selected child runs. Bulk operations return per-child success or failure. | Must-have |
| FR-122 | Reporting and export | Produce a group run report containing parent metadata, scope snapshot, child-run outcomes, gate decisions, failures, overrides, timings, and final aggregate state. Export as CSV and JSON. | Should-have |
| FR-123 | Authorization and scope enforcement | Enforce permissions for creating, viewing, modifying, launching, cancelling, and approving gates for a group. A user may not include projects, runs, or gates outside their authorized portfolio, owner, or role scope. | Must-have |
| FR-124 | Quotas, cost, and budget guardrails | Allow optional token, cost, duration, and child-count caps at group level. When a threshold is reached, the group warns, pauses, or cancels according to policy. No child run may exceed a hard group cap without an explicit override. | Should-have |
| FR-125 | Idempotency, deduplication, and audit linkage | Accept an idempotency key for group creation and launch. Duplicate requests with the same key return the existing group. Every group command, child launch, override, gate decision, and state transition is written to an immutable audit log linked to parent and child identifiers. | Must-have |

#### Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-61 | Performance | Creating a group with 1,000 in-scope projects and resolving its scope must complete within 5 seconds under normal load, excluding child-run execution time. |
| NFR-62 | Scalability | A single group must support at least 10,000 child run specifications. The platform must support at least 100 concurrently active multi-project groups without cross-group starvation. |
| NFR-63 | Throughput | The control plane must sustain at least 500 child run start operations per minute across all active groups under normal load. |
| NFR-64 | Availability | The multi-project run control surface must target 99.9% monthly availability, excluding scheduled maintenance. |
| NFR-65 | Reliability | No accepted child run may be silently lost. If a child launch fails after acceptance, the group must record a retryable failure state. |
| NFR-66 | Consistency | Aggregate group state must be eventually consistent within 2 seconds of any child state transition under normal load. |
| NFR-67 | Security | All group, child run, override, and gate data must be protected by authenticated access, role-based authorization, encryption in transit, and encryption at rest. |
| NFR-68 | Data residency | Multi-project run metadata and audit records must be stored in the region configured for the owning portfolio or tenant, where regional deployment is available. |
| NFR-69 | Deployment and environment | The feature must be deployable in development, staging, and production environments with environment-specific limits, quotas, and notification endpoints. |
| NFR-70 | Observability | The feature must emit metrics, structured logs, and traces for group creation, scope resolution, child launch, queue wait, gate aggregation, failure, retry, and completion. |
| NFR-71 | Retention | Audit records for group commands and gate decisions must be retained for at least 1 year by default, configurable by tenant policy. |
| NFR-72 | API compatibility | Public API contracts for multi-project runs must be versioned. Breaking changes require a new major version and a documented migration path. |
| NFR-73 | Accessibility | Any operator-facing UI for multi-project runs must meet WCAG 2.1 AA for keyboard navigation, contrast, focus visibility, and screen-reader labels. |
| NFR-74 | Internationalization | User-facing timestamps must display in the user’s locale; stored timestamps must be UTC. Numbers and durations must use locale-aware formatting. |
| NFR-75 | Cost efficiency | The system must avoid duplicate child runs for the same project, pipeline version, and idempotency key, and must expose queued child counts so operators can avoid over-launching. |

#### User Stories

| ID | Story |
|---|---|
| US-61 | As a portfolio manager, I want to run one pipeline across every eligible project in a portfolio, so that I can standardize delivery without opening each project. |
| US-62 | As a pipeline operator, I want to run a pipeline across an explicit list of projects, so that I can coordinate a targeted release or migration. |
| US-63 | As a pipeline operator, I want to preview which projects will be included before launch, so that I can avoid running work against the wrong scope. |
| US-64 | As a pipeline operator, I want to set concurrency limits for a multi-project run, so that I do not overwhelm model capacity or downstream systems. |
| US-65 | As a pipeline operator, I want to pause, resume, or cancel an entire multi-project run, so that I can react to incidents or changing priorities. |
| US-66 | As a pipeline operator, I want to retry only failed child runs, so that I can recover from partial failures without rerunning successful projects. |
| US-67 | As a reviewer, I want to see all pending human-in-the-loop gates across a multi-project run in one queue, so that I can decide them efficiently. |
| US-68 | As a portfolio manager, I want an aggregate view of run status across all child projects, so that I can report progress without checking each project. |
| US-69 | As a pipeline operator, I want to drill into a specific child run from the aggregate view, so that I can diagnose a failure in context. |
| US-70 | As a pipeline operator, I want notifications when a multi-project run completes or fails, so that I do not need to poll the dashboard. |
| US-71 | As a pipeline operator, I want to schedule a multi-project run for later, so that it starts during an approved maintenance window. |
| US-72 | As a pipeline operator, I want to save a multi-project run configuration as a template, so that recurring releases are repeatable. |
| US-73 | As a portfolio manager, I want to export a multi-project run report, so that I can share outcomes with stakeholders. |
| US-74 | As a security administrator, I want multi-project run permissions scoped by portfolio and role, so that users cannot act outside their authority. |
| US-75 | As a FinOps owner, I want to set cost and token caps on a multi-project run, so that a broad launch cannot exceed budget. |

### Behaviour

1. An operator creates a multi-project run group by selecting a scope source, execution policy, and shared configuration.
2. The system resolves the scope into a concrete project list and returns a preview before launch.
3. On launch, the system validates the group, then materializes one child run specification per eligible project.
4. Child runs are initiated according to execution mode, dependency rules, and concurrency limits.
5. Each child run follows the F-3 run initiation, pre-flight, stage execution, and gate behavior; F-5 does not redefine those rules.
6. The parent group continuously aggregates child states into a single group state.
7. Human-in-the-loop gates from all children appear in the group gate queue and may be decided individually or in bulk.
8. Group-level pause, resume, cancel, retry, and skip commands propagate according to policy and are audited.
9. Failures are isolated or propagated according to the group failure policy.
10. The group reaches a terminal state when all children are terminal, or earlier if the policy stops the group.
11. All events, overrides, decisions, and child linkages are retained for audit and reporting.

### Business Rules

| ID | Rule |
|---|---|
| BR-1 | A multi-project run group must always have exactly one owner and one scope definition. |
| BR-2 | A project may appear at most once in a single group unless explicit duplicate-inclusion override is recorded with a reason. |
| BR-3 | Archived projects are excluded from scope by default. Including an archived project requires an explicit override and must be audited. |
| BR-4 | A child run inherits the parent group’s pinned pipeline version unless a per-project override explicitly changes it before launch. |
| BR-5 | A child run may not start unless it passes the same pre-flight readiness rules that apply to a single-project run. |
| BR-6 | Group concurrency limits are upper bounds. The system may run fewer children than the limit if capacity or dependencies require it. |
| BR-7 | Bulk gate decisions apply only to gates the actor is authorized to decide. Unauthorized gates remain pending and are reported as skipped. |
| BR-8 | Fail-fast stops new child launches after the first configured failure, but does not cancel already-running children unless cancellation is explicitly requested. |
| BR-9 | Continue-on-error allows all eligible children to launch even if some fail. |
| BR-10 | Retry-failed-only creates new execution attempts only for children in a failed or retryable state; successful and skipped children are not rerun. |
| BR-11 | A group cannot be marked complete while any child is non-terminal, unless the group was cancelled and the policy allows partial completion. |
| BR-12 | Cost and token caps are enforced against the sum of all child usage, not per child, unless the operator configures both group and child caps. |
| BR-13 | An idempotency key is scoped to a tenant and operation. Reusing the same key with a different payload is rejected as a conflict. |
| BR-14 | Audit entries for group commands, overrides, and gate decisions are immutable and may not be edited or deleted by normal users. |
| BR-15 | Deleting or archiving a parent group does not delete child run history; child history remains governed by the retention policy of F-3 and the tenant. |

### Validation

| ID | Validation |
|---|---|
| V-1 | Group name is required, trimmed, and between 1 and 200 characters. |
| V-2 | Scope source must be one of: explicit projects, portfolio, saved filter, tags, saved query. |
| V-3 | Explicit project IDs must reference existing, non-deleted projects unless an archived-inclusion override is supplied. |
| V-4 | Portfolio scope must reference an existing portfolio the actor can read. |
| V-5 | Tag scope must contain at least one non-empty tag. |
| V-6 | Execution mode must be parallel, sequential, wave-based, or dependency-ordered. |
| V-7 | Wave definitions must not contain empty waves and must not assign the same project to multiple waves unless explicitly allowed. |
| V-8 | Dependency graph must be acyclic. Any cycle fails validation before launch. |
| V-9 | Concurrency limits must be positive integers and must not exceed platform maximums. |
| V-10 | Failure policy must be fail-fast, continue-on-error, retry-failed-only, or quarantine. |
| V-11 | Parameter overrides must match the schema of the target pipeline stage or child run parameter. |
| V-12 | Cost, token, duration, and child-count caps must be non-negative numbers or null. |
| V-13 | Idempotency key, when supplied, must be between 1 and 255 characters and URL-safe. |
| V-14 | Scheduled start time must be in the future at creation time, or the request is rejected unless immediate launch is explicitly requested. |
| V-15 | Gate decisions must include a decision value, actor, timestamp, and reason for reject or request-changes decisions. |

### Edge Cases

| ID | Edge Case | Expected Behaviour |
|---|---|---|
| EC-1 | Scope resolves to zero projects. | Launch is blocked with an actionable empty-scope report. |
| EC-2 | Scope resolves to projects the actor cannot access. | Inaccessible projects are excluded and listed in the preview; launch may proceed only with remaining eligible projects if policy allows. |
| EC-3 | Same project appears through both explicit ID and portfolio. | Project is deduplicated by default and reported once. |
| EC-4 | Child run launch succeeds but parent linkage write fails. | Child is marked orphan-risk, launch is rolled back if possible, or the linkage is repaired and audited. |
| EC-5 | Group is paused while children are mid-stage. | New children do not start; running children continue to the next safe checkpoint unless the pause policy requests immediate stop. |
| EC-6 | Group is cancelled while gates are pending. | Pending gates are cancelled or expired according to policy and recorded as cancelled, not approved. |
| EC-7 | A child fails during retry. | Retry attempt is recorded separately; child remains failed or moves to exhausted-retry state. |
| EC-8 | Bulk gate decision includes a gate already decided by another actor. | Decision is rejected for that gate and reported per child; other eligible gates proceed. |
| EC-9 | Cost cap is reached mid-run. | Group pauses or cancels according to policy; no new child starts; in-flight children complete or stop at a safe boundary. |
| EC-10 | Pipeline version is upgraded in the registry after group launch. | Children continue using the pinned version; the group records that a newer version exists but does not auto-upgrade. |
| EC-11 | Scheduled group’s scope changes before start time. | At launch, scope is re-resolved and the preview diff is recorded; if the scope becomes invalid, launch is blocked or paused for review. |
| EC-12 | User attempts to detach a child run from its parent. | Detach is rejected unless performed by an authorized administrator and recorded as an audited exception. |

### Error Handling

| ID | Error Condition | Handling |
|---|---|---|
| EH-1 | Group creation payload invalid. | Return structured validation errors by field; no group is created. |
| EH-2 | Scope resolution service unavailable. | Retry with backoff; if still unavailable, fail the request with a retryable error. |
| EH-3 | One or more projects fail pre-flight. | Record per-project readiness failure; launch eligible projects according to policy or block whole group if policy requires all-or-nothing. |
| EH-4 | Child run initiation returns a transient error. | Queue for retry up to policy limit; record attempt history. |
| EH-5 | Child run initiation returns a permanent error. | Mark child failed with reason; apply failure policy. |
| EH-6 | Concurrency limit service unavailable. | Do not launch new children; queue them and surface a degraded-controls warning. |
| EH-7 | Gate aggregation service lags. | Show last-known aggregate with a stale indicator; do not silently hide pending gates. |
| EH-8 | Bulk operation partially fails. | Return per-child success/failure list; do not report the whole bulk operation as fully successful. |
| EH-9 | Webhook delivery fails. | Retry with backoff; after final failure, record delivery failure and expose it in the group notification log. |
| EH-10 | Audit write fails for a group command. | Treat the command as failed unless a durable local queue can guarantee eventual audit write; never silently drop audit. |
| EH-11 | Idempotency key conflict with different payload. | Return 409 Conflict and do not create a new group. |
| EH-12 | Budget cap calculation unavailable. | Pause new launches until cost accounting recovers, unless the operator explicitly overrides with audit. |
| EH-13 | Dependency predecessor never reaches required state. | Dependent child remains blocked until timeout; then it fails or is skipped according to group policy. |
| EH-14 | Project deleted after group creation but before child launch. | Child is marked ineligible with reason; group policy decides whether to continue or pause. |
| EH-15 | User loses permission mid-run. | User can no longer view or act on the group; running children continue under system authority unless the group owner is deactivated. |

### Acceptance Criteria

| ID | Criterion |
|---|---|
| AC-1 | An operator can create a multi-project run group from a portfolio and see a preview of all included projects before launch. |
| AC-2 | An operator can create a multi-project run group from an explicit list of project IDs. |
| AC-3 | Invalid or inaccessible projects are excluded and listed with reasons in the preview. |
| AC-4 | Launching a group creates one child run per eligible project, each linked to the parent group. |
| AC-5 | Shared parameters are inherited by all children unless overridden at project or stage level. |
| AC-6 | Overrides are recorded with actor, timestamp, and reason. |
| AC-7 | Concurrency limits are enforced; excess children show a queued state and queue reason. |
| AC-8 | Pausing the group prevents new child launches while respecting the pause policy for running children. |
| AC-9 | Cancelling the group moves all non-terminal children to cancelled or stopping according to policy. |
| AC-10 | Retrying failed children reruns only failed or retryable children. |
| AC-11 | Pending gates from all children appear in one group gate queue. |
| AC-12 | A bulk gate approve succeeds only for gates the actor is authorized to approve and reports per-gate outcomes. |
| AC-13 | Aggregate view shows counts by child status, gate backlog, and last activity within 2 seconds of a state change. |
| AC-14 | Drilling into a child run from the aggregate view opens that child’s run detail in context. |
| AC-15 | Group notifications fire on started, paused, resumed, child-failed, gate-pending, completed, cancelled, and budget-threshold events. |
| AC-16 | A scheduled group re-resolves its scope at launch and records the diff. |
| AC-17 | A saved template can create a new group without copying previous child-run history. |
| AC-18 | Export contains parent metadata, scope snapshot, child outcomes, gate decisions, overrides, failures, and timings. |
| AC-19 | Unauthorized users cannot view or act on groups outside their portfolio or role scope. |
| AC-20 | Reusing an idempotency key with the same payload returns the existing group; reusing it with a different payload returns a conflict. |

### API Behaviour

| ID | API Surface | Behaviour |
|---|---|---|
| API-1 | Create multi-project run group | `POST /multi-project-runs` accepts scope, execution policy, parameters, limits, notifications, and idempotency key. Returns group ID, state, preview summary, and links. |
| API-2 | Preview scope | `POST /multi-project-runs/preview-scope` resolves scope without creating a group. Returns included, excluded, duplicate, inaccessible, and ineligible projects with reasons. |
| API-3 | Get group | `GET /multi-project-runs/{groupId}` returns parent metadata, aggregate state, policy, limits, scope snapshot, and child summary counts. |
| API-4 | List groups | `GET /multi-project-runs` supports filters by status, owner, portfolio, tag, created time, and scheduled time. |
| API-5 | Launch group | `POST /multi-project-runs/{groupId}/launch` validates readiness, materializes children, and starts execution according to policy. Supports idempotency. |
| API-6 | Group lifecycle command | `POST /multi-project-runs/{groupId}/commands` accepts pause, resume, cancel, retry-failed, skip-selected, or archive with target scope. Returns per-target outcomes. |
| API-7 | List child runs | `GET /multi-project-runs/{groupId}/children` returns child runs with project, status, wave, dependency, gate backlog, and failure reason. |
| API-8 | Gate queue | `GET /multi-project-runs/{groupId}/gates` returns pending gates across children with project, stage, child run, gate type, and required role. |
| API-9 | Bulk gate decision | `POST /multi-project-runs/{groupId}/gates/decisions` accepts a list of gate IDs and a decision. Returns per-gate success, skipped, or failure. |
| API-10 | Aggregate metrics | `GET /multi-project-runs/{groupId}/metrics` returns counts by status, progress, gate backlog, failure classes, queue depth, cost usage, and last activity. |
| API-11 | Export report | `GET /multi-project-runs/{groupId}/report` returns CSV or JSON according to `Accept` header. Report generation may be asynchronous for large groups. |
| API-12 | Events and webhooks | Group events are emitted to the notification subsystem and may be subscribed to by webhook. Each event includes group ID, event type, timestamp, actor, and affected child IDs. |

### Priority

| Priority | Items |
|---|---|
| Must-have | FR-101 through FR-106, FR-107, FR-108, FR-110, FR-111, FR-112, FR-113, FR-114, FR-115, FR-116, FR-117, FR-121, FR-123, FR-125 |
| Should-have | FR-109, FR-118, FR-119, FR-120, FR-122, FR-124 |
| Nice-to-have | None in this feature; all listed requirements are required for the multi-project run surface to be safe and operable. |
