# Product Forge --- Agent Memory Architecture Integration Specification

**Document Status:** Proposed Architecture Integration\
**Target:** Product Forge / Product Factory\
**Purpose:** Formalize and integrate a unified agent-memory architecture
into the existing Product Forge runtime without unnecessarily replacing
existing components.

------------------------------------------------------------------------

## 1. Executive Summary

Product Forge already contains substantial memory-related capabilities:
context management, persistent memory, knowledge/retrieval, skills,
execution state, workflows, Git/files/artifacts, evaluation, policies,
and model/provider abstractions.

However, these capabilities are currently better understood as
**distributed memory-related infrastructure** rather than one explicit,
governed Agent Memory Architecture.

This specification formalizes that architecture.

The recommended approach is **not** to create seven independent memory
subsystems. Instead, Product Forge should introduce a unified **Memory &
Context Platform** that classifies and orchestrates existing
capabilities into:

1.  Working / Context Memory
2.  Semantic Memory
3.  Episodic Memory
4.  Procedural Memory
5.  External / Retrieval Memory
6.  Prospective Memory
7.  Parametric Memory boundary

The three most important platform components to formalize/add are:

-   **Memory Orchestrator**
-   **Memory Compiler**
-   **Memory Consolidator**

Supporting contracts should cover:

-   memory taxonomy
-   memory record schema
-   scope and isolation
-   authority and provenance
-   retrieval and ranking
-   validation and promotion
-   lifecycle and supersession
-   conflict resolution
-   context/token budgeting
-   security and access control
-   observability and evaluation

The objective is to make Product Forge capable of reliable long-running,
multi-agent, resumable execution where agents do not merely "remember"
information, but retrieve, validate, use, verify, and consolidate memory
under explicit controls.

------------------------------------------------------------------------

# 2. Architectural Principle

The core principle is:

> **Persistent memory should not simply be dumped into an agent's
> context. It must be selectively retrieved, validated, ranked,
> governed, and compiled into task-specific working context.**

The runtime flow should be:

``` text
Retrieve
   ↓
Validate
   ↓
Rank
   ↓
Compile
   ↓
Reason
   ↓
Plan
   ↓
Execute
   ↓
Verify
   ↓
Consolidate
   ↓
Update Memory
```

A memory item is not automatically authoritative merely because an agent
previously generated it.

------------------------------------------------------------------------

# 3. Current Product Forge Capability Mapping

Product Forge already has many building blocks.

  ------------------------------------------------------------------------------------
  Memory capability       Existing Product Forge direction     Integration decision
  ----------------------- ------------------------------------ -----------------------
  Working / Context       Context manager, execution/session   Preserve and formalize
                          context                              

  Persistent memory       Persistent memory capabilities       Preserve and classify

  Semantic memory         Knowledge/document/source retrieval  Formalize as semantic
                                                               memory

  Episodic memory         Execution/job/history/observations   Formalize as episodic
                                                               memory

  Procedural memory       Skills, workflows, agent procedures  Formalize as procedural
                                                               memory

  External memory         Git, files, artifacts, DB, KB        Preserve as
                                                               authoritative external
                                                               sources

  Prospective memory      Tasks, DAG/workflow, scheduler       Formalize as
                                                               future-action memory

  Parametric memory       Model/provider layer                 Keep outside persistent
                                                               Product Forge memory

  Memory Orchestration    Distributed logic                    Add explicit platform
                                                               service/contract

  Memory Compilation      Partially implicit in context        Add explicit component
                          handling                             

  Memory Consolidation    Reflection/evaluation concepts       Formalize as explicit
                                                               lifecycle

  Authority/provenance    Policies, evidence, artifacts, Git   Unify under memory
                                                               governance

  Lifecycle               Partial retention/history concepts   Add explicit state
                                                               model

  Cross-agent isolation   Existing policy/security concepts    Formalize memory scope
                                                               policy
  ------------------------------------------------------------------------------------

**Conclusion:** This is primarily an **integration and formalization
effort**, not a replacement architecture.

------------------------------------------------------------------------

# 4. Unified Agent Memory Model

``` text
                         AGENT MEMORY
                              |
       +----------------------+----------------------+
       |                      |                      |
       v                      v                      v
 MODEL MEMORY          PERSISTENT MEMORY       RUNTIME MEMORY
       |                      |                      |
 Parametric          +--------+--------+       Working /
 Memory              |        |        |       Context
                     v        v        v
                  Semantic Episodic Procedural
                     |        |        |
                     +--------+--------+
                              |
                         Prospective
                           Memory
                              |
                              v
                     External Evidence
```

## 4.1 Parametric Memory

Parametric memory is the knowledge and capability encoded in model
parameters.

Examples:

-   general programming knowledge
-   general language knowledge
-   general software engineering patterns
-   general Kubernetes knowledge
-   general REST/API concepts

It belongs to the **model/provider boundary**, not the Product Forge
persistent-memory store.

Project-specific authoritative information must take precedence over
generic model knowledge.

------------------------------------------------------------------------

# 5. Memory Types

## 5.1 Working / Context Memory

### Purpose

Information required by the agent **right now**.

### Typical contents

-   current objective
-   current task/subtask
-   active instructions
-   retrieved memory
-   current plan
-   current tool results
-   current variables
-   current errors
-   active constraints
-   current decisions
-   verification state
-   pending actions

### Lifetime

Seconds to current execution/session/checkpoint.

### Storage

Context manager / runtime state / checkpoint state.

### Important rule

Working memory is a **compiled temporary view**, not the authoritative
source of truth.

------------------------------------------------------------------------

## 5.2 Semantic Memory

Semantic memory represents information the system has established or
retained as knowledge.

Examples:

``` text
Product Forge uses API-first architecture.

Authentication uses OAuth2 + JWT.

Project X uses PostgreSQL.

ADR-024 established the authentication architecture.
```

Possible contents:

-   facts
-   concepts
-   decisions
-   constraints
-   project knowledge
-   architecture knowledge
-   preferences
-   validated lessons

Semantic memory should retain provenance and authority metadata.

------------------------------------------------------------------------

## 5.3 Episodic Memory

Episodic memory represents **what happened**.

Example:

``` text
Execution #381

Agent: QA Agent
Task: API regression

Result:
47 passed
3 failed

Failure:
Refresh-token test failed.

Root cause:
Token expiry configuration mismatch.

Resolution:
Configuration corrected.

Verification:
All tests passed.
```

Episodic memory should preserve:

-   execution ID
-   agent
-   task
-   timestamps
-   actions
-   observations
-   tool results
-   errors
-   outcomes
-   verification evidence
-   causal relationships where available

------------------------------------------------------------------------

## 5.4 Procedural Memory

Procedural memory represents **how to perform a task**.

Examples:

-   skills
-   SOPs
-   workflows
-   test procedures
-   coding standards
-   troubleshooting procedures
-   deployment procedures
-   recovery procedures
-   agent-specific operating instructions

Product Forge's existing **Skills** architecture should become a major
source of procedural memory.

------------------------------------------------------------------------

## 5.5 External / Retrieval Memory

External memory is information stored outside the agent memory layer.

Examples:

-   Git repositories
-   source code
-   architecture documents
-   PRDs
-   ADRs
-   databases
-   APIs
-   test reports
-   CI/CD results
-   build artifacts
-   logs
-   product documents
-   knowledge bases

External sources can provide authoritative evidence for memory.

Example:

``` text
Semantic memory:
"Authentication uses JWT."

Authoritative evidence:
ADR-024
architecture/security/authentication.md
commit abc123
```

Memory should retain the reference to the evidence rather than copying
large source documents unnecessarily.

------------------------------------------------------------------------

## 5.6 Prospective Memory

Prospective memory represents **future actions that must occur**.

Examples:

-   run security scan after build
-   verify deployment after deployment
-   rerun failed test after fix
-   wait for approval before merge
-   create release notes after release candidate passes
-   revisit unresolved issue
-   execute a scheduled workflow

Prospective memory should integrate tightly with:

-   task management
-   workflow/DAG engine
-   scheduler
-   event system
-   condition triggers

It should not become an unstructured reminder database.

------------------------------------------------------------------------

# 6. Memory Architecture

The target Product Forge architecture should be:

``` text
                    PRODUCT FORGE
                         |
              +----------+----------+
              |                     |
              v                     v
         AGENT RUNTIME        ORCHESTRATION
              |                     |
              +----------+----------+
                         |
                         v
              +---------------------+
              | MEMORY ORCHESTRATOR |
              +----------+----------+
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
      Semantic       Episodic       Procedural
       Memory         Memory          Memory
          |              |              |
          +--------------+--------------+
                         |
                         v
                  Prospective Memory
                         |
                         v
                External Retrieval
                         |
                         v
              +----------------------+
              | MEMORY GOVERNANCE    |
              | Authority            |
              | Provenance           |
              | Validation           |
              | Freshness            |
              | Security             |
              | Isolation            |
              +----------+-----------+
                         |
                         v
              +----------------------+
              |   MEMORY COMPILER    |
              | Relevance            |
              | Ranking              |
              | Conflict resolution  |
              | Token budgeting      |
              | Context construction |
              +----------+-----------+
                         |
                         v
                 WORKING CONTEXT
                         |
                         v
                       AGENT
                         |
                 Plan / Act / Tools
                         |
                         v
                    Verification
                         |
                         v
              +----------------------+
              | MEMORY CONSOLIDATOR  |
              +----------+-----------+
                         |
              +----------+----------+
              |          |          |
              v          v          v
           Episodic   Semantic   Procedural
             update     update     update
                         |
                         v
                   Prospective
                     actions
```

------------------------------------------------------------------------

# 7. Memory Orchestrator

The Memory Orchestrator is the central control point.

It determines:

-   what memory is needed
-   which memory sources to query
-   which scopes apply
-   which agent is requesting memory
-   authority requirements
-   freshness requirements
-   retrieval limits
-   privacy/security constraints
-   whether external evidence must be consulted
-   what can enter the context

### Example

``` text
QA Agent
   |
   v
Memory Orchestrator
   |
   +--> Requirements
   +--> Previous failures
   +--> Test procedures
   +--> Current source
   +--> Current build
   +--> Pending QA tasks
   |
   v
Memory Compiler
   |
   v
QA-specific context
```

------------------------------------------------------------------------

# 8. Memory Compiler

The Memory Compiler converts distributed memory into a **task-specific
context package**.

It must answer:

-   What is relevant?
-   What is authoritative?
-   What is current?
-   What conflicts?
-   What is stale?
-   What evidence supports it?
-   How much can fit into the context budget?
-   Which instructions must be pinned?
-   Which information can be summarized?
-   Which information must be retained verbatim?

### Target flow

``` text
Memory stores
      |
      v
Retrieval
      |
      v
Ranking
      |
      v
Authority check
      |
      v
Conflict resolution
      |
      v
Freshness check
      |
      v
Token/context optimization
      |
      v
Context Compiler
      |
      v
Agent Context
```

The compiler should prevent the common failure mode:

> The correct instruction exists somewhere in the system but is not
> reliably available to the agent at the point of execution.

------------------------------------------------------------------------

# 9. Memory Consolidator

The Memory Consolidator processes execution outcomes and determines what
should become persistent memory.

``` text
Agent execution
       |
       v
Observations
       |
       v
Tool results
       |
       v
Tests / verification
       |
       v
Memory candidates
       |
       v
Validation
       |
       v
Classification
       |
       +----> Episodic
       +----> Semantic
       +----> Procedural
       +----> Prospective
       |
       v
Persist / Update / Supersede / Reject
```

### Critical rule

**Unverified agent output must not automatically become trusted
persistent memory.**

------------------------------------------------------------------------

# 10. Memory Record Schema

Every persistent memory record should have a common envelope.

Suggested schema:

``` yaml
memory_id:
memory_type:
scope:
sub_scope:

content:

source:
source_type:
source_reference:

provenance:
  created_by:
  created_at:
  observed_at:
  effective_from:
  effective_until:

authority:
verification_status:
confidence:
freshness:

status:
  ACTIVE | SUPERSEDED | EXPIRED | REJECTED | ARCHIVED

supersedes:
superseded_by:

project_id:
product_id:
agent_scope:
task_scope:
session_scope:

access_policy:

tags:
embedding_reference:
structured_reference:

evidence:
  - reference:
    type:
    verification:

metadata:
```

------------------------------------------------------------------------

# 11. Memory Authority Model

Memory should not be treated as equally trustworthy.

Recommended authority levels:

``` text
L0 — Parametric knowledge
     Generic model knowledge

L1 — Unverified observation
     Agent-generated observation

L2 — Retrieved evidence
     External source retrieved for reference

L3 — Validated memory
     Evaluated and verified information

L4 — Authoritative project state
     Approved ADR/specification/Git/artifact/workflow state

L5 — Runtime control state
     Current execution/checkpoint/transaction state
```

The exact numbering can be changed during implementation; the important
concept is explicit authority.

Example:

``` text
Memory:
Authentication uses JWT

Source:
ADR-024

Evidence:
commit abc123

Validation:
passed

Authority:
PROJECT_AUTHORITATIVE
```

------------------------------------------------------------------------

# 12. Memory Lifecycle

Every memory candidate should follow:

``` text
OBSERVE
   |
CAPTURE
   |
CLASSIFY
   |
ENRICH
   |
VALIDATE
   |
SCORE
   |
CONSOLIDATE
   |
STORE
   |
INDEX
   |
RETRIEVE
   |
USE
   |
REVALIDATE
   |
UPDATE / SUPERSEDE / EXPIRE
```

Memory must be allowed to become stale.

Example:

``` text
Old:
PostgreSQL 15
Status: SUPERSEDED

New:
PostgreSQL 17
Status: ACTIVE

Source:
Approved architecture change
```

------------------------------------------------------------------------

# 13. Temporal Memory

Temporal memory should be treated as a **dimension across memory
types**, not as another independent memory type.

Examples:

-   semantic + temporal
-   episodic + temporal
-   procedural + temporal
-   prospective + temporal

Questions the system must support:

``` text
What is true now?
What was true at time T?
What happened?
When did it happen?
Which procedure applied at that time?
Which decision superseded another decision?
```

This is important for evolving repositories, dependencies,
architectures, models, workflows and policies.

------------------------------------------------------------------------

# 14. Memory Scope and Isolation

Memory must have explicit scope.

Recommended hierarchy:

``` text
Global
  |
  +-- Organization
       |
       +-- Product
            |
            +-- Project
                 |
                 +-- Workflow
                      |
                      +-- Agent
                           |
                           +-- Task
                                |
                                +-- Session
```

Example:

``` text
Global:
REST API knowledge

Product:
Product Forge architecture

Project:
MyMoney architecture

Task:
Implement voice provider adapter

Session:
Current debugging information
```

An agent must not automatically inherit memory from unrelated projects.

------------------------------------------------------------------------

# 15. Agent-Specific Memory Retrieval

Different agents should have different retrieval policies.

## Coding Agent

Retrieve:

-   architecture
-   coding standards
-   relevant source
-   implementation procedures
-   previous implementation attempts
-   active task
-   relevant ADRs

## QA Agent

Retrieve:

-   requirements
-   test strategy
-   test procedures
-   previous failures
-   source/API state
-   build/test artifacts
-   pending test tasks

## Security Agent

Retrieve:

-   security requirements
-   security procedures
-   dependency state
-   previous findings
-   configuration
-   compliance evidence

The Memory Orchestrator should therefore use **agent role + task +
scope + policy** to construct retrieval requests.

------------------------------------------------------------------------

# 16. Memory Retrieval Pipeline

Recommended retrieval stages:

``` text
1. Determine task intent
        |
2. Determine agent role
        |
3. Determine memory scope
        |
4. Identify required memory types
        |
5. Retrieve candidates
        |
6. Filter by access policy
        |
7. Filter stale/superseded records
        |
8. Rank by relevance
        |
9. Rank by authority
        |
10. Resolve conflicts
        |
11. Retrieve supporting evidence where needed
        |
12. Apply token/context budget
        |
13. Compile final context
```

------------------------------------------------------------------------

# 17. Conflict Resolution

Memory conflicts must be explicit.

Example:

``` text
Memory A:
Database = PostgreSQL 15
Source: old architecture document

Memory B:
Database = PostgreSQL 17
Source: approved ADR
```

The system should not simply select whichever vector result scores
higher.

It should consider:

``` text
Authority
Freshness
Effective date
Scope
Source type
Verification
Supersession
```

Result:

``` text
PostgreSQL 17 = ACTIVE
PostgreSQL 15 = SUPERSEDED
```

------------------------------------------------------------------------

# 18. Memory and Evidence

The architecture should distinguish:

``` text
Memory
   ≠
Evidence
```

Memory may summarize an observation.

Evidence proves or supports it.

Example:

``` text
Semantic memory:
"API authentication uses JWT."

Evidence:
ADR-024
Source code
CI result
Approved specification
```

Where possible, memory should retain references to evidence.

------------------------------------------------------------------------

# 19. Memory and Product Forge Reliability

This architecture directly addresses several agent reliability problems:

### Problem: Agent forgets an instruction

Solution:

``` text
Persistent instruction
   ↓
Semantic/Procedural memory
   ↓
Retrieval
   ↓
Memory Compiler
   ↓
Pinned working context
```

### Problem: Agent claims something was completed

Solution:

``` text
Claim
   ↓
Execution state
   ↓
Artifact/test/evidence
   ↓
Verification
   ↓
Only then mark complete
```

### Problem: Agent repeats a known failure

Solution:

``` text
Previous failure
   ↓
Episodic memory
   ↓
Failure pattern
   ↓
Procedural/semantic consolidation
   ↓
Retrieved during future execution
```

### Problem: Old architecture contaminates current execution

Solution:

``` text
Temporal metadata
+
supersession
+
authority
+
freshness
```

### Problem: Too much memory enters context

Solution:

``` text
Memory Compiler
+
relevance ranking
+
authority filtering
+
token budgeting
```

------------------------------------------------------------------------

# 20. Memory vs Context vs State

These must remain separate.

  Concept           Meaning
  ----------------- ---------------------------------------------------------
  Memory            Information retained for future use
  Context           Information supplied to the model for current reasoning
  State             Current execution condition
  Evidence          Data supporting a claim
  Artifact          Produced output
  Task              Work that must be performed
  Procedure/Skill   How work should be performed

Example:

``` text
Memory:
"Previous deployment failed due to missing DB_URL."

State:
"Current deployment is running."

Context:
"Before deployment, validate DB_URL."

Evidence:
Deployment log.

Artifact:
Deployment manifest.

Task:
Deploy service.

Procedure:
Deployment workflow.
```

This separation is important and should be enforced in the architecture.

------------------------------------------------------------------------

# 21. Integration With Existing Product Forge Components

Do not create duplicate systems.

## Reuse

``` text
Existing Context Manager
        → Working Memory

Existing Persistent Memory
        → Persistent Memory foundation

Existing Skills
        → Procedural Memory

Existing DAG / Workflow Engine
        → Prospective Memory

Existing Scheduler
        → Prospective triggers

Existing Git/File/Artifact systems
        → External Memory/Evidence

Existing Execution State
        → Episodic source

Existing Evaluation
        → Memory validation

Existing Policies
        → Memory governance

Existing Model Gateway
        → Parametric-memory boundary
```

## Add/formalize

``` text
Memory Orchestrator
Memory Compiler
Memory Consolidator
Memory Record Contract
Memory Authority Model
Memory Lifecycle
Memory Scope Policy
Memory Retrieval Contract
Memory Evaluation Metrics
Memory Observability
```

------------------------------------------------------------------------

# 22. Proposed APIs

The exact technology can follow Product Forge's existing API-first
conventions.

## Retrieve memory

``` http
POST /memory/retrieve
```

Request:

``` json
{
  "agent_id": "qa-agent",
  "project_id": "product-forge",
  "task_id": "task-123",
  "memory_types": [
    "semantic",
    "episodic",
    "procedural",
    "external"
  ],
  "query": "authentication regression testing",
  "max_tokens": 12000
}
```

## Compile context

``` http
POST /memory/compile
```

## Record memory candidate

``` http
POST /memory/candidates
```

## Consolidate

``` http
POST /memory/consolidate
```

## Validate

``` http
POST /memory/validate
```

## Supersede

``` http
POST /memory/{memory_id}/supersede
```

## Retrieve evidence

``` http
POST /memory/evidence
```

These should remain behind the Product Forge memory abstraction rather
than being coupled directly to one vector database or provider.

------------------------------------------------------------------------

# 23. Storage Strategy

Do not force all memory into one storage technology.

A practical architecture is:

``` text
Semantic
   → structured DB + vector/graph indexes

Episodic
   → execution/event store + searchable index

Procedural
   → skills/workflow repository + structured metadata

Prospective
   → task/workflow/scheduler store

External
   → Git/files/DB/artifacts/knowledge stores

Working
   → runtime/context/checkpoint store
```

Vector search should be considered a **retrieval mechanism**, not the
definition of memory.

------------------------------------------------------------------------

# 24. Memory Quality Controls

Every memory operation should support:

### Relevance

Is this relevant to the current task?

### Authority

How authoritative is the source?

### Freshness

Is the information still current?

### Confidence

How strongly is the information supported?

### Verification

Was it actually checked?

### Provenance

Where did it come from?

### Scope

Which product/project/agent can use it?

### Conflict

Does it contradict another memory?

### Lifecycle

Is it active, superseded, expired, archived, or rejected?

------------------------------------------------------------------------

# 25. Security Requirements

Memory must be treated as a security boundary.

Required controls:

-   tenant isolation
-   project isolation
-   agent isolation
-   role-based access
-   secret filtering
-   PII handling
-   prompt-injection protection
-   untrusted-source labeling
-   provenance
-   audit logging
-   memory write authorization
-   memory read authorization
-   deletion/retention policy
-   immutable evidence where required

An agent must not be allowed to write arbitrary information into
authoritative memory.

------------------------------------------------------------------------

# 26. Memory Write Policy

Not every agent output should become memory.

Recommended promotion model:

``` text
Agent output
    |
    v
Candidate memory
    |
    v
Classification
    |
    v
Evidence check
    |
    v
Verification
    |
    +---- FAIL ----> Reject / retain as untrusted episode
    |
    +---- PASS
           |
           v
      Promotion policy
           |
     +-----+------+
     |            |
     v            v
 Persistent     Temporary
 memory         observation
```

High-authority memory should require stronger verification.

------------------------------------------------------------------------

# 27. Memory Consolidation Example

Suppose deployment fails because `DB_URL` is missing.

The system can create:

### Episodic memory

``` text
Deployment #847 failed because DB_URL was missing.
```

### Semantic memory

``` text
Service X requires DB_URL in production.
```

### Procedural memory

``` text
Before deployment, validate mandatory environment variables.
```

### Prospective memory

``` text
Run environment validation before the next deployment.
```

### External evidence

``` text
Deployment log
CI result
Configuration file
Git commit
```

One execution can therefore produce several related memory records.

------------------------------------------------------------------------

# 28. Memory Graph

Where useful, related memories should be linked.

``` text
             ADR-024
                |
                v
        Semantic Decision
                |
        +-------+-------+
        |               |
        v               v
 Procedure          Execution
        |               |
        |               v
        |            Failure
        |               |
        |               v
        +--------> Lesson
                     |
                     v
              Future Procedure
```

This is useful for traceability and root-cause analysis.

------------------------------------------------------------------------

# 29. Context Compilation Contract

A compiled context should contain structured sections.

Example:

``` text
SYSTEM / GOVERNANCE
- Active policies
- Authority rules

TASK
- Objective
- Acceptance criteria

AUTHORITATIVE KNOWLEDGE
- Relevant semantic memory

RELEVANT HISTORY
- Relevant episodic memory

PROCEDURES
- Required skills/workflows

CURRENT STATE
- Execution/checkpoint state

EVIDENCE
- Source/artifact references

PENDING ACTIONS
- Prospective memory

CONSTRAINTS
- Technical/business/security constraints

VERIFICATION
- Required validation steps
```

This makes context predictable rather than an arbitrary collection of
retrieved chunks.

------------------------------------------------------------------------

# 30. Failure Handling

Memory operations must fail safely.

Examples:

### Retrieval unavailable

Do not invent memory.

``` text
MEMORY_UNAVAILABLE
```

### Conflicting authoritative memories

Pause or invoke conflict resolution.

``` text
MEMORY_CONFLICT
```

### Evidence unavailable

Lower authority.

``` text
UNVERIFIED_MEMORY
```

### Memory stale

Retrieve current external source.

``` text
STALE_MEMORY
```

### Context budget exceeded

Compile a smaller context rather than blindly truncating critical
instructions.

------------------------------------------------------------------------

# 31. Observability

Track memory-specific metrics.

Recommended metrics:

``` text
Memory retrieval latency
Memory retrieval hit rate
Relevant-memory precision
Context usefulness
Memory conflict rate
Stale-memory rate
Memory validation rate
Memory promotion rate
Memory rejection rate
Memory supersession rate
Duplicate-memory rate
Context token utilization
Memory-induced failures
Memory-related agent retries
```

These should feed Product Forge's existing QA/agent evaluation
framework.

------------------------------------------------------------------------

# 32. Implementation Priority

## P0 --- Mandatory

1.  Define memory taxonomy.
2.  Define common memory record contract.
3.  Formalize working/context memory.
4.  Introduce Memory Orchestrator contract.
5.  Introduce Memory Compiler.
6.  Introduce Memory Consolidator.
7.  Define authority/provenance.
8.  Define scope/isolation.
9.  Define validation/write policy.
10. Integrate with existing agent runtime.

## P1 --- High Priority

11. Temporal metadata.
12. Supersession/versioning.
13. Memory conflict resolution.
14. Agent-specific retrieval policies.
15. Evidence linking.
16. Memory observability.
17. Memory evaluation metrics.

## P2 --- Advanced

18. Memory graph.
19. Learned retrieval/ranking.
20. Adaptive context compilation.
21. Memory quality prediction.
22. Cross-project knowledge promotion with explicit authorization.
23. Advanced memory compression/summarization.

------------------------------------------------------------------------

# 33. Migration Strategy

Do not rewrite the existing Product Forge memory implementation.

### Phase 1 --- Classification

Map existing components and data into:

``` text
Working
Semantic
Episodic
Procedural
Prospective
External
```

### Phase 2 --- Contracts

Introduce common interfaces:

``` text
MemoryRecord
MemorySource
MemoryRetriever
MemoryValidator
MemoryCompiler
MemoryConsolidator
MemoryPolicy
```

### Phase 3 --- Orchestration

Route existing memory retrieval through the Memory Orchestrator.

### Phase 4 --- Context Compilation

Make the Memory Compiler the controlled path into agent context.

### Phase 5 --- Consolidation

Route execution outcomes through Memory Consolidator.

### Phase 6 --- Governance

Add:

-   authority
-   provenance
-   temporal state
-   supersession
-   scope
-   access control

### Phase 7 --- Optimization

Optimize:

-   retrieval
-   ranking
-   context size
-   latency
-   token cost
-   memory quality

------------------------------------------------------------------------

# 34. Acceptance Criteria

The integration is complete when Product Forge can demonstrate:

### Retrieval

-   Agent retrieves relevant memory automatically.
-   Retrieval is task/agent/project scoped.
-   Irrelevant memory is filtered.

### Authority

-   Authoritative sources outrank unverified agent memory.
-   Conflicting memories are detected.
-   Superseded memories are not silently treated as current.

### Context

-   Only relevant memory enters working context.
-   Context compilation is deterministic/auditable.
-   Critical instructions are protected from accidental truncation.

### Execution

-   Agent can use semantic, episodic, procedural and prospective memory.
-   Agent can retrieve external evidence.
-   Agent can resume from checkpoints.

### Consolidation

-   Verified outcomes can become persistent memory.
-   Failed/unverified outcomes are not promoted to authoritative
    knowledge.
-   Lessons can become procedural/semantic memory.

### Lifecycle

-   Memories can be updated.
-   Memories can be superseded.
-   Memories can expire.
-   Historical state can be reconstructed.

### Security

-   Memory access is scoped.
-   Cross-project leakage is prevented.
-   Sensitive information is controlled.
-   Memory writes are governed.

------------------------------------------------------------------------

# 35. Final Target Architecture

``` text
                         PRODUCT FORGE
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
     Agent Runtime       Orchestration       Governance
          |                   |                   |
          +-------------------+-------------------+
                              |
                              v
                  +-------------------------+
                  |   MEMORY ORCHESTRATOR   |
                  +------------+------------+
                               |
          +--------------------+--------------------+
          |         |          |         |          |
          v         v          v         v          v
      Semantic  Episodic  Procedural  Prospective External
       Memory    Memory     Memory      Memory     Retrieval
          |         |          |         |          |
          +---------+----------+---------+----------+
                              |
                              v
                  +-------------------------+
                  |    MEMORY GOVERNANCE    |
                  | authority               |
                  | provenance              |
                  | freshness               |
                  | validation              |
                  | security                |
                  | scope                   |
                  | lifecycle               |
                  +------------+------------+
                               |
                               v
                  +-------------------------+
                  |     MEMORY COMPILER     |
                  | relevance               |
                  | ranking                 |
                  | conflict resolution     |
                  | token budget             |
                  | context assembly         |
                  +------------+------------+
                               |
                               v
                    WORKING / CONTEXT MEMORY
                               |
                               v
                          AGENT / MODEL
                               |
                    +----------+----------+
                    |                     |
                  ACTION              OBSERVATION
                    |                     |
                    +----------+----------+
                               |
                               v
                         VERIFICATION
                               |
                               v
                  +-------------------------+
                  |  MEMORY CONSOLIDATOR    |
                  +------------+------------+
                               |
                 +-------------+-------------+
                 |             |             |
                 v             v             v
             Episodic      Semantic      Procedural
             Update        Update        Update
                               |
                               v
                         Prospective
                           Actions
                               |
                               v
                         Future Runtime
```

------------------------------------------------------------------------

# 36. Architectural Decision

## Decision

**Adopt the Unified Agent Memory Architecture as a Product Forge
platform capability.**

Do not create independent implementations for every memory type.

Instead:

> **Formalize and unify the existing Product Forge context, persistent
> memory, skills, execution history, workflows, scheduler, external
> repositories, evidence, policies and evaluation systems behind a
> governed Memory & Context Platform.**

### Mandatory new/formalized platform capabilities

``` text
Memory Orchestrator
Memory Compiler
Memory Consolidator
Memory Record Contract
Memory Authority/Provenance
Memory Scope/Isolation
Memory Lifecycle
Memory Validation/Promotion
Memory Retrieval/Ranking
Memory Observability
```

### Components to preserve

``` text
Context Manager
Persistent Memory
Skills
Workflow/DAG Engine
Scheduler
Execution State
Git/File/Artifact Systems
Knowledge Retrieval
Policies
Evaluation
Model Gateway
```

This minimizes architectural churn while providing the missing control
layer required for reliable agentic execution.

------------------------------------------------------------------------

# 37. Key Design Rule for Product Forge

The final architecture should enforce:

``` text
              KNOW
               |
               v
             RETRIEVE
               |
               v
             VERIFY
               |
               v
             COMPILE
               |
               v
            REASON
               |
               v
              ACT
               |
               v
            VERIFY
               |
               v
          CONSOLIDATE
               |
               v
             LEARN
```

And never:

``` text
Agent said it
     ↓
Store it
     ↓
Believe it forever
```

The memory architecture must therefore be treated as part of the **Agent
Reliability, Governance, Context Management, and Execution Control
plane**, not merely as a knowledge-storage feature.
