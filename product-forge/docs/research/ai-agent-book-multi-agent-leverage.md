# AI Agent Book — Multi-Agent System Leverage

Source: https://github.com/bojieli/ai-agent-book
Focus: What we should extract and apply when designing our multi-agent system.

## Executive Summary

**Keep this repository as a foundational architecture reference.**

Its central model is:

> **Agent = LLM + Context + Tools**

For a multi-agent platform, the important lesson is that adding more agents is not the primary source of capability. The system should first provide each agent with the right **context, knowledge, tools, constraints, verification, and feedback loops**. Multi-agent orchestration then becomes a controlled way to divide work, specialize capabilities, and improve reliability.

The book's 10-chapter structure covers agent fundamentals, context engineering, memory/knowledge, tools, coding agents, interaction/observation/action spaces, evaluation, post-training, continuous evolution, and multi-agent collaboration.

---

# 1. What We Should Leverage

## 1.1 Agent = LLM + Context + Tools

Use this as the base abstraction for every agent.

Each agent definition should specify:

- **Reasoning model** — which model is appropriate for the task
- **Context** — system instructions, task state, relevant knowledge, history
- **Tools** — explicitly defined actions available to the agent
- **Constraints** — permissions and boundaries
- **Verification** — how outputs/actions are checked
- **Correction** — retry, repair, fallback, escalation

Do not define an agent as merely a prompt/persona.

Recommended conceptual interface:

```text
Agent
├── Identity / Role
├── Goal
├── Model
├── Context Policy
├── Skills
├── Knowledge Access
├── Tools
├── Permissions
├── Memory
├── State
├── Verification
├── Recovery / Retry
└── Evaluation
```

---

# 2. Harness Engineering Should Be a First-Class Layer

One of the strongest ideas to carry into our architecture is **Harness engineering**.

The harness controls the environment in which an agent operates.

Use five functions:

```text
Context → Tools → Constrain → Verify → Correct
```

### Context
Give the agent sufficient information to make the current decision.

### Tools
Provide clear, narrow, agent-friendly interfaces.

### Constrain
Use least privilege and fail-safe defaults. Capabilities should be explicitly enabled.

### Verify
Validate structured outputs, tool results, files, tests, policies, and state transitions.

### Correct
Retry recoverable failures, repair bad outputs, and escalate after repeated failure.

For our system:

```text
Agent
  ↓
Harness
  ├── Context manager
  ├── Skill loader
  ├── Knowledge router
  ├── Tool router
  ├── Permission manager
  ├── State manager
  ├── Validator
  ├── Evaluator
  └── Recovery controller
```

**Important:** the harness should remain independent from individual agent personalities.

---

# 3. Context Engineering

Context should be treated as a managed resource, not an unlimited conversation transcript.

Use:

- static context
- dynamic task context
- relevant memory
- retrieved knowledge
- tool results
- agent state
- task artifacts
- summaries / compression
- on-demand context loading

Avoid sending the entire history to every agent by default.

### Multi-agent implication

Prefer **distilled handoffs** between specialized agents when full context is unnecessary.

```text
Research Agent
     ↓
Research Result
     ↓
Structured Handoff
     ↓
Architecture Agent
```

Instead of:

```text
Agent B receives entire Agent A transcript
```

This reduces context growth, cost, noise, and accidental coupling.

---

# 4. Shared vs Non-Shared Context

This is one of the most important architectural decisions for our multi-agent system.

## Shared Context

Agent B receives the complete relevant trajectory of Agent A.

Use when:

- continuity is essential
- the next agent must understand detailed reasoning
- iterative refinement is required
- context size remains manageable

## Non-Shared Context

Agents operate independently and exchange:

- structured messages
- task results
- files
- artifacts
- summaries
- explicit handoff packages

Use by default when agents have distinct responsibilities.

### Recommended default

```text
Shared workspace
        +
Structured handoffs
        +
Selective context inheritance
```

Do **not** make full transcript sharing the default.

---

# 5. Multi-Agent Topologies

The book identifies three useful collaboration patterns.

## 5.1 Peer / Pipeline Collaboration

Agents have specialized roles and pass work between one another.

```text
Planner
   ↓
Researcher
   ↓
Implementer
   ↓
Tester
   ↓
Reviewer
```

Best for:

- predictable workflows
- staged production
- software engineering
- research pipelines

## 5.2 Manager / Orchestrator Pattern

A manager dynamically delegates tasks to specialist agents.

```text
              Orchestrator
            /      |              Research  Coding   Testing
            \      |       /
              Results
```

Best for:

- dynamic tasks
- uncertain decomposition
- variable specialist requirements

The orchestrator should manage **work**, not perform every task itself.

## 5.3 Decentralized Collaboration

Agents have relatively equal responsibility and coordinate through shared state/messages.

Best for:

- distributed exploration
- negotiation
- simulations
- complex cooperative problems

Use cautiously because coordination cost and emergent failure modes increase.

---

# 6. Agent Roles Should Be Capability-Based

Do not create dozens of agents merely because different prompts sound useful.

Prefer a smaller number of strong specialist roles.

Example:

```text
Orchestrator
├── Planner
├── Research Agent
├── Knowledge Agent
├── Coding Agent
├── Security Agent
├── Test / Evaluation Agent
├── Reviewer
└── Release / Operations Agent
```

Each role should have:

- explicit responsibility
- explicit inputs
- explicit outputs
- explicit tools
- explicit permissions
- explicit success criteria

An agent should be specialized because its **capability boundary** differs, not merely because its prompt is different.

---

# 7. Structured Handoffs

Introduce a standard handoff contract.

Example:

```yaml
handoff:
  task_id: "..."
  from_agent: "researcher"
  to_agent: "architect"
  status: "completed"

  objective:
    "...what was requested..."

  findings:
    - "..."

  evidence:
    - source: "..."
      claim: "..."

  decisions:
    - "..."

  uncertainties:
    - "..."

  artifacts:
    - path: "..."

  recommended_next_action:
    "..."

  validation:
    status: "passed"
```

This makes agent collaboration observable, testable, resumable, and debuggable.

---

# 8. Shared Workspace / Data Plane

A major architectural takeaway is to treat shared artifacts as part of the multi-agent runtime.

Recommended virtual workspace:

```text
/workspace/
├── task/
├── shared/
├── agents/
│   ├── planner/
│   ├── researcher/
│   ├── coder/
│   └── tester/
├── artifacts/
├── evidence/
├── reports/
└── state/
```

### Four useful areas

1. **Agent-specific workspace**
2. **Multi-agent shared workspace**
3. **External resources**
4. **System resources**

This gives agents a stable place to exchange information without forcing everything through model context.

---

# 9. Tools as Agent Interfaces

Tools should be designed for agents, not merely exposed as programmer APIs.

Apply an **Agent-Computer Interface (ACI)** mindset.

Good tools should have:

- intuitive names
- clear parameters
- examples
- narrow responsibilities
- predictable outputs
- explicit failure modes
- safe defaults

Bad:

```text
execute()
```

Better:

```text
run_unit_tests(test_path, timeout)
```

Better tools reduce reasoning burden and prevent misuse.

---

# 10. MCP / Tool Layer

The architecture should support a standardized tool layer.

Potential categories:

```text
Perception Tools
├── Search
├── Read
├── Browse
├── Inspect
└── Retrieve

Execution Tools
├── Write
├── Edit
├── Run
├── Deploy
└── Communicate

Collaboration Tools
├── Delegate
├── Handoff
├── Ask Agent
├── Publish Artifact
└── Request Review
```

Tool access should be permissioned per agent.

---

# 11. Least Privilege

Every agent should have only the tools and permissions it needs.

Example:

```text
Research Agent
  ✓ search
  ✓ browser
  ✓ knowledge retrieval
  ✗ production deployment
  ✗ secrets
  ✗ arbitrary shell

Coding Agent
  ✓ repository read/write
  ✓ tests
  ✓ build
  ✗ production credentials

Release Agent
  ✓ deployment
  ✓ monitoring
  ✗ unrestricted source modification
```

Use explicit capability grants rather than broad access.

---

# 12. Verification Must Be Independent

Never rely solely on an agent claiming that its work is correct.

Use independent verification:

```text
Agent produces result
        ↓
Validator
        ↓
Tests / schemas / policies / evidence
        ↓
Pass / Fail
```

Examples:

- schema validation
- unit tests
- integration tests
- linting
- security scanning
- factual evidence checks
- policy checks
- artifact existence checks
- regression evaluation

For important tasks, use a separate evaluator/reviewer agent.

---

# 13. Evaluation Is Part of the Architecture

Evaluation should not be added after the system is built.

Define measurable success criteria for each agent and workflow.

Examples:

```text
Research Agent
- factual accuracy
- citation coverage
- source quality
- completeness

Coding Agent
- tests passing
- correctness
- regression rate
- security findings

Planner
- task decomposition quality
- dependency correctness
- execution success

Multi-Agent Workflow
- end-to-end success
- latency
- token cost
- handoff failures
- retry rate
- human escalation rate
```

Use:

- controlled comparisons
- ablation tests
- regression suites
- representative task sets
- statistical analysis where appropriate

The book explicitly emphasizes evaluation as the mechanism for distinguishing real capability improvements from superficial changes.

---

# 14. Agent Loops

Use the basic loop:

```text
Observe
  ↓
Think / Plan
  ↓
Act
  ↓
Observe Result
  ↓
Verify
  ↓
Correct / Continue
```

For multi-agent systems:

```text
Task
 ↓
Decompose
 ↓
Delegate
 ↓
Execute
 ↓
Verify
 ↓
Repair
 ↓
Integrate
 ↓
Evaluate
```

This should be the standard runtime loop.

---

# 15. Coding Agents Are Especially Important

Treat code as a special capability because code can create or modify future tools and workflows.

A coding agent can:

```text
inspect system
   ↓
write code
   ↓
run tests
   ↓
observe failures
   ↓
modify code
   ↓
repeat
```

Therefore coding agents should have stronger:

- sandboxing
- permissions
- verification
- test requirements
- change tracking
- rollback
- human escalation

This is particularly relevant to an autonomous multi-agent software-development system.

---

# 16. Continuous Evolution

The architecture should eventually learn from operations.

Capture:

```text
Execution
   ↓
Outcome
   ↓
Evaluation
   ↓
Feedback
   ↓
Learning Signal
   ↓
System Improvement
```

But separate different kinds of updates:

### Within-task adaptation
Temporary context/state.

### External artifact update
Update:

- Skills
- knowledge
- procedures
- documentation
- reusable code

### Model update
SFT/RL or other parameter-level training.

Do not automatically modify the model or core system from every runtime failure.

---

# 17. Memory Architecture

Separate memory into layers.

```text
Working Memory
    ↓
Task Memory
    ↓
User / Project Memory
    ↓
Knowledge Base
    ↓
Long-Term Operational Memory
```

Use structured storage where possible.

Potential components:

- vector retrieval
- structured indexes
- knowledge graphs
- artifact repositories
- execution histories
- learned procedures

The important principle is **retrieve only what is relevant**.

---

# 18. Failure Modes to Design For

Multi-agent systems introduce new failure modes.

Plan for:

### Context explosion
Too much information passed between agents.

### Coordination overhead
Agents spend more effort communicating than solving.

### Cascading errors
One incorrect result propagates through the workflow.

### Conflicting outputs
Agents reach incompatible conclusions.

### Duplicate work
Multiple agents independently solve the same task.

### Infinite delegation
Agents keep delegating instead of executing.

### Authority confusion
Agents don't know who owns the final decision.

### Shared-state corruption
Agents overwrite or invalidate one another's artifacts.

### Silent failure
An agent reports success without verification.

### Cost explosion
Too many agents, tool calls, or retries.

### Emergent behavior
Interactions produce outcomes not intended by individual prompts.

---

# 19. Recommended Architecture for Our Multi-Agent System

Use the book's principles as a foundation for this architecture:

```text
                         USER / SYSTEM
                              │
                              ▼
                    ┌──────────────────┐
                    │   ORCHESTRATOR   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          Planner        Researcher       Builder
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                     Shared Workspace
                             │
                 ┌───────────┼───────────┐
                 ▼           ▼           ▼
             Knowledge     Skills      Artifacts
                 │           │           │
                 └───────────┼───────────┘
                             ▼
                       Verification
                             │
                      ┌──────┴──────┐
                      ▼             ▼
                    PASS          FAIL
                      │             │
                      ▼             ▼
                 Integration      Repair
                      │             │
                      └──────┬──────┘
                             ▼
                         Evaluation
                             │
                             ▼
                    Learning / Evolution
```

Across all agents:

```text
                ┌─────────────────────────┐
                │          HARNESS         │
                │                          │
                │ Context                  │
                │ Skills                   │
                │ Knowledge                │
                │ Tools                    │
                │ Permissions              │
                │ State                    │
                │ Verification             │
                │ Recovery                 │
                │ Evaluation               │
                └─────────────────────────┘
```

---

# 20. What NOT to Copy

The book should be used as an architectural reference, not copied blindly.

Do not:

- create multi-agent complexity before proving a single-agent workflow
- pass entire transcripts everywhere
- create agents for trivial specialization
- expose unrestricted tools
- trust model-generated claims without verification
- use a manager agent for every task
- treat memory as one giant vector database
- optimize prompts before fixing context/tool architecture
- add frameworks simply because they are fashionable
- allow agents to modify core system behavior without validation

The book's simplicity principle is particularly important:

> Start with the simplest architecture that works, then add complexity only when evidence shows it is needed.

---

# 21. Priority Implementation Order

For our system, leverage the repository in this order:

## P0 — Foundation

- Agent contract
- Harness
- Context management
- Tool interface
- Permissions
- State
- Structured outputs
- Verification

## P1 — Multi-Agent Runtime

- Orchestrator
- Agent registry
- Delegation
- Structured handoffs
- Shared workspace
- Task graph
- Retry/recovery

## P2 — Knowledge + Skills

- Skill registry
- Knowledge router
- RAG
- structured knowledge
- long-term memory
- artifact memory

## P3 — Evaluation

- workflow test suite
- agent-level metrics
- evaluator agents
- regression testing
- cost/latency monitoring

## P4 — Autonomous Coding

- sandboxed coding agent
- test/repair loop
- code review agent
- security agent
- release agent

## P5 — Continuous Evolution

- operational feedback
- skill improvement
- knowledge updates
- workflow optimization
- controlled learning
- model improvement

---

# 22. Key Principle for Our System

The most important takeaway is:

> **Multi-agent capability should emerge from well-designed context, tools, skills, memory, permissions, verification, and orchestration—not simply from having more agents.**

Therefore:

```text
                 BAD
                  │
        "Let's add more agents"
                  │
                  ▼
          Complex coordination
                  │
                  ▼
             Fragility


                 GOOD
                  │
        Strong agent primitives
                  │
          ┌───────┼────────┐
          ▼       ▼        ▼
       Context  Tools   Knowledge
          │       │        │
          └───────┼────────┘
                  ▼
              Harness
                  │
          Verification
                  │
          Simple Agents
                  │
          Multi-Agent Graph
                  │
          Evaluation Loop
                  │
             Evolution
```

---

# 23. Final Assessment

**Recommendation: KEEP / FOUNDATIONAL**

This repository should become one of the core references for our multi-agent architecture.

### Leverage heavily

- Agent = LLM + Context + Tools
- Harness engineering
- Context engineering
- Skills
- Memory / knowledge
- Tool design / ACI
- Least privilege
- Verification
- Agent loops
- Evaluation
- Continuous evolution
- Shared vs non-shared context
- Multi-agent topology
- Structured handoffs
- Shared workspace / data plane

### Use selectively

- Specific framework implementations
- Particular model choices
- Experimental architectures
- Examples tied to rapidly changing APIs

### Architectural role

```text
AI Agent Book
      ↓
FOUNDATIONAL PRINCIPLES
      ↓
Multi-Agent Architecture
      ↓
+ Current agent frameworks
+ Coding-agent patterns
+ Security practices
+ Evaluation systems
+ Knowledge/skill systems
```

**Bottom line:** This is not primarily another repository to install. It is a **design and engineering reference that should shape the architecture of the multi-agent platform itself.**
