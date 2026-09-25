# Product Factory — Agent Orchestration, Context, Budgets & Model Strategy

## Purpose

This document consolidates the recommendations for improving the Product Factory so it can build higher-quality products/dashboards while controlling model cost, context size, agent behavior and iteration loops.

The central idea is:

> **Do not solve mediocre AI product output only by adding more skills or using a stronger model. Build a factory that separates product judgment, implementation, evaluation and iteration, while tightly controlling context and budget.**

---

# 1. The fundamental problem

A factory can have excellent GitHub skills and still produce an average dashboard.

Skills provide **knowledge**:
- UX principles
- dashboard patterns
- design systems
- component patterns
- coding practices
- accessibility
- examples

But the model still has to exercise **judgment**:
- What information matters most?
- What should be above the fold?
- What should be a KPI, chart, table or action?
- What should be grouped?
- What deserves visual emphasis?
- What should color mean?
- What interactions matter?
- Is the overall page coherent?

Therefore:

```text
More skills != automatically better product design
```

The factory needs an explicit decision-making and evaluation process.

---

# 2. Recommended factory pipeline

### Basic/current pattern

```text
Requirement
    ↓
Skill Retrieval
    ↓
LLM
    ↓
UI
```

### Recommended pattern

```text
Requirement
    ↓
Product Understanding
    ↓
Skill Retrieval / Routing
    ↓
Product Design Specification
    ↓
UX / Information Architecture
    ↓
Dashboard Archetype
    ↓
Design System / Tokens
    ↓
UI Architecture
    ↓
Implementation
    ↓
Automated Tests
    ↓
Rendered UI / Screenshot
    ↓
Visual QA
    ↓
Design Critic
    ↓
Revision
    ↓
Final QA
    ↓
Accepted Product
```

The exact number of agents is not important. The separation of responsibilities is.

---

# 3. Product Design Specification

Before implementation, create a structured artifact describing the product decision.

Example:

```yaml
product_goal:
primary_user:
primary_job:
secondary_jobs:

key_questions:
  - ...

critical_actions:
  - ...

information_priority:
  primary:
  secondary:
  tertiary:

dashboard_type:
  operational | analytical | executive | workflow | monitoring

recommended_layout:
sections:
navigation:
interaction_model:
visual_hierarchy:
design_principles:
things_to_avoid:
```

The coding agent should consume this artifact instead of inventing product structure while writing code.

---

# 4. Dashboard archetypes

Create reusable dashboard structures.

## Executive

```text
Headline KPIs
    ↓
Trends
    ↓
Business drivers
    ↓
Exceptions
    ↓
Details
```

## Operational

```text
Current status
    ↓
Alerts / exceptions
    ↓
Work queue
    ↓
Performance
    ↓
Historical trends
```

## Sales / Pipeline

```text
Pipeline summary
    ↓
Stage / funnel distribution
    ↓
Pipeline movement
    ↓
Priority opportunities
    ↓
Forecast
    ↓
Opportunity details
```

## Analytics

```text
KPIs
    ↓
Trend
    ↓
Segmentation
    ↓
Comparison
    ↓
Drill-down
```

Archetypes are starting points, not rigid templates. The product designer can adapt them to the actual workflow.

---

# 5. Design system

Do not allow every generation to invent its own visual language.

Create factory-level design tokens:

```text
Typography
Spacing
Radius
Shadows
Borders
Surfaces
Primary / brand
Neutral
Success
Warning
Danger
Information
```

The model's job should be:

> Apply the design system intelligently.

Not:

> Invent a new color system every time.

This improves consistency and reduces arbitrary design decisions.

---

# 6. Design Critic

A separate critic should review the generated product.

Review at least:

- Product logic
- Information hierarchy
- Above-the-fold clarity
- Layout
- Whitespace
- Cognitive load
- Grouping
- Color semantics
- Typography hierarchy
- Chart usefulness
- Interaction model
- Consistency
- Accessibility
- Overall coherence

Use a scorecard:

| Dimension | Score |
|---|---:|
| Product logic | /10 |
| Information hierarchy | /10 |
| Layout | /10 |
| Visual hierarchy | /10 |
| Color | /10 |
| Typography | /10 |
| Interaction | /10 |
| Consistency | /10 |
| Accessibility | /10 |
| Overall | /10 |

Example gate:

```text
< 7       → redesign
7–8       → refine
> 8       → accept
```

The thresholds should be configurable.

---

# 7. Visual QA loop

Eventually the factory should evaluate the **rendered product**, not just source code.

Recommended loop:

```text
Generate
   ↓
Run application
   ↓
Capture screenshot
   ↓
Vision-capable model reviews screenshot
   ↓
Find visual/product issues
   ↓
Generate targeted fixes
   ↓
Render again
   ↓
Final visual QA
```

Examples of useful visual critique:

- Too many competing visual elements
- Weak hierarchy
- Excessive card usage
- Poor whitespace
- Inconsistent spacing
- Bad contrast
- Charts that don't communicate useful information
- Important actions buried
- Visually noisy color usage
- Poor responsive behavior

---

# 8. The most important architecture: Context Manager

Agents should **not automatically receive the entire project context**.

Instead:

```text
Orchestrator
     ↓
Context Manager
     ↓
Build minimum context package
     ↓
Agent
```

The Context Manager determines:

> What is the minimum information this agent needs to perform this task correctly?

This improves both:
- Quality
- Cost

---

# 9. Artifact-based communication

Prefer structured artifacts over passing entire conversations between agents.

Example project state:

```text
/workspace/

  product/
    requirement.md

  artifacts/
    product-spec.json
    ux-spec.json
    design-spec.json
    design-tokens.json
    dashboard-archetype.json
    component-plan.json
    api-contract.json

  src/
    ...

  qa/
    visual-review.json
    functional-review.json
```

Agent flow:

```text
Product Agent
    ↓
product-spec.json
    ↓
UX Agent
    ↓
ux-spec.json
    ↓
Design Agent
    ↓
design-spec.json
    ↓
UI Architect
    ↓
component-plan.json
    ↓
Coding Agent
    ↓
Implementation
    ↓
Visual QA
    ↓
visual-review.json
    ↓
Coding Agent
```

This prevents huge conversation histories from being repeatedly passed around.

---

# 10. Agents should request context

Instead of:

```text
Coding Agent receives:
- entire source tree
- every skill
- every conversation
- every previous output
```

use:

```text
Coding Agent
    ↓
"I need OpportunityCard.tsx"
    ↓
Context/File Manager
    ↓
returns only required file
```

For a Pipeline page, the coding agent might initially receive:

```text
Pipeline.tsx
relevant components
relevant types
design tokens
API contract
design specification
latest QA findings
```

It should be able to request additional files when necessary.

---

# 11. Skill routing

Do not send every retrieved GitHub skill to every agent.

Recommended:

```text
Requirement
    ↓
Skill Router
    ↓
Select 3–5 relevant skills
    ↓
Extract relevant sections
    ↓
Agent
```

For a Pipeline Dashboard, the relevant skills might be:

```text
Dashboard UX
Data visualization
Design system
Accessibility
React UI patterns
```

Unrelated skills should not enter the agent's context.

---

# 12. Agent context contract

Each agent should have an explicit contract.

Example:

```yaml
agent:
  name: design_critic

  model: gpt-5.4-mini

  input_budget:
    max_tokens: 12000

  output_budget:
    max_tokens: 5000

  allowed_inputs:
    - design_spec
    - design_tokens
    - screenshot
    - component_tree
    - latest_qa

  forbidden_inputs:
    - full_project_history
    - unrelated_skills
    - unrelated_source_files
```

This makes the orchestrator responsible for context governance.

---

# 13. Token budgets

Use two different types of token budgets.

## Per-agent output budget

Example:

```yaml
product_analyzer:
  max_output_tokens: 4000

ux_architect:
  max_output_tokens: 6000

ui_architect:
  max_output_tokens: 6000

coding_agent:
  max_output_tokens: 12000

design_critic:
  max_output_tokens: 5000
```

## Per-agent input/context budget

Also control how much context an agent can consume.

Example:

```yaml
design_critic:
  max_input_tokens: 12000
```

Output limits alone do NOT control the cost of repeatedly sending huge contexts.

---

# 14. Project-level budget

The orchestrator should maintain a hard project budget.

Example:

```yaml
project_budget:
  max_total_input_tokens: 1000000
  max_total_output_tokens: 300000
  max_cost_usd: 3.00
  max_iterations: 3
```

If the project reaches, for example:

```text
$2.70 / $3.00
```

the factory can enter:

```text
budget_conservation_mode
```

Possible behavior:
- Stop unnecessary agents
- Reduce optional reviews
- Use cheaper model
- Stop additional iterations
- Produce final result with known limitations

---

# 15. Stop conditions

Agent loops must have explicit termination rules.

Example:

```yaml
design_critic:
  max_iterations: 2

  stop_when:
    - score >= 8
    - no_critical_issues
    - no_major_visual_issues
```

Coding:

```yaml
coding_agent:
  max_revisions: 2
```

Without these controls, the factory can accidentally create:

```text
Critic
 ↓
Fix
 ↓
Critic
 ↓
Fix
 ↓
Critic
 ↓
Fix
 ↓
...
```

which can cause unnecessary cost.

---

# 16. Model routing strategy

Do not use one model for every task.

Use the cheapest model that can reliably perform the task.

## Tier 1 — Cheap workhorse

### GPT-5 mini

Good candidates:
- Orchestration
- Requirement extraction
- Classification
- Skill routing
- Simple planning
- Formatting
- Straightforward coding
- Debugging
- Tests
- Repetitive tasks

Current published API list price:
- $0.25 / 1M input tokens
- $2 / 1M output tokens

Source:
https://developers.openai.com/api/docs/models/gpt-5-mini

---

## Tier 2 — Stronger workhorse

### GPT-5.4 mini

Good candidates:
- Product/UX reasoning
- Information architecture
- UI architecture
- Coding
- More difficult debugging
- Design critique
- Agentic tasks

Current published API list price:
- $0.75 / 1M input tokens
- $4.50 / 1M output tokens

Source:
https://developers.openai.com/api/docs/models/gpt-5.4-mini

This is a particularly interesting default model for the Product Factory because it balances capability and cost.

---

## Tier 2 alternative — Visual QA

### Gemini 2.5 Flash

Good candidates:
- Screenshot analysis
- Visual QA
- Large-context analysis
- Multimodal review
- Cheap secondary opinion

Current published API list price:
- $0.30 / 1M input tokens
- $2.50 / 1M output tokens

It supports multimodal input and a large context window.

Source:
https://ai.google.dev/gemini-api/docs/pricing

---

## Tier 3 — Selective premium reasoning

### GPT-5

Use selectively for:
- Difficult product decisions
- Major UX ambiguity
- Complex architecture
- High-value design critique
- Escalation when cheaper models disagree

Current published API list price:
- $1.25 / 1M input tokens
- $10 / 1M output tokens

Source:
https://developers.openai.com/api/docs/models/gpt-5

Do not make this the default model for every agent.

---

## Optional alternative

### Claude Sonnet 4.6

Potential use:
- Difficult coding
- Agentic workflows
- Design/coding A/B testing

Current published API list price:
- $3 / 1M input tokens
- $15 / 1M output tokens

It is strong, but more expensive, so initially treat it as an optional benchmark rather than a mandatory factory component.

---

# 17. Recommended initial model map

A practical starting configuration:

| Factory Stage | Model |
|---|---|
| Orchestrator | GPT-5 mini |
| Requirement extraction | GPT-5 mini |
| Skill routing | GPT-5 mini |
| Product analysis | GPT-5 mini |
| Product Design Specification | GPT-5.4 mini |
| Dashboard archetype | GPT-5 mini |
| UX / IA | GPT-5.4 mini |
| Design system application | GPT-5 mini |
| UI architecture | GPT-5.4 mini |
| Coding | GPT-5.4 mini |
| Debugging | GPT-5 mini / GPT-5.4 mini |
| Functional testing | GPT-5 mini |
| Screenshot QA | Gemini 2.5 Flash |
| Design critique | GPT-5.4 mini |
| Difficult escalation | GPT-5 |
| Final visual QA | Gemini 2.5 Flash |

Claude can be introduced later for A/B benchmarking.

---

# 18. Recommended architecture

```text
                         PRODUCT FACTORY
                                │
                         ┌──────▼──────┐
                         │ Orchestrator│
                         └──────┬──────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       ↓                        ↓                        ↓
 Budget Manager           Context Manager           Skill Router
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                ↓
                         Agent Execution
                                │
             ┌──────────────────┼──────────────────┐
             ↓                  ↓                  ↓
          Product              UX               Coding
          Agent              Agent               Agent
             │                  │                  │
             └──────────────────┼──────────────────┘
                                ↓
                           Artifacts
                                ↓
                      Rendered Application
                                ↓
                         Visual QA / Critic
                                ↓
                           QA Report
                                ↓
                           Revision
                                ↓
                         Budget Check
                                ↓
                         Final Product
```

The important principle:

> **The orchestrator owns context and budget. Agents own tasks.**

Agents should not inherit the entire factory state.

---

# 19. Cost model

A substantial Pipeline Dashboard build can potentially be kept around **$1–$3 per complete generation/revision run** with controlled context, sensible model routing and limited iterations.

This is an engineering target, not a guaranteed price.

Actual cost depends on:
- Input tokens
- Output tokens
- Repeated context
- Number of agents
- Number of iterations
- Codebase size
- Skill size
- Screenshot/vision inputs
- Model pricing changes

A poorly controlled factory can easily become several times more expensive because it repeatedly sends the same huge context.

Illustrative planning range:

| Full runs | Approx planning cost |
|---:|---:|
| 1 | $1–$3 |
| 2 | $2–$6 |
| 3 | $3–$9 |
| 5 | $5–$15 |
| 10 | $10–$30 |

These are rough planning numbers, not vendor quotes.

---

# 20. The real cost metric

Do not optimize for:

```text
Number of agents
```

or:

```text
Tokens used
```

alone.

Track:

```text
Factory Quality Score
Cost / Accepted Product
Iterations / Product
Human Corrections / Product
Time to Accepted Product
Input Tokens / Product
Output Tokens / Product
```

The most important metric is:

> **Cost per accepted-quality product**

A $2 generation that needs 3 hours of human cleanup is not necessarily better than a $4 generation that is almost production-ready.

---

# 21. Recommended telemetry

Every factory run should record something like:

```json
{
  "run_id": "pipeline-dashboard-001",

  "budget": {
    "max_usd": 3.00,
    "spent_usd": 1.42
  },

  "tokens": {
    "input": 384200,
    "output": 92100
  },

  "iterations": 2,

  "quality_score": 8.3,

  "human_corrections": 4,

  "agents": {
    "product": {
      "model": "gpt-5-mini",
      "input_tokens": 18000,
      "output_tokens": 3200
    },
    "ux": {
      "model": "gpt-5.4-mini",
      "input_tokens": 24000,
      "output_tokens": 5100
    }
  }
}
```

This lets you objectively compare factory versions.

---

# 22. Do not make everything an LLM call

Use normal code wherever deterministic logic is sufficient.

Examples:

```text
Schema validation
Token validation
File discovery
Path validation
Budget accounting
Cost calculation
Iteration counting
Artifact storage
Component existence checks
Type checking
Linting
Unit tests
Build checks
```

Use LLMs when judgment is actually required.

This reduces cost and improves predictability.

---

# 23. Recommended experiment before changing everything

Use the Pipeline Dashboard as the benchmark.

Run three versions.

## A — Current factory

```text
Requirement
 ↓
Skills
 ↓
Current model
 ↓
Dashboard
```

## B — Structured factory using current models

```text
Requirement
 ↓
Product Design Spec
 ↓
UX / IA
 ↓
Dashboard
 ↓
Critic
 ↓
Revision
```

## C — Hybrid model factory

```text
Cheap model
 ↓
Routing / extraction / routine work

GPT-5.4 mini
 ↓
Design / architecture / coding / critique

Gemini Flash
 ↓
Visual QA

GPT-5
 ↓
Only difficult escalations
```

Measure:

```text
Quality
Cost
Iterations
Human corrections
Time
```

This experiment will reveal whether your biggest limitation is:
1. Model capability
2. Factory architecture
3. Context management
4. Missing visual feedback
5. Some combination of the above

---

# 24. Recommended implementation priority

Before collecting many more GitHub skills, check whether your factory already has these capabilities.

### Priority 1

**Context Manager**

Can every agent receive only the context it actually needs?

### Priority 2

**Budget Manager**

Can the orchestrator enforce:
- Per-agent input budget
- Per-agent output budget
- Project token budget
- Project dollar budget
- Maximum iterations?

### Priority 3

**Artifact Store**

Can agents communicate through structured artifacts instead of giant conversation histories?

### Priority 4

**Product Design Specification**

Is product/UX reasoning separated from coding?

### Priority 5

**Design Critic**

Does the factory have an explicit independent quality-review stage?

### Priority 6

**Visual QA**

Can the factory inspect the actual rendered dashboard through screenshots?

### Priority 7

**Model Router**

Can the factory choose a model based on task difficulty and budget?

---

# 25. Final architecture principle

The Product Factory should evolve from:

```text
LLM + lots of skills
```

to:

```text
Knowledge
   +
Explicit product reasoning
   +
Controlled context
   +
Controlled budgets
   +
Specialized agents
   +
Design system
   +
Implementation
   +
Automated testing
   +
Visual evaluation
   +
Iteration
```

### Most important takeaway

**Do not simply add more agents, skills or expensive models.**

Build a system where:

- Skills provide knowledge
- The orchestrator provides workflow
- The Context Manager provides only relevant information
- The Budget Manager controls spend
- Agents perform specialized tasks
- Artifacts preserve decisions
- The Design Critic challenges the result
- Visual QA evaluates the actual UI
- Model routing assigns capability according to task difficulty

Then the factory can become progressively better while remaining economically viable.

---

## Current model-price references

Model pricing changes frequently, so verify before implementing a hard-coded cost table.

- OpenAI GPT-5 mini: https://developers.openai.com/api/docs/models/gpt-5-mini
- OpenAI GPT-5.4 mini: https://developers.openai.com/api/docs/models/gpt-5.4-mini
- OpenAI GPT-5: https://developers.openai.com/api/docs/models/gpt-5
- Google Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Anthropic Claude pricing: https://www.anthropic.com/pricing
