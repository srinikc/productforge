# Multi-Agent System — Lessons to Leverage from 7 Open-Source AI Projects

## Purpose

This document extracts the **architectural ideas worth leveraging** from:

1. DeepTutor
2. OpenViking
3. Headroom
4. AI Hedge Fund
5. Khoj
6. Letta
7. Open WebUI

The goal is **not** to adopt all seven repositories as dependencies. Instead, use them as reference implementations and design inspiration for a robust multi-agent engineering system.

---

## Executive Summary

The strongest ideas from these projects cluster into five layers:

```text
Human / UI
    ↓
Multi-Agent Orchestration
    ↓
State + Memory
    ↓
Knowledge + Skills + Retrieval
    ↓
Context Optimization
    ↓
LLM / Model Layer
```

The most important projects to study deeply are:

- **OpenViking** → context, memory, skills, hierarchical retrieval
- **Letta** → persistent/stateful agents and memory
- **Headroom** → context/token optimization

Study these for multi-agent orchestration patterns:

- **DeepTutor** → research, planning, specialist agents, verification
- **AI Hedge Fund** → role specialization, independent perspectives, synthesis

Use these mainly as product/integration references:

- **Khoj** → personal knowledge and agentic retrieval
- **Open WebUI** → human-facing AI interface and model access

---

# 1. Core Architectural Principle

Do **not** build a multi-agent system as:

```text
User
  ↓
Agent 1
Agent 2
Agent 3
Agent 4
```

Simply adding more agents does not automatically make a system better.

Instead, build a system where agents have:

- clear responsibilities
- specialized skills
- controlled access to knowledge
- persistent state when necessary
- explicit communication contracts
- verification/evaluation
- bounded context
- an orchestrator that decides which agents should run

A useful conceptual model is:

```text
                         USER
                           │
                           ▼
                    ┌─────────────┐
                    │ ORCHESTRATOR│
                    └──────┬──────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        SPECIALIST A  SPECIALIST B  SPECIALIST C
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                     ┌───────────┐
                     │ SYNTHESIS │
                     └─────┬─────┘
                           ▼
                     ┌───────────┐
                     │ EVALUATOR │
                     └─────┬─────┘
                           ▼
                         RESULT
```

---

# 2. OpenViking — Highest-Priority Architecture Reference

## What to leverage

OpenViking is particularly relevant because it treats agent context as a structured system involving:

- resources
- memory
- skills
- hierarchical context
- retrieval
- session/context management

The important lesson is that **the agent should not receive the entire knowledge base every time**.

Instead:

```text
Agent Need
    ↓
Context Manager
    ↓
Relevant Resource / Memory / Skill
    ↓
Retrieve appropriate level of detail
    ↓
Construct context
    ↓
LLM
```

## Apply to our architecture

Separate:

### Knowledge

What the system knows.

Examples:

- documentation
- books
- courses
- engineering standards
- architecture references
- GitHub repositories
- company knowledge

### Skills

What the agent knows how to do.

Examples:

- software design
- debugging
- testing
- security review
- research
- database design
- code review

### Memory

What happened previously.

Examples:

- decisions
- previous task results
- failed approaches
- user/project preferences
- discovered facts
- agent state

### Context

What the agent actually needs **right now**.

This distinction is fundamental.

---

# 3. Letta — Stateful Agent + Persistent Memory

## What to leverage

The key idea is that an agent should not necessarily start from zero on every interaction.

A stateful agent can maintain:

```text
Agent State
├── identity / role
├── working memory
├── long-term memory
├── previous decisions
├── learned information
└── active task state
```

## Important design principle

Do not put everything into memory.

Memory should be selectively written and retrieved.

Use categories such as:

```text
Short-Term / Working Memory
    ↓
Current task

Episodic Memory
    ↓
What happened previously

Semantic Memory
    ↓
Facts learned

Procedural Knowledge
    ↓
Skills / methods
```

For a multi-agent system, memory should also have **ownership boundaries**.

For example:

```text
Global Project Memory
        │
        ├── Research Agent Memory
        ├── Coding Agent Memory
        ├── Security Agent Memory
        └── QA Agent Memory
```

Agents can share selected project knowledge without exposing every internal state to every other agent.

---

# 4. Headroom — Context Optimization Layer

## What to leverage

Context is a limited resource.

The system should optimize context before sending it to the model.

Instead of:

```text
Retrieve 100,000 tokens
        ↓
Send everything to LLM
```

use:

```text
Retrieve
   ↓
Rank
   ↓
Filter
   ↓
Compress / summarize
   ↓
Remove redundancy
   ↓
Construct task-specific context
   ↓
LLM
```

## Architectural implication

Create a dedicated:

**Context Optimizer / Context Compiler**

Possible responsibilities:

- deduplicate results
- remove irrelevant tool output
- summarize large documents
- retain critical details
- prioritize recent state
- preserve citations/provenance
- enforce context budgets
- select the appropriate model/context level

This should be a first-class system component, not an afterthought.

---

# 5. DeepTutor — Multi-Agent Workflow Patterns

## What to leverage

DeepTutor is useful primarily as a reference for multi-agent workflows involving:

- planning
- research
- retrieval
- specialist reasoning
- iterative refinement
- verification
- user feedback

The key lesson is:

> Multi-agent systems should behave like workflows, not collections of independent chatbots.

A useful pattern:

```text
TASK
 ↓
PLANNER
 ↓
RESEARCH / SPECIALIST AGENTS
 ↓
EVIDENCE COLLECTION
 ↓
SYNTHESIZER
 ↓
EVALUATOR
 ↓
REVISION LOOP
 ↓
FINAL RESULT
```

## Important

Agents should have explicit roles.

Bad:

```text
Agent 1
Agent 2
Agent 3
```

Better:

```text
Planner
Researcher
Implementer
Reviewer
Security Analyst
Tester
Evaluator
Synthesizer
```

---

# 6. AI Hedge Fund — Specialist Perspective Pattern

## What to leverage

The interesting idea is **independent specialist perspectives**.

Different agents can analyze the same problem using different objectives or expertise.

For example:

```text
                   TASK
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
 Architecture     Security       Cost
 Agent             Agent          Agent
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                 SYNTHESIZER
                     │
                     ▼
                 EVALUATOR
```

This is useful when:

- the problem has competing trade-offs
- independent analysis reduces blind spots
- adversarial review is useful
- multiple technical domains are involved

Do not use multiple agents merely for the sake of using multiple agents.

---

# 7. Khoj — Knowledge + Personal AI Pattern

## What to leverage

Khoj demonstrates the value of combining:

```text
Documents
   +
Search
   +
Retrieval
   +
Reasoning
   +
Agents
   +
User interaction
```

For our system, this supports the idea of a persistent **AI knowledge layer**.

The knowledge base should be able to contain:

```text
/books
/courses
/github
/docs
/architecture
/research
/company
/project
```

But the agent should retrieve from this dynamically rather than loading everything.

---

# 8. Open WebUI — Human Control Plane

Open WebUI is less important to the core agent architecture.

Its main value is as a reference for the **human-facing layer**.

Conceptually:

```text
                 HUMAN
                   │
                   ▼
              AI INTERFACE
                   │
                   ▼
             AGENT PLATFORM
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
      Agents     Tools     Knowledge
```

Treat UI separately from the intelligence/orchestration layer.

This allows the same agent system to be accessed through:

- web UI
- CLI
- API
- IDE
- automation
- other applications

---

# 9. Recommended Multi-Agent Architecture

Combining the strongest ideas:

```text
┌───────────────────────────────────────────────────────┐
│                    HUMAN / CLIENT                     │
│             UI / CLI / API / IDE / Automation         │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                       │
│                                                       │
│  task decomposition • routing • dependencies         │
│  agent selection • parallelism • retry • escalation   │
└──────────────────────────┬────────────────────────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        Research       Engineering     Evaluation
          Agent           Agent           Agent
             │             │             │
             └─────────────┼─────────────┘
                           ▼
┌───────────────────────────────────────────────────────┐
│                 SHARED CONTEXT LAYER                  │
│                                                       │
│ Knowledge │ Memory │ Skills │ Project State │ Tools  │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│                 CONTEXT OPTIMIZER                     │
│                                                       │
│ retrieve → rank → filter → compress → compile         │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│                    MODEL LAYER                        │
│                                                       │
│ GPT │ Claude │ Gemini │ Qwen │ local models           │
└───────────────────────────────────────────────────────┘
```

---

# 10. Agent Communication

Do not allow arbitrary agent-to-agent conversation to become the architecture.

Prefer structured messages.

Example:

```yaml
task:
  id: TASK-123

from: architecture-agent
to: security-agent

objective:
  Review proposed architecture for security risks.

context:
  architecture_version: v4
  relevant_documents:
    - security-guidelines
    - system-design

deliverables:
  - vulnerabilities
  - severity
  - mitigations
  - unresolved_questions
```

This makes agents:

- observable
- testable
- replaceable
- debuggable
- easier to evaluate

---

# 11. Orchestration Patterns to Support

The system should support several patterns rather than one fixed topology.

## Sequential

```text
A → B → C → D
```

Use when each step depends on the previous step.

## Parallel

```text
       ┌→ A ─┐
Task ──┼→ B ─┼→ Synthesizer
       └→ C ─┘
```

Use when independent analysis can happen concurrently.

## Supervisor

```text
             Supervisor
            /    |                A     B      C
```

Use when one agent coordinates specialists.

## Debate / Adversarial Review

```text
Proposal
   ↓
Proponent
   ↓
Critic
   ↓
Reviser
   ↓
Evaluator
```

Useful for architecture, code, research and high-risk decisions.

## Evaluator Loop

```text
Generate
   ↓
Evaluate
   ↓
Fail? ──Yes──→ Revise
   │
   No
   ↓
Return
```

This is particularly important for autonomous coding.

---

# 12. Skills Architecture

Skills should be independently loadable.

Example:

```text
skills/
├── software-engineering/
├── system-design/
├── testing/
├── security/
├── databases/
├── devops/
├── research/
├── data-analysis/
└── product/
```

Each skill should contain:

```text
skill/
├── instructions
├── methodology
├── examples
├── checklists
├── tools
├── references
└── evaluation criteria
```

Agents should load only the skills required for their current task.

---

# 13. Knowledge Base Architecture

Avoid making the entire knowledge base part of the prompt.

Use progressive disclosure:

```text
L0 — Metadata
     ↓
L1 — Summary / index
     ↓
L2 — Relevant section
     ↓
L3 — Full source
```

This is one of the most important ideas to carry forward from the OpenViking-style approach.

For example:

```text
Agent asks:
"How should we design our event system?"

        ↓

Knowledge search

        ↓

Find:
System Design
Kafka documentation
Internal architecture
Relevant prior decisions

        ↓

Load summaries first

        ↓

Retrieve only relevant sections

        ↓

Context optimizer

        ↓

Agent
```

---

# 14. Memory Architecture

Recommended structure:

```text
memory/
├── global/
│   └── project-facts
├── task/
│   └── current-task-state
├── episodic/
│   └── previous-events
├── semantic/
│   └── learned-facts
├── decisions/
│   └── architecture-decisions
└── agent/
    ├── research-agent
    ├── coding-agent
    └── review-agent
```

Important rule:

**Memory must be curated.**

Do not automatically store every conversation or every model output.

Use:

```text
Candidate memory
      ↓
Importance
      ↓
Deduplication
      ↓
Validation
      ↓
Persist
```

---

# 15. Evaluation Is a First-Class Agent Capability

One of the strongest combined lessons is that generation alone is insufficient.

The system needs independent evaluation.

```text
                TASK
                  │
                  ▼
              Generator
                  │
                  ▼
               Output
                  │
                  ▼
              Evaluator
             /                   PASS          FAIL
           │             │
           ▼             ▼
         Return        Revision
                         │
                         └──────→ Evaluator
```

Evaluation can include:

- correctness
- tests
- security
- factual grounding
- requirements coverage
- architecture consistency
- performance
- cost
- style
- user-defined success criteria

---

# 16. What NOT to Copy

Do not turn this research into:

```text
Install OpenViking
Install Letta
Install Khoj
Install Headroom
Install DeepTutor
Install AI Hedge Fund
Install Open WebUI
```

and assume the system is solved.

That creates unnecessary coupling.

Instead:

```text
Study → Extract Pattern → Implement Minimal Version → Measure
```

Only adopt a dependency when it provides a capability that is genuinely better than the internal implementation.

---

# 17. Priority Matrix

| Project | Study | Adopt Directly | Main Lesson |
|---|---:|---:|---|
| OpenViking | ★★★★★ | Maybe | Context + memory + skills |
| Letta | ★★★★★ | Maybe | Stateful agents + memory |
| Headroom | ★★★★★ | Maybe | Context optimization |
| DeepTutor | ★★★★☆ | Maybe | Multi-agent workflows |
| AI Hedge Fund | ★★★★☆ | Usually no | Specialist perspectives |
| Khoj | ★★★☆☆ | Maybe | Knowledge + personal AI |
| Open WebUI | ★★★☆☆ | Optional | Human-facing interface |

---

# 18. Final Design Principles

The multi-agent system should follow these principles:

### 1. Fewer, better agents

Do not create agents unless specialization provides measurable value.

### 2. Explicit roles

Every agent should have a clear responsibility.

### 3. Shared knowledge, controlled memory

Agents should be able to access common project knowledge while retaining appropriate private state.

### 4. Dynamic context

Retrieve context based on the current task.

### 5. Progressive disclosure

Load summaries first; retrieve deeper content only when necessary.

### 6. Context optimization

Treat tokens/context as an engineering resource.

### 7. Structured communication

Use typed/structured task messages instead of uncontrolled agent conversations.

### 8. Independent evaluation

Every important autonomous workflow should have a verification stage.

### 9. Observable execution

Record:

- agent selected
- task
- inputs
- retrieved knowledge
- skills loaded
- tools used
- outputs
- evaluation
- retries
- final decision

### 10. Model independence

Agents should not be tightly coupled to one model provider.

```text
Agent
  ↓
Model Router
  ↓
┌─────────┬─────────┬─────────┐
GPT      Claude    Gemini    Local
```

### 11. Knowledge ≠ Skills ≠ Memory ≠ Context

Keep these as distinct concepts even if they share infrastructure.

### 12. Orchestration should be adaptive

The orchestrator should decide whether a task needs:

- one agent
- sequential agents
- parallel specialists
- debate
- evaluator loop
- human approval

---

# 19. The Core Architecture to Carry Forward

The most useful synthesis from these repositories is:

```text
                         USER
                           │
                           ▼
                    TASK / INTENT
                           │
                           ▼
                    ┌─────────────┐
                    │ ORCHESTRATOR│
                    └──────┬──────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          Planner       Specialists    Evaluator
             │             │
             │       ┌─────┼─────┐
             │       ▼     ▼     ▼
             │    Research Code Security
             │       │     │     │
             └───────┴─────┴─────┘
                           │
                           ▼
                  KNOWLEDGE / MEMORY
                           │
                     ┌─────┴─────┐
                     │           │
                 Knowledge     Skills
                     │           │
                     └─────┬─────┘
                           │
                           ▼
                  CONTEXT OPTIMIZER
                           │
                           ▼
                         MODEL
                           │
                           ▼
                      EVALUATOR
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
               PASS                 FAIL
                 │                   │
                 ▼                   ▼
               RESULT             REVISE
                                     │
                                     └──→ EVALUATOR
```

## Bottom Line

The biggest takeaway from this list is not any individual repository.

It is the emergence of a **context-centric, stateful, evaluatable multi-agent architecture**:

**Agents + Orchestration + Skills + Knowledge + Memory + Context Optimization + Evaluation.**

If building our system from scratch, prioritize the architecture in this order:

1. **Agent contracts and orchestration**
2. **Knowledge / skills separation**
3. **Persistent and structured memory**
4. **Dynamic retrieval**
5. **Context optimization**
6. **Specialist-agent workflows**
7. **Evaluator / verification loops**
8. **Observability**
9. **Model routing**
10. **Human control plane**

The repositories should serve as **reference implementations for these primitives**, not as a collection of mandatory dependencies.
