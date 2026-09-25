# AI Repositories — What We Actually Need

## Executive Summary

The 13 repositories in the source list are useful, but they should **not** be treated as 13 components that all need to be installed.

The stronger conclusion is that the current open-source agent ecosystem is converging around a small set of architectural primitives:

1. **Skills** — reusable, task-specific procedures and knowledge.
2. **Context / knowledge / memory** — mechanisms for loading the right information without bloating every prompt.
3. **Execution tools** — terminal, browser, APIs, files, databases, GitHub, etc.
4. **Orchestration** — graph/workflow/task routing across agents and tools.
5. **Evaluation + repair loops** — execute, verify, diagnose, fix, and retry.
6. **Long-running state** — persistent sessions, goals, checkpoints, and autonomous continuation.
7. **Security / permissions / sandboxing** — essential once agents can act autonomously.

For the proposed OpenCode-centered system, the recommended strategy is:

> **Adopt the concepts and selected components; do not assemble the system by stacking all 13 repositories together.**

The highest-value references are **Superpowers, Scientific Agent Skills, OpenViking, Prime Agent, and Everything Claude Code**. OpenHands, Browser Use, Hermes, OpenClaw, Codex, Claude Plugins, Archify, and Awesome Agent Skills are useful selectively or as reference implementations.

---

## 1. The Architectural Lesson from the 13 Repositories

A mature agent system should look approximately like this:

```text
                         USER GOAL
                            |
                            v
                    +----------------+
                    | Goal / Planner  |
                    +-------+--------+
                            |
                            v
                    +----------------+
                    |  Orchestrator  |
                    | graph / tasks  |
                    +-------+--------+
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
         Research         Build         Analyze
             |              |              |
             +--------------+--------------+
                            |
                            v
                    +----------------+
                    | Skill Registry |
                    +-------+--------+
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
         Knowledge       Memory        Resources
             |              |              |
             +--------------+--------------+
                            |
                            v
                    +----------------+
                    | Tool Execution |
                    +-------+--------+
                            |
                            v
                    +----------------+
                    |   Evaluator    |
                    | tests/evidence |
                    +-------+--------+
                            |
                       pass / fail
                         /       \
                       pass       fail
                        |          |
                        v          v
                      Output    Diagnose
                                   |
                                   v
                                 Repair
                                   |
                                   +-----> loop
```

This architecture is more important than any individual repository.

---

# 2. What Is Actually Needed

## A. Skill System — REQUIRED

A skill system should be a first-class architectural layer.

Examples:

```text
skills/
  software-engineering/
  system-design/
  testing/
  security/
  debugging/
  data-analysis/
  research/
  finance/
  product/
  architecture/
  domain-specific/
```

Each skill should ideally contain:

```text
SKILL.md
references/
scripts/
assets/
```

Only the information required for the current task should be loaded into context.

### Why this matters

The Scientific Agent Skills repository provides a strong concrete example: skills are narrow, separately packaged capabilities, with optional references and scripts. Its repository guidance explicitly keeps skills narrow and avoids turning the skill repository into a general orchestrator. citehttps://github.com/K-Dense-AI/scientific-agent-skills/blob/main/AGENTS.md

**Decision:** Build/adopt a skill registry. Do not copy every available skill into every project.

---

# 3. Development Methodology — HIGH PRIORITY

## Superpowers

**Verdict: Strongly adopt / study deeply.**

Superpowers is not just a collection of prompts. It packages a development methodology as composable skills and can be used with OpenCode. Its OpenCode integration registers its skills with OpenCode's native skill system, and its workflow emphasizes brainstorming/specification, planning, implementation, and testing instead of jumping directly into code. citehttps://github.com/obra/superpowershttps://github.com/obra/superpowers/blob/main/docs/README.opencode.md

### What we should take

- brainstorming / requirements refinement
- design before implementation
- implementation plans
- test-first / verification-oriented workflow
- explicit task decomposition
- composable skills
- OpenCode integration model

### What we should NOT do

Do not blindly make Superpowers the entire platform. Treat it as a **development workflow/skill layer** inside the larger architecture.

### Recommended status

**ADOPT / ADAPT**

---

# 4. Knowledge, Context and Memory — HIGH PRIORITY

## OpenViking

**Verdict: Study deeply; borrow the architectural ideas before deciding whether to run it directly.**

The important concept is the explicit separation and organization of context resources, memory, and skills for agents.

This directly matches the intended architecture:

```text
Skill     = what procedure to follow
Knowledge = what information is known
Memory    = what the agent/project learned or decided
Resource  = where the original source lives
Tool      = how an action is performed
```

### Recommended architecture

```text
                 CONTEXT LAYER
                       |
         +-------------+-------------+
         |             |             |
      Skills       Knowledge       Memory
         |             |             |
         +-------------+-------------+
                       |
                  Resources
                       |
                       v
                    Agent
```

### Recommended status

**ARCHITECTURE REFERENCE / POSSIBLE COMPONENT**

Do not automatically make it a mandatory dependency.

---

# 5. Scientific Agent Skills — HIGH PRIORITY

## Scientific Agent Skills

**Verdict: One of the best examples of scalable skill packaging.**

The repository organizes narrow scientific/research capabilities as individual skills and supports optional references and scripts. Examples include literature review, database lookup, experimental design, statistical analysis, and domain-specific tools. citehttps://github.com/K-Dense-AI/scientific-agent-skills/blob/main/docs/skills.mdhttps://github.com/K-Dense-AI/scientific-agent-skills/blob/main/AGENTS.md

### What we should take

- one narrow capability per skill
- optional reference material loaded on demand
- executable helpers where useful
- explicit operating rules
- provenance / evidence handling
- domain-specific skill packs
- tests outside the skill package

### Important implication for the earlier course/knowledge idea

Do **not** convert every course, book, or repository into one enormous prompt.

Use:

```text
External source
    -> extract useful methodology
    -> curate / validate
    -> package as skill + references
    -> load only when needed
```

### Recommended status

**ADOPT THE PATTERN; USE THE REPO AS A SOURCE OF EXAMPLES/SKILLS**

---

# 6. Long-Horizon Autonomous Loops — HIGH PRIORITY

## Prime Agent

**Verdict: Study deeply for autonomous execution architecture.**

Prime Agent's current long-running-agent documentation describes persistent workers, state, scheduled prompts, direct agent messaging, goals, and bounded autonomous continuation. citehttps://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/long-running-agents.md

This is directly relevant to the proposed loop architecture:

```text
Goal
  -> Plan
  -> Execute
  -> Observe evidence
  -> Evaluate
  -> Repair
  -> Continue
  -> Complete
```

### What we should take

- persistent task state
- resumable sessions
- bounded autonomous continuation
- explicit goals
- checkpoints
- worker/session separation
- stopping conditions

### Critical design rule

Autonomy should be **bounded**.

Avoid:

```text
agent -> agent -> agent -> agent -> ... forever
```

Prefer:

```text
Goal
+ budget
+ timeout
+ max iterations
+ success criteria
+ evaluator
+ stop conditions
```

### Recommended status

**ADOPT CONCEPTS; IMPLEMENT WITH OUR ORCHESTRATOR**

---

# 7. Everything Claude Code — MEDIUM/HIGH PRIORITY

## Everything Claude Code

**Verdict: Mine for practical patterns, don't make it a dependency.**

This category is useful because it packages skills, workflows, hooks, commands and practical coding-agent patterns.

### What to extract

- reusable engineering workflows
- hooks / automation ideas
- coding conventions
- verification patterns
- repository/project setup patterns
- practical skill examples

### What not to do

Do not assume Claude Code-specific mechanisms are the required architecture for OpenCode.

### Recommended status

**REFERENCE / SELECTIVE ADOPTION**

---

# 8. OpenHands — MEDIUM/HIGH PRIORITY

## OpenHands

**Verdict: Strong reference implementation for autonomous software engineering.**

Study it for:

- agent runtime
- task lifecycle
- tool execution
- sandboxing
- software-engineering task handling
- evaluation
- autonomous execution

### Do not automatically replace OpenCode with OpenHands

If OpenCode is the chosen execution environment, OpenHands is better treated as a source of architectural lessons unless a specific OpenHands capability is required.

### Recommended status

**REFERENCE IMPLEMENTATION**

---

# 9. Browser Use — REQUIRED ONLY WHEN BROWSER AUTOMATION IS NEEDED

## Browser Use

**Verdict: Tool capability, not the central agent architecture.**

It provides browser control so agents can interact with websites. citehttps://github.com/browser-use/browser-use

The preferred abstraction is:

```text
Agent
  |
  +-- terminal
  +-- browser
  +-- APIs
  +-- files
  +-- databases
  +-- GitHub
```

### Recommended status

**OPTIONAL TOOL LAYER**

Install/use when the product actually needs web interaction.

---

# 10. Hermes Agent — MEDIUM PRIORITY

## Hermes Agent

**Verdict: Useful reference for persistent personal-agent behavior.**

Study for:

- persistent memory
- skills
- tools
- autonomous workflows
- personal-agent UX

But these are architectural concerns that can also be implemented within our own platform.

### Recommended status

**REFERENCE / SELECTIVE ADOPTION**

---

# 11. OpenClaw — MEDIUM PRIORITY WITH SECURITY CAUTION

## OpenClaw

**Verdict: Interesting for personal-agent autonomy and cross-platform operation; not a foundation to copy wholesale.**

Study it for:

- persistent personal assistant model
- autonomous action
- integrations
- long-lived agent behavior
- human/agent interaction patterns

### Security lesson

Persistent agents with broad permissions dramatically expand the attack surface.

Therefore the platform should enforce:

```text
least privilege
sandboxing
secret isolation
approval gates
command allowlists
network controls
artifact logging
```

### Recommended status

**REFERENCE ONLY AT FIRST**

---

# 12. Codex — REFERENCE IMPLEMENTATION

## OpenAI Codex

**Verdict: Useful coding-agent implementation to study, but not necessary if OpenCode is the selected execution harness.**

Study for:

- coding-agent execution patterns
- terminal workflows
- repository work
- model/tool integration
- agent UX

### Recommended status

**REFERENCE IMPLEMENTATION**

Do not introduce another coding runtime simply because it is on the list.

---

# 13. Claude Plugins Official — SELECTIVE

## Anthropic Claude Plugins

**Verdict: Study the extension/plugin model; do not make Claude-specific plugins a platform dependency.**

Useful concepts:

- modular extensions
- packaged skills
- external integrations
- plugin lifecycle

Translate useful ideas into OpenCode-compatible components.

### Recommended status

**REFERENCE / PORT IDEAS**

---

# 14. Archify — NICHE

## Archify

**Verdict: Useful specialized skill, not foundational infrastructure.**

It fits naturally into an architecture/design skill pack:

```text
architecture/
  system-design/
  workflow-design/
  diagrams/
  archify-adapter/
```

### Recommended status

**OPTIONAL DOMAIN SKILL**

---

# 15. Awesome Agent Skills — DISCOVERY LAYER

## Awesome Agent Skills

**Verdict: Useful as a catalogue/discovery source, not a runtime dependency.**

Recommended flow:

```text
Skill catalogue
     |
     v
candidate skill
     |
security review
     |
quality review
     |
version pinning
     |
internal skill registry
```

### Important

Never install arbitrary skills automatically into a privileged agent environment. Skills can contain scripts, tool instructions, dependencies, or external calls.

### Recommended status

**DISCOVERY SOURCE**

---

# 16. Recommended Classification of All 13

| Repository | Classification | Recommendation |
|---|---|---|
| Superpowers | Development methodology + skills | **Adopt/adapt** |
| OpenViking | Context / memory / resources | **Study deeply** |
| Scientific Agent Skills | Skill ecosystem | **Adopt pattern** |
| Prime Agent | Long-horizon runtime | **Study deeply** |
| Everything Claude Code | Practical workflow library | **Mine selectively** |
| OpenHands | Autonomous SWE runtime | **Reference** |
| Browser Use | Browser tool | **Optional** |
| Hermes Agent | Personal autonomous agent | **Reference** |
| OpenClaw | Personal autonomous assistant | **Reference + security lessons** |
| Codex | Coding agent | **Reference** |
| Claude Plugins | Plugin ecosystem | **Reference / port ideas** |
| Archify | Architecture skill | **Optional** |
| Awesome Agent Skills | Skill catalogue | **Discovery** |

---

# 17. What We Should Actually Build

The proposed system should remain relatively small at the core.

## Core Platform

```text
1. OpenCode / coding-agent runtime
2. Skill registry
3. Context / knowledge manager
4. Memory store
5. Graph/task orchestrator
6. Tool registry
7. Evaluator / verifier
8. Loop controller
9. Security / permission layer
10. Observability / audit log
```

## Add-on capabilities

```text
Browser Use
Scientific skills
Finance skills
Research skills
Architecture skills
Domain-specific skills
External connectors
```

---

# 18. Proposed Skill Architecture

```text
.agent/

  skills/
    core/
      planning/
      verification/
      debugging/
      security/
      system-design/

    engineering/
      backend/
      frontend/
      testing/
      devops/
      databases/

    research/
      literature-review/
      source-validation/
      data-analysis/

    domain/
      finance/
      india-markets/
      policy/
      agriculture/

  knowledge/
    courses/
    books/
    github/
    standards/
    documentation/

  memory/
    project/
    user-decisions/
    learned-patterns/

  workflows/
    build/
    research/
    analysis/
    release/

  evaluators/
    tests/
    quality/
    security/
    evidence/
```

The key design principle is:

> **Skills are active procedures. Knowledge is supporting information. Memory is accumulated state. Resources point to source material.**

---

# 19. Relationship to Multi-Agent Architecture

These repositories do **not** imply that every task needs multiple agents.

Prefer:

```text
single agent + skills + tools + evaluator
```

before:

```text
5 agents + 10 messages + duplicated context
```

Use multiple agents when there is real parallelism or specialization:

```text
                 Orchestrator
                      |
          +-----------+-----------+
          |           |           |
      researcher   builder    reviewer
          |           |           |
          +-----------+-----------+
                      |
                   evaluator
```

The orchestration layer should decide when specialization produces enough value to justify the added complexity and token cost.

---

# 20. Relationship to Autonomous Loops

The 13 repos strengthen the case for the previously proposed loop architecture.

A robust loop should have:

```text
Goal
Success criteria
Budget
Plan
Execution
Evidence collection
Evaluation
Repair
Retry limit
Stop condition
Final report
```

Example:

```text
BUILD FEATURE
     |
     v
WRITE SPEC
     |
     v
PLAN
     |
     v
IMPLEMENT
     |
     v
RUN TESTS
     |
  PASS? -------- NO --------+
     |                       |
    YES                  DIAGNOSE
     |                       |
     v                     REPAIR
  REVIEW                     |
     |                       |
     +-----------------------+
             |
          RECHECK
             |
           DONE
```

This is more important than adding more agents.

---

# 21. Knowledge / Course Integration

The repositories also support the earlier approach to long-form learning material.

Do not make the agent repeatedly read the full course every time.

Instead:

```text
Course / Book / Documentation
           |
           v
      Ingestion
           |
           v
    Structured notes
           |
           v
  Extract reusable methods
           |
           v
     Skill + references
           |
           v
      Skill registry
```

Large source documents can remain as references and be loaded only when needed.

Promote material into a local skill only when it is:

- reusable
- sufficiently validated
- stable enough to operationalize
- beneficial to many future tasks

---

# 22. Security Requirements

This part should be treated as mandatory rather than optional.

Every skill/tool/plugin should have metadata such as:

```yaml
name: example-skill
description: ...
version: ...
source: ...
risk_level: low|medium|high
allowed_tools:
  - read
  - bash
network_access: false
requires_secrets: false
requires_approval: false
```

For high-risk actions:

```text
Agent proposes action
       |
       v
Policy check
       |
  +----+----+
  |         |
allow     approval
  |         |
  v         v
execute   human gate
```

---

# 23. What NOT to Build

Avoid these unnecessary directions:

### 1. Do not install all 13 repos

Most are overlapping reference implementations or specialized components.

### 2. Do not create an agent for every skill

A skill is usually a capability loaded by an agent, not a separate agent.

### 3. Do not store all knowledge in the system prompt

Use retrieval and skill loading.

### 4. Do not create an elaborate multi-agent graph for trivial tasks

A single agent can execute many workflows well.

### 5. Do not run untrusted plugins/skills with unrestricted permissions

Everything executable needs provenance, review, and policy controls.

### 6. Do not duplicate context across agents unnecessarily

Context sharing should be deliberate and minimal.

---

# 24. Final Recommendation

## Keep

**Core ideas worth incorporating into the architecture:**

- Superpowers-style development methodology
- Scientific Agent Skills-style skill packaging
- OpenViking-style context/memory/resource separation
- Prime Agent-style long-running bounded execution
- evaluator-driven repair loops
- tool abstraction (terminal/browser/API/etc.)
- explicit security and permission controls

## Optional

- Browser Use for browser automation
- scientific skills for research workflows
- Archify for architecture diagrams
- other domain-specific skill packs

## Reference only

- OpenHands
- Hermes Agent
- OpenClaw
- Codex
- Claude Plugins
- Everything Claude Code
- Awesome Agent Skills

These are useful for extracting ideas, not requirements for the core platform.

---

# 25. Recommended Target Architecture

```text
                         USER
                          |
                          v
                 +------------------+
                 | Goal / Intent    |
                 +--------+---------+
                          |
                          v
                 +------------------+
                 | Task Orchestrator |
                 | graph / workflow  |
                 +--------+---------+
                          |
           +--------------+--------------+
           |              |              |
           v              v              v
      Researcher       Builder        Reviewer
       (optional)       Agent          (optional)
           |              |              |
           +--------------+--------------+
                          |
                          v
                 +------------------+
                 | Skill Registry   |
                 +--------+---------+
                          |
                 +--------+---------+
                 | Context Engine   |
                 |                  |
                 | skills           |
                 | knowledge        |
                 | memory           |
                 | resources        |
                 +--------+---------+
                          |
                          v
                 +------------------+
                 | Tool Registry     |
                 | terminal/browser  |
                 | APIs/files/GitHub |
                 +--------+---------+
                          |
                          v
                 +------------------+
                 | Evaluator         |
                 | tests/evidence    |
                 | quality/security  |
                 +--------+---------+
                          |
                    pass / fail
                     /       \
                    v         v
                 OUTPUT     REPAIR
                              |
                              +----> LOOP
```

## Bottom line

The list is useful, but the value is **architectural, not cumulative**.

We do not need 13 separate systems.

We need a small platform with:

> **OpenCode + Skills + Context/Knowledge/Memory + Tools + Orchestration + Evaluator + Bounded Autonomous Loops + Security**

The 13 repositories should be treated as a **research/reference pool from which to select proven patterns and components**.

That keeps the platform modular, avoids unnecessary duplication, reduces context/token waste, and leaves room to add specialized skills later without redesigning the core.
