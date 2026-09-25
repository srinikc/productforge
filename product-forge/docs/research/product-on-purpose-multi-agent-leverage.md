# Product on Purpose — What We Should Leverage for Our Multi-Agent System

## Executive summary

Product on Purpose is best viewed as a **reference architecture for turning expert methodology into reusable, composable, testable agent skills**.

The most valuable lesson for our multi-agent system is not to copy all of its PM skills. It is to adopt its **skill engineering model**:

> **Skill = explicit procedure + inputs + output contract + examples + quality checks + metadata + versioning**

The ecosystem currently includes `pm-skills`, `thinking-framework-skills`, `agent-skills-toolkit`, `writing-style-catalog`, `product-lifecycle-templates`, and a plugin distribution layer. `pm-skills` contains 68 product-management skills, while `thinking-framework-skills` contains 63 evidence-graded reasoning skills, 4 meta-tools, and 9 recipes. The organization describes these as composable capabilities for general-purpose AI agents.

## 1. What we should take from it

### A. Treat skills as first-class system components

Do not build one giant system prompt containing all expertise.

Instead:

```text
Agent
  |
  +-- discover relevant skills
  |
  +-- load only required skills
  |
  +-- execute procedure
  |
  +-- produce typed artifact
  |
  +-- validate artifact
  |
  +-- hand off to next agent/skill
```

This reduces prompt bloat and makes capabilities independently versionable and testable.

### B. Use a standard Skill Contract

Every skill in our system should have a predictable structure:

```text
skill-name/
├── SKILL.md
├── references/
│   ├── TEMPLATE.md
│   └── EXAMPLE.md
├── metadata/
│   └── skill.meta.yml
├── tests/
└── scripts/                 # optional
```

Recommended `SKILL.md` sections:

1. Frontmatter / metadata
2. Purpose / overview
3. When to use
4. Inputs and prerequisites
5. Procedure
6. Output format / contract
7. Quality checklist
8. Examples
9. Failure modes / when NOT to use

This closely follows the useful anatomy demonstrated by Product on Purpose.

## 2. Build a Skill Registry

Create a central machine-readable registry:

```yaml
skill:
  id: product.problem-framing
  name: Problem Framing
  version: 1.0.0
  domain: product
  category: reasoning
  description: Reframe an ambiguous product problem before solution design.

  inputs:
    - problem_statement
    - context
    - evidence

  outputs:
    - problem_definition
    - assumptions
    - success_criteria

  dependencies:
    - reasoning.problem-restatement

  quality:
    required_checks:
      - assumptions_explicit
      - evidence_separated
      - output_complete

  routing:
    use_when:
      - ambiguous_problem
      - unclear_customer_need
```

The registry becomes the foundation for **skill discovery, routing, dependency resolution, versioning and evaluation**.

## 3. Separate reasoning skills from execution skills

This is one of the strongest architectural ideas in Product on Purpose.

Use two major classes:

### Reasoning layer

Examples:

- problem restatement
- first principles
- premortem
- assumption mapping
- scenario analysis
- alternative generation
- argument mapping
- perspective review
- decision matrices

### Execution/domain layer

Examples:

- PRD creation
- user research
- architecture design
- coding
- testing
- security review
- deployment
- analytics
- customer support

Architecture:

```text
                 ORCHESTRATOR
                      |
            +---------+---------+
            |                   |
       REASONING             EXECUTION
         SKILLS                SKILLS
            |                   |
       decide HOW            perform WHAT
            |                   |
            +---------+---------+
                      |
                   ARTIFACT
```

`thinking-framework-skills` explicitly separates reasoning from PM execution: reasoning helps decide what to work on and why; PM skills help execute how.

We should generalize this beyond product management.

## 4. Make every skill artifact-producing

Avoid skills whose only output is a paragraph of generic advice.

Prefer:

```text
premortem
    ↓
Risk Register

decision analysis
    ↓
Option Matrix

research
    ↓
Evidence Table

architecture review
    ↓
Architecture Decision Record

security review
    ↓
Threat/Risk Register

coding
    ↓
Code + Tests + Verification Report
```

Artifacts should become inputs to subsequent agents.

This creates an **artifact-driven multi-agent workflow** rather than a conversation-driven workflow.

## 5. Compose skills into workflows

Product on Purpose uses workflows/recipes to chain skills.

We should implement the same pattern:

```text
Workflow: Build Feature

1. problem-framing
2. customer-evidence
3. assumption-analysis
4. premortem
5. requirements
6. architecture
7. implementation
8. tests
9. security-review
10. evaluation
11. release-readiness
```

Each stage should consume the previous stage's artifact rather than reconstructing context from scratch.

```text
Problem Brief
      ↓
Evidence Pack
      ↓
Decision Pack
      ↓
PRD
      ↓
Architecture Spec
      ↓
Implementation Plan
      ↓
Code
      ↓
Verification Report
      ↓
Release Decision
```

## 6. Add a Skill Router

The `Framework Advisor` concept is especially valuable.

Instead of hard-coding every workflow:

```text
User goal
   ↓
Skill/Framework Router
   ↓
recommended skills
   ↓
ordered execution plan
   ↓
agents execute
```

The router should answer:

- What skill is appropriate?
- What should run first?
- What should NOT run?
- What evidence/context is required?
- Which skills can run in parallel?
- What artifact should be passed forward?

This becomes the **cognitive routing layer** of our multi-agent system.

## 7. Build quality gates into the skill system

This may be the most important contribution from `agent-skills-toolkit`.

Do not trust a skill because its prompt looks good.

Every skill should be evaluated against a standard.

Suggested quality levels:

### Bronze
- valid structure
- clear purpose
- usable instructions
- defined output

### Silver
- examples
- explicit failure modes
- quality checklist
- metadata
- deterministic validation

### Gold
- automated conformance checks
- evaluation cases
- versioning
- dependency metadata
- cross-agent compatibility
- self-validation in CI
- measurable output quality

Architecture:

```text
New Skill
   ↓
Schema Validation
   ↓
Conformance Checks
   ↓
Example Tests
   ↓
Behavior Evaluation
   ↓
Quality Grade
   ↓
Approved Skill Registry
```

This prevents our knowledge base from turning into a collection of untested prompts.

## 8. Evidence-grade knowledge

`thinking-framework-skills` has another important idea: **do not treat every methodology as equally reliable**.

For our knowledge/skills system, add provenance:

```yaml
evidence:
  grade: S-M
  sources:
    - ...
  confidence: high
  last_reviewed: 2026-09-01
  caveats:
    - ...
```

Useful categories:

```text
Research-backed
Practitioner-supported
Observed pattern
Heuristic
Experimental
Contested
```

The agent should know not only *what* a skill says, but **how strongly we should trust it**.

## 9. Explicitly encode when NOT to use a skill

A surprisingly important pattern is:

```text
When to use
When NOT to use
```

Example:

```yaml
use_when:
  - major architectural decision
  - competing viable approaches

do_not_use_when:
  - implementation is already constrained
  - decision is reversible and low-cost
```

This reduces cargo-cult application of frameworks.

Our router should use these constraints when selecting skills.

## 10. Cross-agent compatibility

Product on Purpose intentionally targets multiple agent environments rather than coupling everything to one agent.

We should make our skill library portable:

```text
                 Skill Standard
                       |
       +---------------+---------------+
       |               |               |
    Claude           Codex          Other Agents
       |               |               |
       +---------------+---------------+
                       |
                Shared Skill Files
```

The **skill definition should be independent of the orchestration runtime**.

Runtime-specific adapters should sit outside the skill itself.

## 11. Use metadata for discovery

Every skill should expose metadata such as:

```yaml
id:
domain:
category:
version:
description:
inputs:
outputs:
dependencies:
compatible_agents:
use_when:
avoid_when:
evidence:
risk:
cost:
latency:
parallelizable:
produces_artifact:
```

This allows an orchestrator to reason about the skill library programmatically.

## 12. Skill dependencies and composability

Skills should declare relationships:

```text
problem-framing
      ↓
assumption-analysis
      ↓
research-plan
      ↓
evidence-analysis
      ↓
decision-analysis
```

But dependencies should not become rigid chains.

The orchestrator should be able to construct a graph:

```text
              problem
                 |
       +---------+---------+
       |                   |
   research             premortem
       |                   |
       +---------+---------+
                 |
             decision
                 |
        +--------+--------+
        |                 |
       PRD           architecture
        |                 |
        +--------+--------+
                 |
              build
```

Independent branches can run in parallel.

## 13. Multi-agent roles we should derive

A useful initial agent topology:

```text
                         MASTER ORCHESTRATOR
                                  |
        +-------------------------+-------------------------+
        |                         |                         |
   PRODUCT AGENT             REASONING AGENT          RESEARCH AGENT
        |                         |                         |
   PM skills               thinking skills             evidence
        |                         |                         |
        +-------------------------+-------------------------+
                                  |
                           DECISION ARTIFACT
                                  |
                    +-------------+-------------+
                    |                           |
              ARCHITECT AGENT              BUILD AGENT
                    |                           |
             system design                 coding
             security                       testing
                    |                           |
                    +-------------+-------------+
                                  |
                           EVALUATION AGENT
                                  |
                         quality / verification
                                  |
                           RELEASE AGENT
```

The exact number of agents should remain small. **Skills should provide most specialization; agents should provide ownership, context and execution boundaries.**

## 14. Do not create one agent per skill

This is a key architectural conclusion.

Bad:

```text
68 PM skills = 68 agents
63 reasoning skills = 63 agents
```

Better:

```text
5–10 specialized agents
+
hundreds of reusable skills
+
dynamic skill routing
```

For example:

```text
Product Agent
    ├── PRD skill
    ├── hypothesis skill
    ├── user-story skill
    └── discovery skills

Reasoning Agent
    ├── premortem
    ├── first-principles
    ├── assumption analysis
    └── decision matrix
```

Agents become **workers with context and authority**; skills become **portable expertise**.

## 15. Build a critique/evaluation loop

The Product on Purpose ecosystem also points toward a useful separation:

```text
Producer Agent
      ↓
Artifact
      ↓
Critic / Evaluator
      ↓
Issues
      ↓
Producer revises
      ↓
Evaluator
      ↓
PASS
```

We should make this a standard system primitive.

Example:

```text
Architecture Agent
        ↓
Architecture Spec
        ↓
Architecture Critic
        ↓
Security Critic
        ↓
Cost Critic
        ↓
Revision
```

This is much more reliable than asking one agent to "check its own work."

## 16. Templates should be governed artifacts

The `product-lifecycle-templates` idea should also be adopted.

Templates should not be empty documents.

Each should contain:

```text
Template
+ instructions
+ metadata
+ example
+ quality gates
+ required fields
+ provenance
```

For our system:

```text
PRD
Architecture Spec
ADR
Threat Model
Research Report
Test Plan
Evaluation Report
Release Checklist
```

should all have machine-readable schemas.

## 17. Recommended architecture for our system

Combine the lessons into:

```text
                         USER / GOAL
                              |
                              ↓
                     ORCHESTRATOR
                              |
                 +------------+------------+
                 |                         |
          CONTEXT ENGINE              SKILL ROUTER
                 |                         |
        memory / knowledge         selects capabilities
                 |                         |
                 +------------+------------+
                              |
                         WORKFLOW GRAPH
                              |
          +-------------------+-------------------+
          |                   |                   |
       PRODUCT             REASONING           RESEARCH
        AGENT               AGENT               AGENT
          |                   |                   |
       skills              skills              skills
          |                   |                   |
          +-------------------+-------------------+
                              |
                           ARTIFACT
                              |
                         CRITIC LAYER
                              |
                    +---------+---------+
                    |                   |
                evaluator          validators
                    |                   |
                    +---------+---------+
                              |
                          REVISION
                              |
                           APPROVAL
                              |
                         FINAL OUTPUT
```

## 18. Proposed repository structure

```text
multi-agent-system/
├── agents/
│   ├── orchestrator/
│   ├── product/
│   ├── reasoning/
│   ├── research/
│   ├── architect/
│   ├── builder/
│   ├── evaluator/
│   └── release/
│
├── skills/
│   ├── product/
│   ├── reasoning/
│   ├── research/
│   ├── engineering/
│   ├── security/
│   ├── testing/
│   └── operations/
│
├── workflows/
│   ├── discover/
│   ├── design/
│   ├── build/
│   ├── validate/
│   └── release/
│
├── knowledge/
│   ├── sources/
│   ├── evidence/
│   ├── concepts/
│   └── learned-skills/
│
├── artifacts/
│   ├── schemas/
│   ├── templates/
│   └── examples/
│
├── evaluations/
│   ├── skills/
│   ├── agents/
│   └── workflows/
│
└── registry/
    ├── skills.yml
    ├── agents.yml
    └── workflows.yml
```

## 19. What to directly leverage

### Highest priority

1. **Skill anatomy**
2. **Skill metadata and registry**
3. **Artifact-first outputs**
4. **Composable skills**
5. **Workflow/recipe chaining**
6. **Skill routing**
7. **Evidence grading**
8. **Quality/conformance gates**
9. **Worked examples as benchmarks**
10. **Explicit "when NOT to use" rules**

### Useful second tier

- PM lifecycle taxonomy
- reasoning framework catalog
- writing-style components
- governed document templates
- plugin/distribution model

### Do not blindly copy

- Their exact PM taxonomy
- Their exact workflow names
- Their Claude Code-specific runtime behavior
- MCP implementation as the core architecture
- Every individual framework

We should **extract the architectural patterns and rebuild them around our broader multi-agent mission**.

## 20. Integration with our existing AI-agent knowledge strategy

Product on Purpose fits particularly well as the **Skill Engineering Standard** layer.

```text
External repos / books / courses
              ↓
        Knowledge extraction
              ↓
       Evidence + sources
              ↓
        Skill generation
              ↓
     Skill quality evaluation
              ↓
        Skill Registry
              ↓
        Skill Router
              ↓
       Multi-Agent System
              ↓
          Artifacts
              ↓
       Critic / Evaluator
              ↓
        Improved system
```

This creates a feedback loop:

```text
Knowledge → Skills → Agents → Products
     ↑                         |
     |                         ↓
     +------ Evaluation -------+
```

## Final recommendation

**Adopt Product on Purpose as a reference implementation for our skill architecture, not simply as a PM skill dependency.**

The three repositories to study most deeply are:

1. `pm-skills` — how to package domain expertise as reusable agent capabilities.
2. `thinking-framework-skills` — how to package reasoning methods with evidence, caveats and artifact-producing procedures.
3. `agent-skills-toolkit` — how to standardize, validate and govern a large skill library.

The most important principle to carry into our system is:

> **Agents should not contain all the expertise. Agents should dynamically acquire the right tested skills, execute them through workflows, exchange structured artifacts, and have independent evaluators verify the result.**

That gives us a scalable path from **knowledge → skills → agents → workflows → autonomous product execution**, without turning the system into a collection of giant prompts.
