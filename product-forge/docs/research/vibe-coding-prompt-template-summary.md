# Vibe Coding Prompt Template — Summary & Architectural Takeaways

Repository: `KhazP/vibe-coding-prompt-template`

## Executive Summary

`vibe-coding-prompt-template` is a structured AI-assisted software-development workflow that turns a product idea into an executable project through staged artifacts, agent instructions, handoffs, planning, implementation, and verification.

Its strongest architectural ideas are:

1. A canonical `AGENTS.md` project contract.
2. Structured handoffs between workflow stages.
3. A Research → PRD → Tech Design → Build pipeline.
4. Plan → Execute → Verify loops.
5. Agent/tool adapters that keep the core workflow relatively tool-neutral.
6. Persistent project documentation and context rather than relying entirely on conversation history.

For our broader AI engineering system, it should be treated as a **reference implementation for the project execution layer**, not as the complete architecture.

---

## Core Workflow

The repository's workflow can be viewed as:

```text
Idea
  ↓
Research
  ↓
PRD
  ↓
Technical Design
  ↓
AGENTS.md / Project Contract
  ↓
Plan
  ↓
Execute
  ↓
Verify
  ↓
Fix / Iterate
  ↓
Ship
```

This provides a useful bridge between product intent and actual coding-agent execution.

---

## 1. Canonical AGENTS.md Contract

One of the most valuable ideas is maintaining a canonical `AGENTS.md`.

Instead of repeatedly putting a large system prompt into every agent session, the project maintains durable instructions and context covering areas such as:

- Project purpose
- Current state
- Architecture
- Coding conventions
- Constraints
- Development practices
- Verification requirements
- Roadmap
- Agent expectations
- Things agents should and should not do

### Why this matters

The project contract becomes a persistent source of truth.

```text
                AGENTS.md
                    │
        ┌───────────┼───────────┐
        ↓           ↓           ↓
     Planning    Coding       Review
       Agent      Agent        Agent
```

This is more robust than depending on conversation history.

---

## 2. Structured Artifacts

The workflow separates major pieces of knowledge into artifacts rather than keeping everything inside prompts.

Typical artifacts include:

- Research
- Product requirements
- Technical design
- Architecture decisions
- Agent instructions
- Implementation plans
- Verification results
- Handoff context

This is important because agents should consume **relevant artifacts**, rather than receiving the entire history of the project every time.

---

## 3. Handoff Context

A particularly useful pattern is structured context passed from one stage to another.

Instead of:

```text
Research Agent
    ↓
Huge conversation history
    ↓
PRD Agent
```

use:

```text
Research Agent
    ↓
Research Artifact
    +
Handoff Context
    ↓
PRD Agent
    ↓
PRD Artifact
    +
Handoff Context
    ↓
Architecture Agent
```

This reduces unnecessary context and makes the workflow easier to reproduce.

### Implication for our architecture

Handoffs should be treated as first-class artifacts containing things such as:

- What was discovered
- Decisions made
- Open questions
- Constraints
- Relevant evidence
- Required next actions
- Links to source artifacts

---

## 4. Plan → Execute → Verify

The repository emphasizes an iterative development loop rather than simply asking an agent to "build the application."

Basic form:

```text
PLAN
 ↓
EXECUTE
 ↓
VERIFY
```

For our system, this should be expanded:

```text
PLAN
 ↓
EXECUTE
 ↓
TEST
 ↓
EVALUATE
 ↓
REVIEW
 ↓
FIX
 ↓
VERIFY
 ↓
COMMIT / SHIP
```

A separate evaluator/reviewer is often preferable because a coding agent should not be the sole judge of whether its own work is correct.

---

## 5. Agent Skills and Commands

The repository includes reusable agent-oriented workflow components and commands.

The important architectural idea is to separate:

- reusable skills
- project-specific instructions
- workflow commands
- project artifacts

This supports composability.

A future system can therefore load only the skills required for a particular task instead of putting every possible instruction into every agent context.

---

## 6. Tool / Agent Adapters

A strong design principle is having a canonical project contract while allowing different coding agents and environments to consume it.

Conceptually:

```text
                 Canonical Project Contract
                         AGENTS.md
                            │
          ┌─────────────────┼─────────────────┐
          ↓                 ↓                 ↓
      Claude Code         Codex            Cursor
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ↓
                     Same project truth
```

This avoids making the entire engineering methodology dependent on one AI coding product.

For our architecture, the same principle should support:

- OpenCode
- Codex
- Claude Code
- Cursor
- Gemini / Antigravity
- Other future coding agents

---

# What We Should Borrow

## Highest Priority

### 1. Canonical AGENTS.md

Adopt this concept directly.

It should become the project's durable agent contract.

### 2. Structured Handoffs

Make handoff artifacts a standard part of every major workflow.

### 3. Plan → Execute → Verify

Make verification an explicit stage rather than an afterthought.

### 4. Tool-Neutral Core Contract

Keep project truth independent of the particular coding agent being used.

### 5. Persistent Project Context

Store important project state in files/artifacts rather than relying exclusively on chat history.

---

# What We Should Extend

The repository is primarily focused on AI-assisted/vibe-oriented software development.

Our broader architecture should go further.

## Target Architecture

```text
                         HUMAN GOAL
                             │
                             ↓
                       ORCHESTRATOR
                             │
                       TASK PLANNER
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
    Research             Product              Architecture
      Agent                Agent                  Agent
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ↓
                       Coding Agent(s)
                             │
                             ↓
                       Test / QA Agent
                             │
                             ↓
                       Evaluator Agent
                             │
                    ┌────────┴────────┐
                    ↓                 ↓
                  PASS              FAIL
                    │                 │
                    ↓                 ↓
                  SHIP              FIX
                                      │
                                      └──→ Execute
```

Underneath this should sit:

```text
Knowledge Base
      │
      ├── Skills
      ├── Engineering Knowledge
      ├── Course Knowledge
      ├── Repository Knowledge
      ├── Patterns
      └── References

Model / Resource Router
      │
      ├── Model selection
      ├── Cost optimization
      ├── Context optimization
      └── Task-specific routing
```

---

# Where This Repository Fits

The repository should be considered an **execution-layer reference**.

```text
┌─────────────────────────────────────────────┐
│        OUR AI ENGINEERING SYSTEM             │
├─────────────────────────────────────────────┤
│                                             │
│  Knowledge Layer                            │
│  Skills / Courses / Repos / Patterns        │
│                                             │
│  Orchestration Layer                        │
│  Planning / Routing / Multi-Agent Control   │
│                                             │
│  Project Contract Layer                     │
│  AGENTS.md / Requirements / Architecture    │
│                                             │
│  Execution Layer  ← this repository fits    │
│  Research → PRD → Design → Build → Verify   │
│                                             │
│  Evaluation Layer                           │
│  Tests / Review / Quality / Security        │
│                                             │
└─────────────────────────────────────────────┘
```

---

# What Not to Copy Wholesale

The repository should **not** become the entire architecture.

It does not by itself solve:

- General-purpose multi-agent orchestration
- Dynamic agent routing
- Model selection
- Token/context optimization
- Large-scale knowledge management
- Long-term organizational memory
- Advanced evaluation systems
- Security governance
- Autonomous production operations
- Comprehensive software supply-chain controls

Therefore:

> Use the repository's workflow and contract ideas as building blocks, not as the complete AI engineering operating system.

---

# Recommended Integration

For our system, create a project structure along these lines:

```text
project/
│
├── AGENTS.md
│
├── .agent/
│   ├── skills/
│   ├── workflows/
│   ├── adapters/
│   └── policies/
│
├── knowledge/
│   ├── project/
│   ├── engineering/
│   ├── repositories/
│   ├── courses/
│   └── patterns/
│
├── artifacts/
│   ├── research/
│   ├── prd/
│   ├── architecture/
│   ├── plans/
│   ├── handoffs/
│   └── verification/
│
├── src/
├── tests/
└── docs/
```

The exact directory layout can evolve, but the separation of **contract, skills, knowledge, artifacts, implementation, and verification** is the important principle.

---

# Key Design Principle

The most important lesson from this repository is:

> **Don't make the prompt the system. Make the project state and contracts the system.**

Prompts can change with models and tools.

A durable project contract, structured artifacts, skills, handoffs, tests, and verification results provide a much more stable foundation.

---

# Relationship to Our Agent Loop Architecture

This repository aligns strongly with the agent-loop approach discussed elsewhere.

A useful combined loop is:

```text
Goal
 ↓
Understand
 ↓
Research
 ↓
Specify
 ↓
Plan
 ↓
Implement
 ↓
Test
 ↓
Evaluate
 ↓
Review
 ↓
Fix
 ↓
Verify
 ↓
Update Project Knowledge
 ↓
Ship
```

The final step is important.

When an agent learns something important about the project, the result should be persisted into the appropriate artifact or knowledge layer instead of being lost when the session ends.

---

# Overall Assessment

| Area | Relevance |
|---|---|
| `AGENTS.md` contract | ★★★★★ |
| Structured workflow | ★★★★★ |
| Handoff context | ★★★★★ |
| Plan / Execute / Verify | ★★★★★ |
| Agent skills | ★★★★☆ |
| Tool adapters | ★★★★★ |
| Context continuity | ★★★★★ |
| CLI workflow | ★★★★☆ |
| Multi-agent orchestration | ★★★☆☆ |
| Knowledge architecture | ★★★☆☆ |
| Model/token optimization | ★★☆☆☆ |
| Complete autonomous engineering OS | ★★☆☆☆ |

## Bottom Line

`KhazP/vibe-coding-prompt-template` is worth keeping in our AI engineering reference set.

The most valuable concepts to incorporate are:

1. **Canonical `AGENTS.md`**
2. **Structured project artifacts**
3. **Explicit agent-to-agent handoffs**
4. **Plan → Execute → Verify loops**
5. **Persistent project context**
6. **Tool-neutral agent contracts**

Its role should be the **project execution/workflow layer** within a larger system that also provides knowledge, skills, orchestration, model routing, context optimization, evaluation, and long-term project memory.
