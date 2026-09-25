# Loop Modes for Agentic Systems

## Purpose

Agent systems should not be designed only as:

`Prompt → LLM → Answer`

A more capable architecture uses explicit **execution loops** that determine how work starts, continues, gets evaluated, retries, and finishes.

The key shift is:

`Goal → Execute → Evaluate → Retry / Route → Complete`

Prompt engineering is **not dead**. It becomes one component inside a larger **agent-engineering** system.

---

## 1. Four Core Loop Modes

### 1.1 Turn-Based Loop

**Pattern:**

`Prompt → Work → Check → Reply`

**Characteristics**
- Human-driven
- Interactive
- One task/turn at a time
- Human retains control
- AI performs a bounded unit of work and returns control

**Best for**
- Ambiguous requirements
- Exploration
- Tasks needing frequent human decisions
- High-risk actions
- Early product/design work

**Typical autonomy:** low

---

### 1.2 Goal-Based Loop

**Pattern:**

`Goal → Try → Judge → Done`

If the evaluation fails:

`Goal → Try → Judge → Retry → ...`

**Characteristics**
- Target-driven
- Defines what "done" means before execution
- Agent can iterate autonomously
- Independent evaluator determines success
- Stops when acceptance criteria pass or a retry/trial limit is reached

**Best for**
- Software development
- Test fixing
- Bug resolution
- Acceptance-test-driven work
- Tasks with objective success criteria

**Critical principle:**

> Do not let the worker be the sole judge of its own success.

Prefer:

`Worker → Artifact → Independent Evaluator → Pass/Fail`

Example:

`Requirement → Coding Agent → Tests → Evaluator → PASS`

or

`Requirement → Coding Agent → Tests → Evaluator → FAIL → Coding Agent`

This is one of the most important agentic control loops.

---

### 1.3 Time-Based Loop

**Pattern:**

`Interval → Check → React → Wait → Check`

**Characteristics**
- Timer/schedule-driven
- Periodically inspects an external system
- Acts only when a relevant change is detected
- Continues until cancelled or the underlying task ends

**Best for**
- Scheduled reports
- CI/CD checks
- Pull-request monitoring
- Periodic data collection
- External-system health checks
- Recurring summaries

Example:

`Every interval → Inspect PR → New reviewer comment? → Fix/Test → Wait`

Prefer event-driven triggers where available instead of unnecessarily polling every few minutes.

---

### 1.4 Proactive / Event-Based Loop

**Pattern:**

`Event → Route → Parallel Work → Review → Output`

**Characteristics**
- Hands-off
- Event-driven
- Router dispatches work automatically
- Multiple child agents can operate concurrently
- Review/synthesis happens after work
- Human does not need to initiate every task

Example:

`PR Opened`
→ Router
→ Security Agent
→ Code Review Agent
→ Test Agent
→ Documentation Agent
→ Synthesis/Review
→ Output

**Best for**
- Bug reports
- GitHub events
- Issue triage
- Dependency changes
- Batch processing
- Automated engineering workflows
- Continuous agent operations

**Typical autonomy:** high

---

# 2. Loop Modes Are Orchestration Primitives

These four modes should be treated as reusable orchestration primitives rather than four competing agent architectures.

```text
                         AGENT SYSTEM
                              │
             ┌────────────────┼────────────────┐
             ↓                ↓                ↓
        TURN-BASED       GOAL-BASED       EVENT-BASED
             │                │                │
          Human            Evaluator         Router
          control          + Retry          + Parallel
             │                │                │
             └────────────────┼────────────────┘
                              ↓
                       TIME / SCHEDULE
                              │
                              ↓
                         PROACTIVE OPS
```

A real workflow may combine multiple modes.

Example:

`Event → Router → Parallel Agents → Goal Loop → Evaluator → Human Approval`

---

# 3. Five Important Agent-System Layers

Loop mode is only one layer of a complete agent system.

## A. Agents

Who performs the work?

Examples:
- Architect
- Developer
- Researcher
- Tester
- Security Agent
- UI/UX Agent
- Data Analyst

## B. Skills / Knowledge

What does the agent know how to do?

Examples:
- Coding skills
- Security practices
- Engineering methodology
- Framework knowledge
- Domain knowledge
- Course-derived knowledge
- Documentation and reference material

## C. Orchestrator

Who decides which agent works and when?

Capabilities:
- Sequential execution
- Parallel execution
- Conditional branching
- Routing
- Graph workflows
- Hierarchical delegation
- Dependency management

## D. Evaluators

Who determines whether the work is actually good?

Possible evaluators:
- Unit tests
- Integration tests
- End-to-end tests
- Linters
- Security scanners
- Acceptance criteria
- LLM judges
- Human approval

## E. Loop / Trigger

What causes the system to continue?

Modes:
- Turn-based
- Goal-based
- Time-based
- Event-based
- Proactive

---

# 4. Recommended Software-Engineering Pattern

For autonomous product/code development:

```text
                    USER GOAL
                       ↓
                 ORCHESTRATOR
                       ↓
              ┌────────┴────────┐
              ↓                 ↓
          ARCHITECT           RESEARCH
              ↓                 ↓
              └────────┬────────┘
                       ↓
                     CODER
                       ↓
                  TEST AGENT
                       ↓
                   EVALUATOR
                   /        \
                FAIL        PASS
                 ↓            ↓
               CODER        REVIEW
                 ↑            ↓
                 └──────── DONE
```

The loop should have explicit:
- Goal
- Acceptance criteria
- Maximum retries
- State
- Context
- Tool permissions
- Evaluation evidence
- Failure/recovery rules
- Human escalation conditions

---

# 5. OpenCode / Coding-Agent Integration

The loop architecture does **not** require a special model.

A coding agent such as OpenCode can act as an execution engine while the surrounding orchestration layer determines:

- What task should run
- Which skill should be loaded
- Which model should be used
- Which tools are allowed
- Which agents run in parallel
- What evaluator runs afterward
- Whether to retry
- When to stop
- When to request human approval

Conceptually:

```text
                    ORCHESTRATOR
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
          Agent / Model         Agent / Model
              ↓                     ↓
            Skills               Skills
              ↓                     ↓
            Tools                Tools
              └──────────┬──────────┘
                         ↓
                     EVALUATOR
                         ↓
                    PASS / FAIL
                         ↓
                 Retry / Escalate / Done
```

The model is the **execution engine**.

The orchestration system is the **control system**.

---

# 6. Prompt Engineering's Actual Role

The claim "prompt engineering is completely dead" is misleading.

Prompting remains important, but it is no longer sufficient as the primary abstraction.

Old model:

`Prompt → Response`

Modern agentic model:

```text
Goal
 ↓
Instructions / Prompt
 ↓
Context + Skills + Knowledge
 ↓
Tool Use
 ↓
Execution
 ↓
Evaluation
 ↓
Retry / Route / Escalate
 ↓
Result
```

Therefore:

> Prompt engineering becomes a component of agent engineering.

The higher-level engineering concerns become:
- Goal specification
- Context management
- Skill selection
- Tool design
- Orchestration
- Evaluation
- State/memory
- Retry/recovery
- Permissions
- Cost/token management
- Observability
- Human oversight

---

# 7. Independent Evaluation

This is a foundational design principle.

Avoid:

`Agent → "I think I'm done" → Done`

Prefer:

```text
             WORKER
                ↓
             ARTIFACT
                ↓
          INDEPENDENT TEST
                ↓
            EVALUATOR
             /     \
          FAIL     PASS
           ↓         ↓
        RETRY       DONE
```

For software:

```text
Requirement
    ↓
Implementation
    ↓
Unit Tests
    ↓
Integration Tests
    ↓
Security Checks
    ↓
Acceptance Evaluation
    ↓
PASS → Review / Merge
FAIL → Return to Worker
```

Evaluation can combine deterministic and model-based checks.

Deterministic checks should be preferred wherever objective validation is possible.

---

# 8. Parallel Proactive Architecture

A proactive event can dispatch specialized agents concurrently.

```text
                       EVENT
                         ↓
                       ROUTER
             ┌───────────┼───────────┐
             ↓           ↓           ↓
          Agent A     Agent B     Agent C
             │           │           │
             └───────────┼───────────┘
                         ↓
                  REVIEW / SYNTHESIS
                         ↓
                       OUTPUT
```

Example for a pull request:

```text
PR Opened
   ↓
Router
   ├── Architecture Review
   ├── Code Review
   ├── Test Analysis
   ├── Security Review
   └── Documentation Review
             ↓
       Synthesis Agent
             ↓
       Final Evaluator
             ↓
       Human / Merge
```

Parallelism should be used when tasks are independent; dependent tasks should remain sequential.

---

# 9. Time-Based vs Event-Based

Do not automatically equate autonomy with frequent polling.

### Time-based

```text
Timer → Check → React → Wait
```

Useful when:
- No event trigger exists
- Periodic inspection is sufficient
- Scheduled delivery is required

### Event-based

```text
Event → React
```

Usually preferable when:
- External systems provide webhooks/events
- Immediate reaction matters
- Polling would waste tokens/compute

A mature system supports both.

---

# 10. Guardrails for Autonomous Loops

Autonomous loops introduce risks that simple prompting does not.

Every production loop should consider:

### Loop control
- Maximum iterations
- Timeouts
- Retry budgets
- Circuit breakers
- Stop conditions

### Evaluation
- Independent evaluator
- Objective tests
- Confidence thresholds
- Human escalation

### Security
- Least-privilege tools
- Sandboxing
- Approval gates
- Secret isolation
- Safe filesystem/repository boundaries

### Cost and token efficiency
- Context limits
- Model selection
- Skill loading only when needed
- Caching
- Parallelism where useful
- Early termination

### Reliability
- Persistent state
- Checkpoints
- Idempotent actions
- Failure recovery
- Observability/logging

### Multi-agent coordination
- Clear ownership
- Avoid duplicate work
- Dependency management
- Conflict resolution
- Final synthesis/review

---

# 11. Recommended Standard Loop Vocabulary

Use a small common vocabulary across the architecture:

| Primitive | Meaning |
|---|---|
| Goal | What outcome is required |
| Trigger | What starts the workflow |
| Agent | Who performs work |
| Skill | How the agent performs specialized work |
| Context | Information available to the agent |
| Tool | External capability available to the agent |
| Router | Decides where work goes |
| Worker | Executes the task |
| Evaluator | Determines whether the task succeeded |
| Retry | Re-executes after failure |
| State | Persistent workflow information |
| Escalation | Transfers control to a human/other agent |
| Done | Verified completion |

---

# 12. Recommended Architecture for Our Agent Platform

The preferred architecture is:

```text
                    PRODUCT GOAL
                         ↓
                 GOAL / ACCEPTANCE
                         ↓
                     TRIGGER
                         ↓
                   ORCHESTRATOR
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
            ROUTER              WORKFLOW
              ↓                     ↓
        Specialized Agents    Sequential/Graph
              ↓                     ↓
         Skills + Knowledge + Tools
              └──────────┬──────────┘
                         ↓
                    ARTIFACTS
                         ↓
                    EVALUATORS
                         ↓
                 ┌───────┴───────┐
                 ↓               ↓
               FAIL             PASS
                 ↓               ↓
             RETRY/REPAIR     REVIEW
                 ↓               ↓
                 └──────→      DONE
```

Supported execution modes:

1. **Turn-based** — human-in-the-loop
2. **Goal-based** — evaluator + retry
3. **Time-based** — scheduled inspection/action
4. **Event-based / proactive** — automatic routing + parallel agents

---

# 13. Key Takeaway

The valuable lesson from the Claude roadmap is not that Claude eliminates prompting.

The valuable lesson is:

> **Move from asking an AI for an answer to engineering a system that can pursue, evaluate, correct, and complete a goal.**

For our architecture, loop modes should therefore be treated as **standard orchestration primitives**.

The strongest general pattern is:

`Goal → Plan/Route → Execute → Evaluate → Retry/Escalate → Complete`

And for autonomous systems:

`Event → Route → Parallel Work → Evaluate → React → Continue`

This architecture is model-agnostic and can sit above OpenCode or other coding/agent execution systems.
