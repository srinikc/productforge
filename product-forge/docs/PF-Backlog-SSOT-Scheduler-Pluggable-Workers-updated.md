# PF Backlog SSOT, Work Scheduler & Pluggable Worker Orchestration

> **SUPERSEDED (worker subsystem) — ADR-0002 / WorkerGrid Stage 2b (2026-10-07).**
> The in-PF worker layer this design's §43 "Current PF Code Alignment" describes
> (`core/worker*.py`, `/api/v1/engineering/{workers,work,adapters,dispatch*}`,
> `/pf work` verbs) was removed from Product Forge and rehomed in the external
> **WorkerGrid** component (`workergrid/`). Claim pickup now lives in
> `core/scheduler.py::next_eligible` (staleness refresh + PIDL contract attach);
> external coordination (register/heartbeat/claim/lease) is the WorkerGrid
> coordinator (`workergrid/service.py` + `workergrid/store.py`). See
> `docs/WORKERGRID-DESIGN.md` §12 and backlog epic **BI-PF-0360**.
> The backlog SSOT, grooming, analysis, `job_manager` queueing, PIDL and
> non-worker sections remain authoritative for PF.
> Tracked by: BI-PF-0360 (epic), BI-PF-0409/0410/0411 (WorkerGrid stages).

**Status:** Additive implementation design\
**Purpose:** Make the PF backlog a first-class execution SSOT and allow
PF to schedule work to externally registered execution workers without
redesigning existing PF architecture.\
**Primary use initially:** Accelerate PF's own R&D implementation by
distributing work across multiple OpenCode/other coding sessions.\
**Commercial PF use:** Optional execution infrastructure; PF's core
agent orchestration must not depend on it.

------------------------------------------------------------------------

## 1. Executive Decision

Product Forge should make the **canonical backlog/task model the single
source of truth for executable work**.

The backlog must own:

-   task identity
-   lifecycle/status
-   priority
-   dependencies
-   readiness
-   analysis state
-   architecture-fit findings
-   implementation strategy
-   execution ownership
-   completion state
-   blocking state
-   worker assignment/lease references

The scheduler should consume this canonical backlog and determine:

> **What is the highest-priority executable work that can safely be
> assigned now, considering dependencies, contention, worker capability
> and current execution state?**

The scheduler must not become a second task database, workflow engine,
architecture engine or agent framework.

### Core rule

**Backlog = what work exists.**\
**Analysis = what the work means and how it fits PF.**\
**Scheduler = what can run now.**\
**Worker registry = what execution capacity is available.**\
**Worker adapter = how an external runtime is connected.**\
**Worker/runtime = performs the assigned work.**

------------------------------------------------------------------------

# 2. Important Boundary: Agents vs Workers

PF must not equate an agent with a worker.

A PF agent may have its own:

-   model
-   tools
-   skills
-   context
-   memory
-   system instructions
-   reasoning loop
-   state
-   permissions
-   MCP/connectors
-   runtime

and may execute entirely within its own agent system.

A **worker** is an optional external execution resource/session that PF
can schedule work to.

Examples:

-   OpenCode CLI/TUI session
-   another coding-agent runtime
-   remote agent runtime
-   native execution process
-   future execution system

Therefore:

``` text
PF Agent Orchestration
    !=
Worker Orchestration
```

Worker orchestration exists to solve the specific problem:

> "I have multiple externally running execution sessions/resources and
> want PF to distribute canonical backlog work between them instead of
> manually feeding each session."

Do not add a Worker object as a mandatory wrapper around every PF agent.

------------------------------------------------------------------------

# 3. Reuse-First Rule

The existing PF design explicitly identifies existing canonical
task/state and existing worker orchestration as infrastructure to reuse,
and explicitly says not to rewrite the worker orchestration.

Therefore implementation must follow:

1.  Inspect the existing backlog/task model.
2.  Inspect the existing canonical state model.
3.  Inspect the existing scheduler, if present.
4.  Inspect existing worker orchestration.
5.  Inspect existing queues/events.
6.  Inspect existing API conventions.
7.  Extend those components.
8.  Introduce a new component only when no existing capability can
    safely support the requirement.

Do **not**:

-   create a second backlog
-   create a second task store
-   replace the existing worker orchestration
-   create a parallel workflow engine
-   make OpenCode a PF architectural dependency
-   turn workers into agents
-   rewrite working modules for conceptual cleanliness
-   reopen completed intake/design paths
-   introduce microservices merely because the capability has several
    logical parts

This follows the existing PF reuse-first principle.

------------------------------------------------------------------------

# 4. Target Architecture

``` text
                         PF
                         |
                         v
                Canonical Backlog SSOT
                         |
          +--------------+--------------+
          |                             |
          v                             v
   AI/User Grooming              Work Analysis
          |                             |
          +--------------+--------------+
                         |
                         v
                  READY / BLOCKED
                         |
                         v
                  PF Scheduler
                         |
             +-----------+-----------+
             |                       |
        Manual request           Auto mode
        "give me work"       continuously dispatch
             |                       |
             +-----------+-----------+
                         |
                         v
                Worker Registry
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
      Worker A       Worker B       Worker C
          |              |              |
      Adapter         Adapter        Adapter
          |              |              |
      OpenCode       OpenCode       Other Runtime
          |              |              |
          +--------------+--------------+
                         |
                         v
                    Execution
                         |
                         v
                 Result / Evidence
                         |
                         v
                Canonical Backlog
```

The Worker Registry and Scheduler are **optional/pluggable execution
infrastructure**. PF's core agent orchestration must be able to operate
without them.

------------------------------------------------------------------------

# 5. Backlog Becomes a First-Class Citizen

The canonical backlog must no longer be treated as merely an input list.

It becomes the authoritative work lifecycle.

Every executable item gets a stable ID, for example:

``` text
PF-ENG-0421
```

The same ID must be used across:

-   TUI
-   UI
-   API
-   scheduler
-   worker assignment
-   execution
-   logs
-   evidence
-   validation
-   approvals
-   audit
-   completion

No worker may create an independent copy of the task as its own source
of truth.

------------------------------------------------------------------------

# 6. Required Backlog Fields

Exact names must follow the existing PF schema/conventions where
available. The following is the required logical model.

## 6.1 Identity

``` yaml
id:
title:
description:
type:
parent_id:
epic_id:
source:
created_at:
updated_at:
```

## 6.2 Lifecycle

``` yaml
status:
  NEW
  GROOMING
  ANALYSIS_REQUIRED
  ANALYSIS_IN_PROGRESS
  ANALYSIS_COMPLETE
  READY
  ASSIGNED
  IN_PROGRESS
  BLOCKED
  REVIEW
  VALIDATION
  COMPLETED
  FAILED
  CANCELLED
```

Do not add statuses that duplicate existing PF states. Map these
concepts into the current state machine if one already exists.

## 6.3 Priority

``` yaml
priority:
priority_class:
priority_rank:
```

Priority must support deterministic ordering.

The scheduler must never depend only on creation order or task ID.

## 6.4 Dependencies

``` yaml
dependencies:
  - task_id:
    type:
      BLOCKS
      REQUIRES
      RELATED
    required_state:

blocked_by:
unlocks:
```

A task is executable only when all mandatory dependencies are satisfied.

## 6.5 Analysis

``` yaml
analysis:
  status:
    NOT_ANALYZED
    IN_PROGRESS
    COMPLETE
    STALE

  analyzed_at:
  analyzed_by:

  architecture_fit:
    REUSE
    EXTEND
    MODIFY
    NEW_COMPONENT
    NEW_CAPABILITY
    REFACTOR
    OTHER

  implementation_strategy:

  existing_components:
  existing_apis:
  existing_modules:
  existing_services:

  dependency_findings:
  conflict_findings:
  duplication_findings:

  drift:
    NONE
    LOW
    MEDIUM
    HIGH

  rewrite_required: false

  new_component_required: false

  rationale:
  assumptions:
  risks:
  evidence:
  confidence:
```

The actual values should be adapted to the existing PF vocabulary if
equivalent fields already exist.

------------------------------------------------------------------------

# 7. Architecture Analysis Timing

Architecture analysis should **not happen only when the scheduler picks
a task**.

Use two levels.

## Level 1 --- Backlog analysis

When a task is created or materially changed:

``` text
Backlog item
    |
    v
AI grooming
    |
    v
Architecture analysis
    |
    v
Dependency/conflict analysis
    |
    v
Ready for user grooming
```

This determines whether the proposed work:

-   already exists
-   can extend an existing capability
-   should reuse an API
-   introduces duplication
-   conflicts with another task
-   introduces architectural drift
-   genuinely needs a new component
-   appears to require a rewrite

## Level 2 --- Scheduler pre-flight

Before assignment:

``` text
READY
  |
  v
Current-state revalidation
  |
  +-- dependency still satisfied?
  +-- task still valid?
  +-- architecture analysis stale?
  +-- conflicting task active?
  +-- worker capable?
  +-- workspace available?
  |
  v
CLAIM
```

This is a lightweight revalidation, not a second full architecture
analysis.

### Key rule

**Analysis belongs primarily to backlog grooming; scheduler performs
execution-time validation.**

------------------------------------------------------------------------

# 8. Analysis Must Be Versioned/Stale-Aware

A Boolean `analysed=true` is insufficient.

Use:

``` text
NOT_ANALYZED
IN_PROGRESS
COMPLETE
STALE
```

Analysis becomes stale when relevant information changes, such as:

-   task requirement changes
-   dependency changes
-   architecture decision changes
-   affected component changes
-   another task changes the same component
-   significant implementation state changes

A stale analysis must be revalidated before assignment.

------------------------------------------------------------------------

# 9. AI Grooming + User Grooming

PF should support two passes.

## AI grooming

AI examines:

-   requirement
-   existing backlog
-   current architecture
-   existing implementation
-   dependencies
-   related decisions
-   settled PF rules

and proposes:

``` text
priority
dependencies
architecture fit
implementation strategy
risk
drift
duplication
missing information
acceptance criteria
```

## User grooming

User reviews the AI proposal.

Possible outcomes:

``` text
APPROVE
MODIFY
REJECT
DEFER
```

The user should see a concise decision view, not a large internal
analysis dump.

------------------------------------------------------------------------

# 10. Scheduler Responsibility

The scheduler answers only:

> **Which executable task should be assigned to which available worker
> right now?**

It should consider, in order:

1.  task eligibility
2.  dependency satisfaction
3.  current status
4.  priority
5.  explicit ordering constraints
6.  contention/conflicts
7.  worker capability
8.  worker availability
9.  concurrency limits
10. lease/assignment state

The scheduler must not redesign PF architecture.

------------------------------------------------------------------------

# 11. Priority Selection

When a worker requests work:

``` text
PF> work
```

the scheduler should:

``` text
1. Find READY tasks.
2. Remove blocked tasks.
3. Remove already claimed tasks.
4. Remove tasks incompatible with worker capabilities.
5. Apply dependency constraints.
6. Apply conflict/locking rules.
7. Order by priority.
8. Select the highest eligible task.
9. Atomically claim it.
10. Return assignment.
```

"Next task" therefore means:

> **highest-priority currently executable task for that worker**, not
> simply the next numeric task.

------------------------------------------------------------------------

# 12. No Duplicate Assignment / Contention Control

This is mandatory.

Two workers must not be able to receive the same task.

The claim operation must be atomic:

``` text
find eligible task
      |
verify still available
      |
atomic claim
      |
record worker + lease
      |
return assignment
```

Conceptually:

``` text
READY
  |
  +---- Worker A claims ----> ASSIGNED(A)
  |
  X---- Worker B cannot claim
```

Do not rely on workers voluntarily coordinating.

The scheduler/control-plane state is authoritative.

------------------------------------------------------------------------

# 13. Worker Assignment State

A task assignment should record at minimum:

``` yaml
execution:
  worker_id:
  assignment_id:
  lease_id:
  assigned_at:
  lease_expires_at:
  attempt:
  started_at:
  completed_at:
```

Do not duplicate the full task in the worker registry.

The canonical task remains in the backlog.

------------------------------------------------------------------------

# 14. Lease Model

Assignments should use leases rather than permanent ownership.

``` text
Task
  |
  v
ASSIGNED
  |
  +-- heartbeat continues --> lease renewed
  |
  +-- worker fails ---------> lease expires
                                  |
                                  v
                              recovery
```

When a lease expires, PF must apply a recovery policy:

``` text
RESUME
RETRY
REASSIGN
MARK_FAILED
REQUIRE_REVIEW
```

The policy depends on task/runtime capability.

Do not blindly re-run tasks that may have made non-idempotent changes.

------------------------------------------------------------------------

# 15. Worker Registry

Workers are externally registered execution resources.

A worker registration should be intentionally minimal.

Example:

``` yaml
worker_id:
runtime:
capabilities:
role:
endpoint:
workspace:
status:
```

Avoid requiring a large configuration payload.

The worker can later provide additional capability metadata.

------------------------------------------------------------------------

# 16. Worker Registration Protocol

Registration must be runtime-neutral.

Conceptually:

``` text
REGISTER
   |
   v
PF Worker Registry
   |
   v
worker_id assigned/confirmed
   |
   v
HEARTBEAT
```

The worker should not need to understand PF's internal agent
architecture.

It only needs to understand the worker protocol.

------------------------------------------------------------------------

# 17. Runtime Adapters

OpenCode is one adapter.

Conceptually:

``` text
Worker Protocol
       |
       +-- OpenCode Adapter
       +-- Claude Code Adapter
       +-- Other Runtime Adapter
       +-- Native Runtime Adapter
       +-- Remote Worker Adapter
```

The scheduler talks to the worker abstraction, not directly to OpenCode.

This prevents OpenCode from becoming an architectural dependency.

------------------------------------------------------------------------

# 18. OpenCode Initial Integration

For the current PF R&D environment, a worker may represent:

``` text
OpenCode CLI session
OpenCode TUI session
remote OpenCode session
```

The adapter should provide only the minimum required operations:

``` text
register
heartbeat
get_status
accept_assignment
start/continue
pause
cancel
report_result
disconnect
```

The exact OpenCode integration mechanism must be determined by the
current available OpenCode interface rather than inventing an
integration API.

------------------------------------------------------------------------

# 19. Worker Lifecycle

Minimal lifecycle:

``` text
REGISTERING
    |
    v
ONLINE
    |
    +--> IDLE
    |
    +--> BUSY
    |
    +--> PAUSED
    |
    +--> DRAINING
    |
    +--> OFFLINE
    |
    +--> STALE
```

Scheduler owns lifecycle state from registration, heartbeat and
assignment events.

Workers report facts; the scheduler/control plane determines
authoritative state.

------------------------------------------------------------------------

# 20. Heartbeat

Workers must periodically report liveness.

Heartbeat should be lightweight:

``` text
worker_id
timestamp
status
current_assignment_id
```

Optionally:

``` text
runtime_health
resource_summary
capability_version
```

Do not send large context or logs in heartbeat.

------------------------------------------------------------------------

# 21. Manual and Automatic Modes

The scheduler should support both.

## Manual pull

Worker/user asks:

``` text
PF> work
```

Scheduler finds and assigns the next eligible task.

This is the immediate R&D mode.

## Automatic dispatch

Scheduler watches:

``` text
READY tasks
+
available workers
```

and assigns work automatically.

``` text
Worker becomes IDLE
        |
        v
Scheduler
        |
        v
highest eligible task
        |
        v
assignment
```

Automatic mode must be configurable and disableable.

------------------------------------------------------------------------

# 22. Worker Orchestration Is Optional

This is important for PF architecture.

The worker subsystem should be a **pluggable execution capability**.

``` text
PF Core
  |
  +-- Agent Orchestration
  |
  +-- Canonical Work/Backlog
  |
  +-- Analysis
  |
  +-- Validation
  |
  +-- UI/API
  |
  +-- Optional Worker Orchestration
          |
          +-- OpenCode
          +-- Other runtime
```

PF must remain functional if the worker subsystem is disabled.

------------------------------------------------------------------------

# 23. PF Agents Must Not Be Forced Through Workers

A PF agent can execute within its own agent runtime with:

-   tools
-   modes
-   model
-   context
-   memory
-   skills
-   state
-   permissions
-   execution loop

It does not need to become:

``` text
Agent -> Worker -> OpenCode
```

The worker subsystem is for externally managed execution
sessions/resources.

PF's core agent orchestration remains independent.

------------------------------------------------------------------------

# 24. Worker Pool's Role in PF R&D

The immediate use case is:

``` text
PF backlog
   |
   v
Scheduler
   |
   +-- OpenCode session 1
   +-- OpenCode session 2
   +-- OpenCode session 3
```

Instead of manually doing:

``` text
open session
give task
wait
check result
find next task
give next task
```

PF becomes the dispatcher.

This can significantly reduce the user's role as a serial task
dispatcher.

------------------------------------------------------------------------

# 25. Future PF Product Usage

For a fully developed PF user:

``` text
User objective
      |
      v
PF planning
      |
      v
PF agent orchestration
      |
      +-- Architect
      +-- Product
      +-- Developer
      +-- QA
      +-- Security
      +-- Documentation
      +-- Domain agents
      |
      v
Product
```

The user should not normally have to know about worker registration,
leases or OpenCode sessions.

The worker subsystem may be used internally where PF needs external
execution capacity, but it is not the user's primary abstraction.

------------------------------------------------------------------------

# 26. API-First Requirement

All scheduler/worker functionality must be available through PF APIs.

The TUI and UI should be clients of those APIs.

Minimum logical API capabilities:

``` text
Backlog
  create/update/get/list
  dependencies
  grooming
  analysis

Scheduler
  get_next_work
  claim
  release
  pause
  resume
  status

Workers
  register
  heartbeat
  status
  capabilities
  unregister

Assignments
  create
  get
  renew
  complete
  fail
  recover

Execution
  start
  stop
  result
  evidence
```

Exact URL paths must follow existing PF API conventions.

Do not introduce a second API style.

------------------------------------------------------------------------

# 27. TUI

Minimal initial commands:

``` text
PF> backlog
PF> backlog show PF-ENG-0421
PF> backlog groom
PF> backlog analyze PF-ENG-0421

PF> work
PF> scheduler status

PF> workers
PF> worker status
```

Optional later:

``` text
PF> scheduler start
PF> scheduler stop
PF> worker register
PF> worker drain
```

The TUI should not contain scheduler logic. It calls the
API/control-plane functions.

------------------------------------------------------------------------

# 28. UI

The eventual UI should expose:

### Backlog

``` text
Priority
Task
Status
Analysis
Dependencies
Worker
Progress
```

### Scheduler

``` text
Ready
Blocked
Assigned
In Progress
Completed
```

### Workers

``` text
Worker
Runtime
Role
Capabilities
Status
Current Task
Heartbeat
Lease
```

### Task details

``` text
Requirement
Analysis
Architecture fit
Dependencies
Assignment
Execution
Evidence
Validation
History
```

Do not expose unnecessary runtime internals to normal PF users.

------------------------------------------------------------------------

# 29. Scheduler State Ownership

The scheduler must maintain execution coordination state, but the
backlog remains the SSOT for work.

Therefore:

``` text
Backlog SSOT:
  what the task is
  lifecycle
  priority
  dependencies
  analysis
  outcome

Scheduler state:
  claim
  lease
  worker availability
  dispatch state
  transient execution coordination
```

Scheduler state must not become a competing permanent task database.

Where possible, execution state should be persisted through the existing
PF canonical state mechanism.

------------------------------------------------------------------------

# 30. Completion and Counter

There should not be a fragile global "next task counter" used to
determine execution.

The scheduler calculates readiness from canonical state.

Useful operational counters can still be derived:

``` text
READY count
BLOCKED count
ASSIGNED count
IN_PROGRESS count
COMPLETED count
FAILED count
AVAILABLE WORKERS
BUSY WORKERS
STALE WORKERS
```

The authoritative task identity remains the canonical task ID.

------------------------------------------------------------------------

# 31. Dependency-Aware Scheduling

Example:

``` text
PF-101  Backend API
PF-102  Worker Registry
PF-103  Scheduler
PF-104  Integration Tests
```

If:

``` text
PF-104 depends on PF-101 and PF-103
```

then:

``` text
PF-101 -> READY
PF-102 -> READY
PF-103 -> READY
PF-104 -> BLOCKED
```

Once 101 and 103 complete:

``` text
PF-104 -> READY
```

Scheduler automatically considers it.

------------------------------------------------------------------------

# 32. Contention and File/Component Conflicts

Dependencies alone are not enough.

Two tasks may be independent logically but modify the same area.

Analysis should identify likely conflicts:

``` text
Task A -> worker orchestration module
Task B -> worker orchestration module
```

Scheduler should either:

-   serialize them
-   use an explicit resource lock
-   use a declared parallel-safe strategy

Do not rely solely on Git conflicts to discover contention.

------------------------------------------------------------------------

# 33. Architecture Drift Protection

Before assignment, scheduler pre-flight should verify:

``` text
analysis current?
existing architecture still compatible?
related task changed?
dependency changed?
conflicting work active?
```

If analysis becomes stale:

``` text
READY
  |
  v
ANALYSIS_STALE
  |
  v
re-analysis
  |
  v
READY
```

This prevents an old AI recommendation from driving new implementation
after PF has materially changed.

------------------------------------------------------------------------

# 34. Worker Task Context

The scheduler should give a worker a canonical task package containing
only relevant context:

``` text
Task ID
Requirement
Acceptance criteria
Priority
Dependencies
Architecture analysis
Relevant existing components
Relevant decisions/rules
Worker role/capability expectations
Execution constraints
Validation requirements
```

Do not dump the entire PF knowledge base into every worker.

The existing PF context/memory infrastructure should retrieve relevant
information.

------------------------------------------------------------------------

# 35. Personal Intelligence Integration

The existing PF Personal Intelligence/Decision Layer should remain a
**decision/perspective layer**, not become another scheduler.

It can influence:

-   grooming
-   architecture review
-   task interpretation
-   approval requirements
-   decision confidence
-   escalation

The existing design explicitly defines PIDL as a decision/perspective
layer and says it must not become another orchestration engine.

------------------------------------------------------------------------

# 36. Security

Minimum controls:

-   authenticated worker registration
-   worker identity
-   capability validation
-   heartbeat
-   assignment authorization
-   lease validation
-   secure transport
-   audit events
-   no arbitrary worker impersonation
-   worker revocation
-   expired/stale worker handling

Registration should be minimal, but it must not be unauthenticated.

Prefer an enrollment mechanism where the worker receives a
short-lived/bootstrap credential and exchanges it for a scoped worker
credential.

Do not create a second identity system if PF already has one.

------------------------------------------------------------------------

# 37. Failure Scenarios

### Worker disappears

``` text
heartbeat stops
    |
lease expires
    |
worker = STALE
    |
assignment recovery policy
```

### Scheduler restarts

It reconstructs active assignments from canonical persisted state.

### Worker reconnects

It re-registers/reconciles its session state.

### Duplicate registration

Use stable worker identity plus session identity.

### Duplicate task request

Claim operation is idempotent/atomic.

### Task result arrives late

Validate assignment/lease/version before accepting it.

### Task changed while assigned

Mark execution/result against the exact task version.

------------------------------------------------------------------------

# 38. Versioning

Tasks should have a version/revision.

Example:

``` text
PF-ENG-0421
revision: 7
```

Assignment records:

``` text
task_id: PF-ENG-0421
task_revision: 7
```

If the task materially changes:

``` text
revision 8
```

The old assignment/result must not silently overwrite the new task
state.

------------------------------------------------------------------------

# 39. Implementation Order

## Phase 0 --- Repository/Architecture Inventory

Before changing code:

1.  Locate existing backlog/task model.
2.  Locate canonical state.
3.  Locate scheduler.
4.  Locate worker orchestration.
5.  Locate worker/session handling.
6.  Locate queues/events.
7.  Locate API layer.
8.  Locate TUI.
9.  Locate UI.
10. Locate agent orchestration.
11. Locate task assignment logic.
12. Locate existing heartbeat/health handling.
13. Locate existing locks/concurrency mechanisms.

### Gate

Produce a reuse map:

``` text
Requirement
Existing implementation
Extension point
Required change
New code required?
```

No implementation begins until this map exists.

------------------------------------------------------------------------

## Phase 1 --- Backlog First-Class Upgrade

Extend the existing backlog/task model with only missing fields:

-   analysis state
-   priority/rank if absent
-   dependency representation
-   execution state
-   assignment reference
-   task revision
-   conflict metadata
-   architecture-fit findings
-   grooming state

Do not replace the existing model.

### Gate

Every executable task has one canonical ID and one canonical state.

------------------------------------------------------------------------

## Phase 2 --- AI + User Grooming

Add:

``` text
AI grooming
User grooming
```

using existing PF AI/context infrastructure.

### Gate

A task can become `READY` only when required grooming/analysis
conditions are satisfied.

------------------------------------------------------------------------

## Phase 3 --- Architecture Analysis

Implement:

``` text
analyze(task)
```

with:

-   reuse analysis
-   extension analysis
-   new-component assessment
-   duplication
-   dependency
-   conflict
-   drift
-   rewrite assessment
-   confidence
-   evidence

### Gate

No scheduler assignment should use stale mandatory analysis.

------------------------------------------------------------------------

## Phase 4 --- Scheduler Eligibility

Extend the existing scheduler to calculate:

``` text
eligible(task, worker)
```

based on:

-   status
-   priority
-   dependencies
-   conflicts
-   capability
-   concurrency
-   lease
-   task revision

### Gate

Two workers cannot atomically claim the same task.

------------------------------------------------------------------------

## Phase 5 --- Claim + Lease

Implement/reuse:

``` text
claim()
renew_lease()
release()
recover_expired()
```

### Gate

Worker crash does not permanently strand work.

------------------------------------------------------------------------

## Phase 6 --- Minimal Worker Registry

Implement the smallest registry required:

``` text
register
heartbeat
status
capabilities
unregister/revoke
```

Do not build a large worker management platform.

### Gate

A worker can connect/disconnect without modifying scheduler code.

------------------------------------------------------------------------

## Phase 7 --- Worker Adapter Interface

Define the runtime-neutral adapter contract.

Implement **OpenCode adapter first** because it is the current PF R&D
runtime.

Do not couple scheduler code directly to OpenCode.

### Gate

Scheduler can assign work through the adapter abstraction.

------------------------------------------------------------------------

## Phase 8 --- Manual `work`

Implement:

``` text
PF> work
```

Flow:

``` text
worker requests work
    |
scheduler selects highest eligible task
    |
atomic claim
    |
lease
    |
assignment
```

This should be the first end-to-end milestone.

------------------------------------------------------------------------

## Phase 8A --- Backlog Action to JobManager Integration

Before enabling broad automatic dispatch, wire the existing backlog execution
actions to the existing JobManager.

Required flow:

```text
Backlog item
    |
    +-- Execute Now
    |       |
    |       v
    |   JobManager submit
    |
    +-- Schedule
            |
            v
        JobManager submit with schedule/readiness
                    |
                    v
              Scheduler
                    |
                    v
             Existing worker
                    |
          +---------+---------+
          |                   |
          v                   v
   PipelineExecutor      External adapter
```

Implementation:

1. Identify the existing command/API/UI entry points that initiate execution
   or scheduling.
2. Make those entry points submit/control JobManager jobs rather than directly
   launching execution.
3. Preserve existing backlog IDs as the job's canonical work references.
4. Reuse the existing portfolio worker bridge where it already invokes
   `PipelineExecutor`.
5. Ensure job success/failure/cancel state is mirrored back to the backlog.
6. Remove only the bypassing direct-start behavior; do not rewrite the
   pipeline/executor internals.

### Gate

Tracing one executable backlog item from:

```text
Backlog -> Execute Now/Schedule -> JobManager -> claim -> execution ->
finish -> backlog state
```

must show one canonical job and no parallel execution path.

---

## Phase 9 --- Automatic Dispatch

Add:

``` text
scheduler auto mode
```

which reacts to:

-   worker becomes available
-   task becomes READY
-   dependency completes
-   lease recovery
-   worker reconnect

Automatic mode must be independently enabled/disabled.

------------------------------------------------------------------------

## Phase 10 --- Worker UI/API

Expose:

-   workers
-   assignments
-   scheduler state
-   backlog
-   leases
-   heartbeats
-   execution history

through existing API/UI architecture.

------------------------------------------------------------------------

## Phase 11 --- Additional Runtime Adapters

Only after OpenCode works cleanly:

``` text
Claude Code
other coding runtime
native PF execution
remote worker
```

No runtime should require scheduler redesign.

------------------------------------------------------------------------

## Phase 12 --- Optimization

Only after correctness:

-   better worker matching
-   capacity-aware scheduling
-   resource constraints
-   smarter parallelism
-   queue optimization
-   worker affinity
-   advanced contention detection

Do not optimize before the SSOT/claim/lease semantics are correct.

------------------------------------------------------------------------

# 40. Testing Requirements

## Backlog

-   unique task IDs
-   state transitions
-   revisioning
-   priority ordering
-   dependency resolution
-   stale analysis

## Scheduler

-   highest eligible priority
-   dependency blocking
-   contention
-   concurrent claims
-   duplicate prevention
-   lease expiration
-   recovery
-   scheduler restart

## Workers

-   registration
-   duplicate registration
-   heartbeat
-   stale detection
-   disconnect/reconnect
-   capability matching
-   revocation

## Adapters

-   OpenCode connection
-   assignment
-   execution
-   result
-   cancellation
-   failure
-   reconnect

## End-to-end

``` text
create task
 -> groom
 -> analyze
 -> ready
 -> worker registers
 -> worker asks for work
 -> scheduler claims
 -> worker executes
 -> heartbeat
 -> result
 -> validation
 -> complete
 -> dependency unlock
 -> next task assigned
```

------------------------------------------------------------------------

# 41. Important Architectural Non-Goals

Do not turn this change into:

-   a new multi-agent framework
-   a replacement for PF agent orchestration
-   an OpenCode-specific PF architecture
-   a new workflow engine
-   a new queue platform
-   a new memory platform
-   a new identity system
-   a new notification platform
-   a second backlog
-   a mandatory worker layer for PF agents
-   a requirement that every PF user manage workers
-   a rewrite of working PF modules

------------------------------------------------------------------------

# 42. Current PF R&D Operating Model

The immediate target is intentionally simple:

``` text
PF canonical backlog
        |
        v
analysis + priority + dependencies
        |
        v
scheduler
        |
   +----+----+
   |         |
manual     auto
   |         |
   +----+----+
        |
        v
available workers
        |
   +----+----+----+
   |         |    |
 OpenCode OpenCode OpenCode
 session  session  session
```

The user can still intervene at any point.

The scheduler removes the need to manually decide:

> "Which OpenCode session should I give the next task to?"

------------------------------------------------------------------------

# 43. Long-Term PF Operating Model

For the PF user:

``` text
User objective
      |
      v
PF planning
      |
      v
PF agent orchestration
      |
      +-- Agent A
      +-- Agent B
      +-- Agent C
      +-- Agent D
      |
      v
Product output
```

Worker orchestration remains an optional execution facility underneath
where required.

The PF user should primarily interact with:

-   product goals
-   backlog
-   decisions
-   approvals
-   progress
-   results

not with worker leases or OpenCode sessions.

------------------------------------------------------------------------

# 43. Current PF Code Alignment

The current `develop` branch was inspected before defining the extension boundary.

### Existing backlog is already the correct SSOT foundation

`core/backlog.py` already provides:

- one canonical backlog item per ID
- `items/<ID>.json` as the truth
- derived open/closed indexes
- counters
- append-only history
- single-writer locking
- dependency field (`deps`)
- priority field
- duplicate/near-duplicate detection
- idempotent external-ID handling

Therefore this change must **extend the existing backlog module**, not introduce a new backlog store.

### Existing job scheduler is already the correct extension point

`core/job_manager.py` already provides:

- queue states
- priority ordering
- worker assignment
- atomic `BEGIN IMMEDIATE` claim
- paused-job handling
- completion
- automatic dependent-job resume
- existing portfolio database reuse

Therefore the new scheduler requirements should **extend `job_manager.py` and its existing substrate**, rather than creating another scheduler.

What is currently missing for the requested worker-pool model includes, subject to detailed implementation verification:

- worker registration/discovery
- worker capability metadata
- heartbeat/liveness
- explicit worker lifecycle
- assignment leases
- lease renewal/expiry recovery
- stronger task/dependency eligibility against the canonical backlog
- runtime adapter boundary for external workers
- manual worker pull and automatic dispatch
- API/UI exposure of worker state

### Required integration fix: Backlog execution must enter JobManager before execution

The current code inspection also identified an important integration gap that
must be explicitly closed by this implementation.

`core/job_manager.py` is already the queue/scheduling substrate, but the current
`IntentRouter` pipeline-start path can invoke `PipelineExecutor` directly from
`_start_pipeline()` instead of first submitting the work to JobManager.

That creates a bypass:

```text
Backlog work
    |
    X ---> PipelineExecutor directly
```

The target path is:

```text
Canonical Backlog Item
        |
        v
Execute Now / Schedule action
        |
        v
JobManager enqueue/submit
        |
        v
Scheduler / existing queue worker
        |
        +-----------------------------+
        |                             |
        v                             v
PF PipelineExecutor             Registered external worker
        |                             |
        v                             v
PF native agents                 OpenCode / other runtime
```

### Required correction

Add the smallest possible integration so that **any backlog item selected for
execution is represented by a JobManager job before execution begins**.

This means:

1. Reuse the existing `core/job_manager.py`; do not create another queue.
2. Reuse the existing job states, priority, dependency handling and atomic
   claim/finish mechanisms.
3. Add/extend the job-to-backlog-item linkage where required so the job always
   carries the canonical backlog item ID(s).
4. `Execute Now` and `Schedule` are **backlog/work-management actions** that
   submit or control a JobManager job. They are not a second intake mechanism.
5. The scheduler decides when an eligible job can run.
6. The selected execution resource is then either:
   - the existing PF pipeline/native execution path, or
   - a registered external worker through the worker adapter.
7. Preserve the existing `PipelineExecutor`, `AgentRuntime`, `StageRunner` and
   native agent execution contracts. Do not route native agents through the
   external worker registry merely to satisfy this integration.
8. Completion/failure/cancellation must flow back through JobManager and update
   the canonical backlog item and existing history/evidence mechanisms.
9. The existing direct `_start_pipeline()` behavior should therefore be
   changed only at its **submission boundary**: instead of starting the
   pipeline directly, it should create/submit the corresponding JobManager
   job and allow the existing queue/worker path to invoke `PipelineExecutor`.
10. If an existing portfolio worker already performs this bridge, reuse it;
    do not introduce another runner. The implementation should converge on one
    JobManager-controlled execution path.

### Important boundary

This does **not** mean:

```text
JobManager
   |
   v
replace PipelineExecutor
```

It means:

```text
JobManager
   |
   v
existing execution entry point
   |
   +--> PipelineExecutor -> AgentRuntime / native PF agents
   |
   +--> External Worker Adapter -> registered runtime
```

JobManager owns **submission, queueing, scheduling, claim, lease and job
lifecycle**. The execution engine remains responsible for actually executing
the work.

### Implementation gate

Before declaring this feature complete, verify in code that:

- a backlog item selected for execution creates exactly one corresponding
  executable JobManager job;
- no normal execution path can silently bypass JobManager;
- `PipelineExecutor` remains unchanged as the native execution engine except
  where a minimal invocation/return integration is necessary;
- the existing portfolio/queue worker is reused rather than duplicated;
- job completion/failure is reflected in the canonical backlog item;
- duplicate submission/claim is prevented using the existing idempotency and
  atomic-claim mechanisms;
- external workers and PF native execution remain separate execution-resource
  choices under the same scheduling boundary.

This is a **wiring/integration correction**, not an architectural rewrite.

### PF agents currently use a separate native execution path

The current `PipelineExecutor` initializes and executes PF agents through the existing agent runtime and orchestrator stack. `AgentExecutionMixin.execute_agent()` does not call `job_manager`, the backlog scheduler, or an external worker registry.

`StageRunnerMixin` performs PF's existing parallel execution of independent stages and calls `execute_agent()` directly.

The current agent runtime also has its own agent context, tools, checkpoints, state and execution lifecycle.

Therefore:

**Do not route PF's native agents through the external worker scheduler as part of this change.**

The worker scheduler is for the separate use case of coordinating externally running execution sessions such as OpenCode CLI/TUI or another runtime.

The two systems should remain complementary:

```text
PF native agent orchestration
    |
    +-- Agent runtime
    +-- tools
    +-- context
    +-- memory
    +-- native PF execution
    +-- existing parallel stage execution


Canonical backlog / work scheduling
    |
    +-- optional worker scheduler
          |
          +-- registered OpenCode session
          +-- registered other runtime
          +-- future external execution resource
```

This is an extension boundary, not a replacement of the current PF agent architecture.

# 44. Final Design Principle

The final boundary should remain:

``` text
                 PF
                  |
       +----------+----------+
       |                     |
       v                     v
 Agent Orchestration     Work Orchestration
       |                     |
       |                Optional/pluggable
       |                     |
       |                  Scheduler
       |                     |
       |                Worker Registry
       |                     |
       |                Runtime Adapters
       |                     |
       |             OpenCode / Other
       |
       v
 Agent's own runtime,
 tools, context, skills,
 memory, modes and state
```

**Backlog is the SSOT.**

**Scheduler is the dispatcher.**

**Worker registry is execution capacity discovery.**

**Lease/claim state prevents duplicate work and contention.**

**Workers are pluggable external execution resources.**

**OpenCode is only the first adapter.**

**PF agents do not inherently need workers.**

**The worker subsystem can be enabled or disabled.**

**All implementation must extend/reuse existing PF infrastructure and
must not rewrite working architecture.**


## PIDL / Personal Intelligence Integration — Who Triggers It, Where, and How

The worker system must not make each worker responsible for "having the user's personality." PIDL is a centralized decision/perspective capability that is invoked at defined decision gates by the existing orchestration/scheduler path.

### Architectural ownership

```text
Backlog SSOT
    |
    v
Job Manager / Scheduler
    |
    +---- eligibility / priority / dependency / worker capability
    |
    v
Execution / Worker
    |
    v
Worker Result / Proposed Action
    |
    v
PIDL Decision Gate
    |
    +---- AUTO_PROCEED
    +---- AI_REVIEW
    +---- CORRECT / RETRY
    +---- APPROVAL_REQUIRED
    +---- ESCALATE
    |
    v
Existing Orchestration resumes
```

**PIDL owns the decision/perspective. Scheduler owns scheduling. Worker owns execution. Approval service owns secure human approval.**

This is an additive integration. It does not replace the existing PF native agent runtime or create a second orchestration engine.

### When PIDL is triggered

PIDL should not run on every worker heartbeat or every trivial scheduler operation. It is invoked at meaningful decision points:

1. **Pre-dispatch evaluation — optional**
   - Used when a task has ambiguity, competing implementation choices, special user constraints, or an approval policy that must be known before dispatch.
   - PIDL returns the relevant personal context and execution constraints.
   - Scheduler still decides whether/when the work can run.

2. **Worker-result decision gate — primary trigger**
   - Worker completes a meaningful unit of work or proposes a consequential action.
   - Existing orchestration sends the result/proposed action to PIDL.
   - PIDL retrieves only the relevant personal rules, principles, preferences, prior decisions, review lenses and evidence.
   - PIDL evaluates whether the result is consistent and what should happen next.

3. **Cross-worker synthesis gate**
   - Multiple workers complete parallel work.
   - PIDL evaluates the combined result for consistency, conflicts, architecture fit, completeness and established user perspective.
   - It can request another worker, correction, additional evidence, or approval.

4. **Before consequential action**
   - Architecture changes, security-policy changes, destructive/irreversible operations, production actions, licensing/financial commitments, or unresolved conflicts can invoke PIDL + approval policy before execution.
   - The exact policy is configurable; these are examples from the PIDL design.

5. **After user correction/approval**
   - PIDL records the decision/outcome as evidence.
   - It does not silently convert every correction into a permanent rule.
   - Authority and provenance determine whether a pattern becomes reusable.

### Who triggers PIDL

The caller should be the **existing orchestration/control path**, not the worker itself.

For the external worker model:

```text
Job Manager / Scheduler
        |
        v
Worker Adapter / Execution Controller
        |
        v
Worker Runtime
        |
        v
Result / Proposed Action
        |
        v
PIDL Service / Module
```

For PF's native agent path:

```text
PipelineExecutor
   |
   +--> existing native AgentRuntime / StageRunner
   |
   +--> PIDL decision gate when a meaningful decision boundary is reached
```

**Do not insert the external worker scheduler between PF native agents and AgentRuntime.** PIDL is the shared decision capability; the execution path remains native where it is already native.

### How the "AI personality" gets included

Do not inject a giant personality prompt into every worker.

PIDL maintains structured, versioned personal intelligence records:

```text
Personal Intelligence
|
+-- Identity / communication style
+-- Thinking style
+-- Principles
|   +-- architecture
|   +-- engineering
|   +-- QA
|   +-- product
|   +-- UX
|   +-- security
|   +-- operations
+-- Preferences
+-- Strict rules
+-- Approval rules
+-- Prior decisions
+-- Decision patterns
+-- Review lenses
+-- Evidence / provenance
+-- Corrections
+-- Outcome feedback
```

At a PIDL invocation:

```text
Task / Result
    |
    v
Relevant-context retrieval
    |
    +-- applicable strict rules
    +-- applicable principles
    +-- relevant preferences
    +-- relevant prior decisions
    +-- applicable review lenses
    +-- relevant evidence
    |
    v
PIDL decision engine
    |
    +-- deterministic policy checks
    +-- LLM reasoning where needed
    |
    v
Structured decision
```

Only the **relevant subset** becomes the PIDL context for that decision. The complete personal profile is never blindly loaded into every worker.

### What the worker actually receives

A worker receives an execution contract, not the complete personality:

```yaml
task_id: BI-ENG-042
task_revision: 7

pidl_context:
  profile_version: 12
  applicable_rules:
    - PIDL-RULE-004
  applicable_principles:
    - backward_compatibility
    - extend_before_rewrite
  applicable_preferences:
    - reuse_existing_infrastructure
  review_lenses:
    - architecture
    - QA
    - security

execution_policy:
  autonomy: allowed
  approval_required: false
  escalation_allowed: true
```

The worker can therefore behave consistently with the user's established constraints without becoming the owner of those constraints.

### PIDL decision contract

A PIDL invocation should return structured data:

```yaml
decision:
  action: AUTO_PROCEED | REVIEW | CORRECT | APPROVAL_REQUIRED | ESCALATE

confidence:
  factual: 0.96
  architectural: 0.91
  requirement_interpretation: 0.88
  user_preference: 0.87
  implementation: 0.93
  overall: 0.91

risk: LOW | MEDIUM | HIGH

recommendation:
  ...

evidence:
  - reference: PIDL-RULE-004
  - reference: PF-DEC-172

conflicts: []

approval:
  required: false
  policy: ...

next_action:
  ...
```

The scheduler/orchestrator then acts on this structured result.

### Critical separation of responsibilities

| Component | Responsibility |
|---|---|
| **Backlog SSOT** | What work exists and its canonical state |
| **Scheduler / Job Manager** | What is eligible, priority, dependency, lease and assignment |
| **Worker Registry** | What execution capacity exists |
| **Worker Adapter** | How PF invokes a runtime such as OpenCode |
| **Worker** | Performs the assigned execution |
| **PIDL** | Applies the user's established perspective, rules, principles, evidence and decision policy |
| **Approval Policy** | Determines whether human approval is required |
| **Approval Service** | Authenticated approve/reject of the exact decision/action |
| **Audit/Evidence** | Records what happened and why |
| **Memory/RAG** | Stores/retrieves relevant knowledge; PIDL owns the logical personal-intelligence namespace, not a separate memory platform |

### Important distinction: personality vs execution

The "AI personality" should therefore be understood as a **decision/perspective layer**, not a worker persona.

```text
PERSONAL INTELLIGENCE
        |
        | influences
        v
DECISION / POLICY
        |
        | constrains / guides
        v
EXECUTION CONTEXT
        |
        v
WORKER
```

This prevents three architectural problems:

- duplicating the personality into every worker;
- allowing a worker to change or override the user's rules;
- coupling PIDL to OpenCode or any other particular runtime.

### Parallel workers

For parallel execution:

```text
                    Canonical Task
                         |
              +----------+----------+
              |          |          |
              v          v          v
           Worker A   Worker B   Worker C
              |          |          |
              +----------+----------+
                         |
                         v
                  PIDL synthesis gate
                         |
              +----------+----------+
              |          |          |
             pass      correct     approval
              |          |          |
              v          v          v
           continue    re-dispatch  user
```

Independent workers do not wait for one another merely because PIDL exists. PIDL is invoked where a decision boundary or synthesis point actually requires it.

### PIDL versioning and traceability

Every PIDL decision should record:

```text
task_id
task_revision
worker_id / runtime
pidl_profile_version
rules used
principles used
prior decisions used
evidence references
decision version
confidence
risk
approval policy/version
decision outcome
```

If the personal-intelligence rules change after a decision, the old decision remains explainable because it references the exact PIDL/profile versions used at that time.

### Implementation order for this integration

This does not change the previously defined worker/scheduler implementation order. Add PIDL as a capability at the following points:

1. Keep Backlog SSOT unchanged except for any required PIDL decision references.
2. Keep Job Manager/Scheduler as the scheduling authority.
3. Keep Worker Registry and Worker Adapter independent of PIDL.
4. Add a small `PIDLContextResolver` using the existing memory/RAG/context infrastructure.
5. Add a `PIDLDecisionEngine` using deterministic policy first and the existing LLM/provider abstraction where reasoning is required.
6. Add the primary **worker-result decision gate**.
7. Add pre-dispatch PIDL evaluation only where a task actually requires it.
8. Add cross-worker synthesis/review.
9. Add centralized approval-policy integration.
10. Add outcome/correction feedback and controlled learning.
11. Add UI/API visibility for the PIDL decision, evidence, confidence and approval state.
12. Keep the worker runtime adapters unchanged except for consuming the execution context/decision contract.

### Non-goal

Do **not** create:

```text
Personality Worker
Personality Scheduler
Personality Queue
Personality Workflow Engine
Personality-specific OpenCode architecture
```

PIDL is a reusable PF capability invoked by existing orchestration at decision gates.
