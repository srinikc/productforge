# Auto-Company — Adoptable Patterns for AI Product Factory

## Objective

Use Auto-Company as a reference for strengthening the **autonomous execution layer** of the AI Product Factory.

Do **not** replicate Auto-Company wholesale.

Adopt the architectural patterns that make the Factory capable of continuously progressing a product without requiring the user to manually orchestrate every agent.

---

# 1. Adopt: Persistent Autonomous Execution Loop

This is the most important pattern.

The Factory should operate as:

```text
Goal
 ↓
Read State
 ↓
Determine Next Action
 ↓
Select Agents
 ↓
Execute
 ↓
Validate
 ↓
Persist Results
 ↓
Update State
 ↓
Determine Next Action
 ↺
```

Instead of:

```text
User → Prompt → Agents → Result
```

we want:

```text
Product Goal
     ↓
Factory State
     ↓
Autonomous Decision
     ↓
Execution
     ↓
Validation
     ↓
State Update
     ↓
Next Action
     ↺
```

### Why

This turns the Product Factory from an **agent toolbox** into an **autonomous product-building system**.

---

# 2. Adopt: Dynamic Agent Squad Formation

Do not run the entire agent team for every task.

The Orchestrator should determine the capabilities required and dynamically create a temporary squad.

Example:

```text
Task: Validate a new SaaS idea

→ Market Research
→ Product Strategy
→ Competitive Intelligence
→ Finance
→ UX
```

Later:

```text
Task: Implement authentication

→ Architect
→ Backend Engineer
→ Security
→ QA
```

Architecture:

```text
Task
 ↓
Capability Analysis
 ↓
Agent Registry
 ↓
Select Required Agents
 ↓
Create Squad
 ↓
Execute
 ↓
Dissolve Squad
```

### Benefit

- Lower token cost
- Faster execution
- Less unnecessary context
- Better specialization
- Easier scaling

---

# 3. Adopt: Capability-Based Agent Registry

Auto-Company's specialized roles are useful, but the Factory should use **capabilities and responsibilities**, not primarily personality/celebrity personas.

Each agent should define:

```yaml
name:
capabilities:
responsibilities:
tools:
inputs:
outputs:
decision_rights:
constraints:
approval_authority:
```

Example:

```yaml
name: Security Engineer

capabilities:
  - threat_modeling
  - dependency_analysis
  - authentication_review
  - vulnerability_analysis

tools:
  - repository
  - terminal
  - security_scanner

outputs:
  - security_report
  - remediation_plan

decision_rights:
  can_block_release: true
```

This allows the Orchestrator to select agents based on **what they can do**.

---

# 4. Adopt: Shared Persistent State

Adopt Auto-Company's idea of a shared `consensus.md`, but evolve it beyond one file.

### Initial implementation

```text
factory/
└── state/
    ├── current_state.md
    ├── consensus.md
    ├── decisions.md
    └── backlog.md
```

### Later

Move structured state into a database/event system while retaining human-readable Markdown projections.

```text
Database
   +
Event Log
   +
Artifact Store
   +
Markdown Views
```

### Principle

Agents should not need the entire historical conversation.

They should receive:

```text
Current objective
Current state
Relevant decisions
Relevant artifacts
Current task
Required context
```

---

# 5. Adopt: Forced Convergence

Prevent autonomous agents from becoming trapped in endless discussion.

Every agent cycle should move toward one of:

```text
DECISION
ACTION
ARTIFACT
BLOCKER
ESCALATION
LEARNING
```

Recommended product workflow:

```text
DISCOVER
 ↓
RESEARCH
 ↓
ANALYZE
 ↓
VALIDATE
 ↓
DECIDE
 ↓
EXECUTE
```

Once sufficient evidence exists, the system must transition from **thinking → doing**.

This should be enforced by the Orchestrator.

---

# 6. Adopt: Artifact-Based Agent Handoffs

Agents should communicate through durable artifacts wherever possible.

Example:

```text
Research Agent
      ↓
market_research.md
      ↓
Product Agent
      ↓
product_spec.md
      ↓
Architect
      ↓
architecture.md
      ↓
Engineering
      ↓
source code
      ↓
QA
      ↓
test_report.json
```

This gives the Factory:

- Auditability
- Resumability
- Debuggability
- Parallel execution
- Smaller context windows
- Better human visibility

The artifact becomes the contract between agents.

---

# 7. Adopt: Product Development State Machine

The autonomous loop should operate around explicit product states.

```text
IDEA
 ↓
DISCOVERY
 ↓
RESEARCH
 ↓
EVALUATION
 ↓
GO / NO-GO
 ↓
SPECIFICATION
 ↓
DESIGN
 ↓
ARCHITECTURE
 ↓
BUILD
 ↓
TEST
 ↓
SECURITY REVIEW
 ↓
DEPLOY
 ↓
MEASURE
 ↓
FEEDBACK
 ↓
IMPROVE
 ↺
```

The current state determines:

- What needs to happen
- Which agents are eligible
- What artifacts are required
- What approval gates apply
- What the next transition can be

---

# 8. Adopt: Existing Coding Agents as Execution Engines

Do not build another coding agent inside the Factory.

Use existing powerful coding agents as execution workers.

Conceptually:

```text
PRODUCT FACTORY
      ↓
ORCHESTRATOR
      ↓
CODING AGENT
      ↓
Tools
├── Files
├── Terminal
├── Git
├── Browser
├── APIs
├── Tests
└── Cloud
```

The Factory owns:

```text
WHAT
WHO
WHEN
WHY
STATE
VALIDATION
NEXT
```

The coding agent handles:

```text
HOW
```

This separation should remain an architectural boundary.

---

# 9. Adopt: Continuous Runtime / Supervisor

The Factory should eventually be able to operate as a persistent service.

```text
Factory Supervisor
       ↓
Execution Cycle
       ↓
Agent Squad
       ↓
Validation
       ↓
State Update
       ↓
Next Cycle
```

The supervisor handles:

- Process failures
- Agent crashes
- Timeouts
- Retries
- Rate limits
- Budget limits
- Checkpoint recovery
- Pausing/resuming

This is preferable to relying on one long-running LLM session.

---

# 10. Adopt: Checkpoint + Resume

Every meaningful Factory step should create recoverable state.

```text
Task Started
     ↓
Checkpoint
     ↓
Agent Execution
     ↓
Artifact Created
     ↓
Checkpoint
     ↓
Validation
     ↓
State Update
```

If the process crashes:

```text
Crash
 ↓
Load Last Checkpoint
 ↓
Inspect State
 ↓
Resume From Safe Point
```

The Factory should not need to restart the entire product-building process.

---

# 11. Adopt: Circuit Breakers and Failure Handling

Autonomy requires explicit failure boundaries.

```text
Execution
 ↓
Failure
 ↓
Retry
 ↓
Failure
 ↓
Alternate Strategy
 ↓
Failure
 ↓
Circuit Break
 ↓
Mark Blocked
 ↓
Escalate / Wait
```

Implement:

```text
Maximum retries
Execution timeout
Token budget
Financial budget
Tool timeout
Agent timeout
Circuit breaker
Rollback
Human escalation
```

Never allow:

```text
Agent fails → retry forever
```

---

# 12. Adopt: Human Steering

Human control should be **interruptive**, not mandatory for every step.

Provide:

```text
PAUSE
RESUME
APPROVE
REJECT
OVERRIDE
REPRIORITIZE
ROLLBACK
ESCALATE
```

Example:

```text
Factory:
Ready to deploy.

Human:
PAUSE.
Add payment support first.

Factory:
Update state
 ↓
Reprioritize
 ↓
Create new squad
 ↓
Continue
```

This preserves autonomy while keeping the system controllable.

---

# 13. Adopt: Factory Constitution / Guardrails

Create a persistent set of rules available to every agent.

```text
FACTORY_CONSTITUTION.md
```

Include:

```text
Mission
Operating principles
Security rules
Privacy rules
Quality standards
Coding standards
Deployment policies
Budget limits
Approval requirements
Forbidden actions
Escalation rules
```

Agents should treat this as the Factory's operating contract.

---

# 14. Adopt: Explicit Agent Decision Rights

Every agent should have bounded authority.

Example:

```text
Research
 → Recommend

Product
 → Approve specification

Architect
 → Approve architecture

Engineer
 → Modify development branch

QA
 → Block failed release

Security
 → Block security-risk release

Finance
 → Block excessive spend

Human
 → Override
```

This is critical for safe autonomy.

---

# 15. Adopt: Event-Driven Extensions

The initial implementation can use cycles.

Eventually add events:

```text
new_idea
research_completed
spec_approved
code_committed
test_failed
security_issue_found
deployment_failed
user_feedback_received
metric_threshold_crossed
```

Architecture:

```text
Event
 ↓
State Change
 ↓
Trigger
 ↓
Agent Squad
 ↓
Execution
 ↓
New Event
 ↺
```

This will make the Factory reactive rather than merely scheduled.

---

# 16. Adopt: Execution Memory, Not Conversation Memory

Do not preserve everything just because agents generated it.

Store useful execution knowledge:

```text
Decisions
Requirements
Architecture
Experiments
Failures
Lessons
User feedback
Metrics
Successful strategies
```

Recommended structure:

```text
Memory
├── Working
├── Product
├── Decisions
├── Experiments
├── Lessons
├── Knowledge
└── Artifacts
```

Memory should answer:

> "What does the Factory need to know to make the next correct decision?"

---

# 17. Factory Architecture After Adopting These Patterns

```text
                         PRODUCT FACTORY
                                │
                    ┌───────────┴───────────┐
                    │                       │
                 Mission                  Events
                    │                       │
                    └───────────┬───────────┘
                                ↓
                         FACTORY STATE
                                ↓
                         ORCHESTRATOR
                                ↓
                       TASK / STATE ENGINE
                                ↓
                      CAPABILITY ANALYSIS
                                ↓
                       AGENT REGISTRY
                                ↓
                       DYNAMIC AGENT SQUAD
                                ↓
                ┌───────────────┼───────────────┐
                ↓               ↓               ↓
             Research         Build           Review
                │               │               │
                └───────────────┼───────────────┘
                                ↓
                            ARTIFACTS
                                ↓
                           VALIDATION
                                ↓
                       APPROVAL / GATES
                                ↓
                         STATE UPDATE
                                ↓
                      CHECKPOINT / MEMORY
                                ↓
                         NEXT ACTION
                                ↺
```

---

# 18. What We Should NOT Adopt

Do not copy these aspects directly:

```text
14 permanently active agents
Celebrity-based agent identities
Single Markdown file as permanent state
Shell scripts as the complete orchestration layer
Unbounded autonomous execution
Unrestricted agent permissions
Conversation-heavy agent collaboration
```

These can be useful for experimentation, but should not become core architecture.

---

# 19. Implementation Priority

## P0 — Core Factory

Implement first:

```text
✓ Factory State
✓ Autonomous Loop
✓ Orchestrator
✓ Agent Registry
✓ Capability-Based Agent Selection
✓ Dynamic Squads
✓ Product State Machine
✓ Artifact Handoffs
✓ Checkpoints
✓ Human Pause/Resume
✓ Guardrails
```

## P1 — Reliable Autonomy

Then:

```text
✓ Retry System
✓ Circuit Breakers
✓ Budget Controls
✓ Approval Gates
✓ Git Integration
✓ QA Gates
✓ Security Gates
✓ Persistent Supervisor
✓ Structured Decision Records
```

## P2 — Advanced Factory

Later:

```text
○ Event-Driven Runtime
○ Long-Term Organizational Memory
○ Knowledge Graph
○ Autonomous Experimentation
○ Product Portfolio Management
○ Automatic Optimization
○ Multi-Product Factory
```

---

# Final Decision

**Adopt Auto-Company as a reference for the Factory's autonomous execution architecture.**

The highest-value concepts are:

```text
Persistent State
        +
Autonomous Loop
        +
Dynamic Agent Squads
        +
Capability-Based Agents
        +
Forced Convergence
        +
Artifact Handoffs
        +
Checkpointing
        +
Failure Recovery
        +
Human Steering
        +
Guardrails
        +
Continuous Runtime
```

The key architectural addition to the Product Factory is therefore:

> **An Autonomous Factory Runtime that continuously reads product state, determines the next required action, assembles the appropriate agent squad, executes through existing agent/tool runtimes, validates the outcome, persists the resulting artifacts and decisions, and continues from the new state.**

Auto-Company provides a strong reference for this layer; the Product Factory should build a more structured, modular and product-development-specific version of it.