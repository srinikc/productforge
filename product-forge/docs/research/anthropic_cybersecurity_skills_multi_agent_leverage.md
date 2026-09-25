# Anthropic Cybersecurity Skills --- What We Should Leverage for Our Multi-Agent System

## Source

Repository: https://github.com/mukul975/Anthropic-Cybersecurity-Skills

This is an independent community project, not an Anthropic product. At
the time of review, it contains **817 structured cybersecurity skills
across 29 security domains**, mapped to six security/risk frameworks and
designed for progressive skill discovery and loading.

## Executive Summary

The most important thing to take from this repository is **not the
cybersecurity content itself**.

The important idea is the **architecture of a large, modular,
agent-consumable skill library**:

> Keep expert knowledge outside the base agent prompt, make skills
> discoverable through lightweight metadata, and load only the skills
> required for the current task.

This is highly relevant to our multi-agent system.

We should adopt this pattern as a **general Skill System**, then
populate it with skills from cybersecurity, software engineering, system
design, cloud, AI/ML, product engineering, DevOps, research, courses,
documentation, and other domains.

------------------------------------------------------------------------

# 1. What the Repository Demonstrates

The repository provides hundreds of structured skills using a consistent
format.

A skill typically contains:

``` text
skill/
├── SKILL.md
├── references/
├── scripts/
└── assets/
```

The `SKILL.md` contains structured metadata plus operational
instructions.

Typical sections include:

-   When to Use
-   Prerequisites
-   Workflow
-   Verification

Metadata includes things such as:

-   name
-   description
-   domain
-   subdomain
-   tags
-   version
-   framework mappings
-   author/license information

The repository reports compatibility with many agent environments,
demonstrating that the skill format can sit **above the underlying agent
runtime** rather than being tightly coupled to one model.

------------------------------------------------------------------------

# 2. The Core Architecture We Should Adopt

## Progressive Disclosure

This is the single most important architectural lesson.

Do **not** put every skill into every agent's context.

Instead:

``` text
                    User Task
                       |
                       v
                Task Understanding
                       |
                       v
                  Skill Router
                       |
             Search lightweight metadata
                       |
          +------------+-------------+
          |            |             |
       Skill A      Skill B       Skill C
          |            |             |
          +------------+-------------+
                       |
                       v
               Load top relevant skills
                       |
                       v
                Execute workflow
                       |
                       v
                  Verification
```

The repository describes a model where agents can scan lightweight skill
frontmatter and then fully load only the relevant skills.

This dramatically reduces context consumption while allowing a very
large skill library.

### Our principle

> **Discover cheaply. Load selectively. Execute deliberately. Verify
> explicitly.**

------------------------------------------------------------------------

# 3. Skill Registry

We should create a central **Skill Registry** rather than treating
skills as arbitrary Markdown files.

Example:

``` yaml
skill_id: cloud-incident-response
name: Cloud Incident Response
domain: cybersecurity
subdomain: cloud
tags:
  - aws
  - azure
  - gcp
  - incident-response
capabilities:
  - investigation
  - containment
risk_level: medium
trust_level: verified
version: 1.0
source:
  type: github
  repository: ...
frameworks:
  - NIST-CSF
  - MITRE-ATT&CK
```

The registry should answer:

-   What skills exist?
-   What domain do they belong to?
-   What can they do?
-   What tools do they require?
-   Which agents can use them?
-   How trustworthy are they?
-   What version are they?
-   What other skills do they depend on?
-   What frameworks/standards do they map to?

------------------------------------------------------------------------

# 4. Separate Skill Discovery From Skill Execution

We should have two distinct layers.

## Discovery Layer

Responsible for:

-   searching skill metadata
-   matching task → skills
-   ranking skills
-   checking prerequisites
-   checking trust/security level
-   resolving dependencies

## Execution Layer

Responsible for:

-   loading the selected skill
-   executing its workflow
-   invoking tools
-   collecting evidence
-   validating results
-   reporting outcomes

This separation prevents the agent from blindly executing everything it
discovers.

------------------------------------------------------------------------

# 5. Multi-Agent Architecture

This repository should influence the architecture of our multi-agent
system as follows:

``` text
                         ORCHESTRATOR
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
        Research Agent   Engineering Agent  Security Agent
              |               |               |
              +---------------+---------------+
                              |
                       Shared Skill Router
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
        Domain Skills    Workflow Skills   Tool Skills
              |
              v
        Knowledge Sources
```

Agents should **share the skill ecosystem**, but each agent should only
load the skills relevant to its role.

For example:

### Research Agent

Could load:

-   literature research
-   source verification
-   information extraction
-   comparative analysis
-   synthesis
-   citation verification

### System Design Agent

Could load:

-   distributed systems
-   architecture patterns
-   scalability
-   databases
-   caching
-   messaging
-   reliability
-   security
-   capacity planning

### Coding Agent

Could load:

-   language-specific engineering
-   testing
-   debugging
-   refactoring
-   API design
-   database migrations
-   DevOps
-   code review

### Security Agent

Could load:

-   threat modeling
-   incident response
-   vulnerability analysis
-   cloud security
-   application security
-   detection engineering

------------------------------------------------------------------------

# 6. Skills Should Be Reusable Across Agents

A major design principle:

> **Skills belong to the capability layer, not to individual agents.**

Do not create:

``` text
research-agent-skills/
coding-agent-skills/
security-agent-skills/
```

Instead create:

``` text
skills/
├── research/
├── software-engineering/
├── system-design/
├── cybersecurity/
├── cloud/
├── devops/
├── ai-ml/
└── product/
```

Then agents dynamically acquire capabilities.

This makes the system much easier to evolve.

------------------------------------------------------------------------

# 7. Skill Metadata Should Be Machine-Discoverable

The repository's YAML frontmatter is an excellent pattern.

We should standardize our own metadata around something like:

``` yaml
---
id: designing-event-driven-architecture
name: Designing Event-Driven Architecture
domain: system-design
subdomain: distributed-systems

description: >
  Design reliable event-driven systems using queues,
  streams, brokers, consumers and delivery guarantees.

tags:
  - event-driven
  - kafka
  - messaging
  - distributed-systems

capabilities:
  - architecture-design
  - scalability
  - reliability

prerequisites:
  - distributed-systems-basics

tools:
  - architecture-diagram
  - documentation-search

dependencies:
  - messaging-patterns

risk_level: low
trust_level: verified

version: 1.0
---
```

The description and tags are particularly important because they become
the **routing/indexing mechanism**.

------------------------------------------------------------------------

# 8. Framework Mappings Are Extremely Valuable

One of the strongest features of this repository is that skills can be
mapped to external frameworks.

For cybersecurity, it maps skills to frameworks such as:

-   MITRE ATT&CK
-   NIST CSF
-   MITRE ATLAS
-   MITRE D3FEND
-   NIST AI RMF
-   MITRE F3

We should generalize this idea.

A skill should be able to reference:

``` yaml
frameworks:
  - name: NIST-CSF
    references:
      - DE.CM-01

  - name: MITRE-ATT&CK
    references:
      - T1003

  - name: OWASP
    references:
      - A01
```

For other domains:

``` yaml
frameworks:
  - AWS-Well-Architected
  - Kubernetes
  - OWASP
  - ISO-27001
  - CNCF
  - SRE
```

This allows agents to reason using recognized standards rather than
isolated knowledge.

------------------------------------------------------------------------

# 9. Verification Must Be a First-Class Skill Component

This is especially important for autonomous agents.

A skill should not merely say:

``` text
Do X.
```

It should say:

``` text
Do X.

Then verify:
- expected output exists
- tests pass
- evidence supports the conclusion
- assumptions are satisfied
- no required step was skipped
```

Recommended structure:

``` markdown
## Workflow

1. ...
2. ...
3. ...

## Verification

1. Confirm ...
2. Test ...
3. Compare ...
4. Report evidence ...

## Failure Modes

- If X fails, try Y.
- If evidence is insufficient, escalate.
```

This is highly compatible with our goal of building agents that
**execute and self-check rather than simply generate answers**.

------------------------------------------------------------------------

# 10. Skills Should Contain Workflows, Not Just Knowledge

A normal knowledge document says:

> Kafka provides distributed event streaming.

A useful agent skill says:

``` text
When designing an event-driven architecture:

1. Identify event producers.
2. Identify consumers.
3. Determine ordering requirements.
4. Determine delivery semantics.
5. Select broker technology.
6. Define partitioning strategy.
7. Define retry/DLQ strategy.
8. Define observability.
9. Define failure handling.
10. Validate throughput and latency requirements.
```

Therefore:

> **Knowledge tells the agent what something is. A skill tells the agent
> how to perform a task.**

We should preserve both layers.

------------------------------------------------------------------------

# 11. Knowledge Base vs Skills

This repository reinforces an important distinction.

## Knowledge

``` text
What is Kafka?
What is CAP?
What is OAuth?
What is Kubernetes?
```

## Skills

``` text
Design a Kafka-based event pipeline.
Debug OAuth token failures.
Design Kubernetes deployment architecture.
Analyze a distributed-system bottleneck.
```

Our architecture should therefore be:

``` text
Knowledge Base
      |
      +---- facts
      +---- concepts
      +---- documentation
      +---- references
      +---- courses
      |
      v
Skill Layer
      |
      +---- procedures
      +---- workflows
      +---- decision trees
      +---- verification
      +---- tool usage
      |
      v
Agent
```

------------------------------------------------------------------------

# 12. External Repositories Should Become Skill Sources

We should not manually recreate every useful skill.

Instead:

``` text
External GitHub Repository
          |
          v
      Ingestion
          |
          v
      Validation
          |
          v
    Skill Normalization
          |
          v
     Skill Registry
          |
          v
       Indexing
          |
          v
      Agent Router
```

Examples of possible sources:

-   cybersecurity skill libraries
-   system design repositories
-   coding-agent skill libraries
-   AI engineering repositories
-   course material
-   official documentation
-   standards
-   open-source playbooks

This turns the system into a **living capability ecosystem**.

------------------------------------------------------------------------

# 13. Do Not Automatically Trust Imported Skills

This repository also highlights a major security consideration.

A skill may contain:

-   executable scripts
-   shell commands
-   external tool calls
-   privileged operations
-   offensive security procedures
-   instructions that alter files or infrastructure

Therefore imported skills should go through:

``` text
External Skill
      |
      v
Security Scan
      |
      v
Content Validation
      |
      v
License Check
      |
      v
Provenance Check
      |
      v
Human/Agent Review
      |
      v
Trust Classification
```

Suggested trust levels:

``` text
UNTRUSTED
COMMUNITY
REVIEWED
VERIFIED
FIRST_PARTY
```

The agent should know the trust level before executing a skill.

------------------------------------------------------------------------

# 14. Skills Need Permissions

A mature implementation should not allow a skill to execute arbitrary
tools simply because it was retrieved.

For example:

``` yaml
permissions:
  filesystem: read
  network: restricted
  shell: none
  cloud: none
```

A more powerful skill might require:

``` yaml
permissions:
  filesystem: read-write
  shell: restricted
  network: restricted
```

High-risk actions should require explicit authorization.

This is particularly important for cybersecurity, infrastructure,
production deployments and financial systems.

------------------------------------------------------------------------

# 15. Skill Dependencies

Skills should be composable.

For example:

``` text
Design Production API
       |
       +--> API Design
       +--> Authentication
       +--> Database Design
       +--> Caching
       +--> Observability
       +--> Security
       +--> Deployment
```

Metadata can express:

``` yaml
dependencies:
  - api-design
  - authentication
  - database-design
  - observability
```

The router can construct a **skill dependency graph**.

------------------------------------------------------------------------

# 16. Skill Composition for Multi-Agent Workflows

This becomes particularly powerful when multiple agents collaborate.

Example:

``` text
User:
"Design a secure multi-region SaaS platform."

                ORCHESTRATOR
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
      Architect    Security     SRE Agent
          |           |           |
          v           v           v
    Architecture   Threat      Reliability
      Skills       Modeling      Skills
          |           |           |
          +-----------+-----------+
                      |
                      v
                Review Agent
                      |
                      v
                 Final Design
```

The agents aren't merely exchanging messages.

They are **sharing a common capability/skill substrate**.

That should be one of the foundational principles of our multi-agent
system.

------------------------------------------------------------------------

# 17. Recommended Architecture for Our System

``` text
                         USER
                           |
                           v
                    ORCHESTRATOR
                           |
                           v
                    TASK PLANNER
                           |
                           v
                    SKILL ROUTER
                           |
              +------------+-------------+
              |            |             |
              v            v             v
          Skill Index   Knowledge DB   Tool Registry
              |
              v
        Relevant Skills
              |
       +------+------+------+
       |      |      |      |
       v      v      v      v
    Agent A Agent B Agent C Agent D
       |      |      |      |
       +------+------+------+
              |
              v
          EXECUTION
              |
              v
        VERIFICATION
              |
              v
          EVALUATION
              |
              v
        FINAL RESPONSE
```

------------------------------------------------------------------------

# 18. Recommended Skill Lifecycle

Every skill should move through a lifecycle:

``` text
DISCOVER
   ↓
INGEST
   ↓
NORMALIZE
   ↓
VALIDATE
   ↓
CLASSIFY
   ↓
INDEX
   ↓
RETRIEVE
   ↓
LOAD
   ↓
EXECUTE
   ↓
VERIFY
   ↓
EVALUATE
   ↓
IMPROVE
```

This is better than simply copying Markdown files into an agent
directory.

------------------------------------------------------------------------

# 19. What We Should Reuse Directly

From this repository, we should strongly consider adopting:

### A. Standardized `SKILL.md`

Use one predictable skill definition format.

### B. YAML frontmatter

Use metadata for fast discovery.

### C. Progressive disclosure

Scan metadata first; load complete skills only when needed.

### D. Workflow-oriented skills

Make skills executable procedures, not essays.

### E. Verification sections

Every important skill should define how success is checked.

### F. References directory

Keep deep technical information separate from the core workflow.

### G. Scripts/assets separation

Keep executable helpers and templates separate from instructions.

### H. Framework mappings

Connect skills to recognized external standards.

### I. Versioning

Skills should be versioned and updateable independently of agents.

### J. Cross-agent portability

Skills should not depend on one specific model or agent framework
wherever possible.

------------------------------------------------------------------------

# 20. What We Should NOT Copy Blindly

We should not simply clone the repository into every agent.

Avoid:

-   loading hundreds of skills into context
-   treating all skills as trusted
-   executing imported scripts automatically
-   coupling skills to one agent
-   embedding all knowledge inside `SKILL.md`
-   assuming a skill is correct simply because it exists
-   allowing high-risk skills to bypass permissions
-   duplicating the same skill for every agent

Instead, use the repository as a **reference implementation for our
Skill Platform**.

------------------------------------------------------------------------

# 21. Recommended Directory Structure

A starting point for our system:

``` text
ai-agent-system/
│
├── agents/
│   ├── orchestrator/
│   ├── researcher/
│   ├── architect/
│   ├── engineer/
│   ├── security/
│   ├── reviewer/
│   └── evaluator/
│
├── skills/
│   ├── software-engineering/
│   ├── system-design/
│   ├── cybersecurity/
│   ├── cloud/
│   ├── devops/
│   ├── ai-ml/
│   ├── research/
│   └── product/
│
├── knowledge/
│   ├── concepts/
│   ├── documentation/
│   ├── courses/
│   ├── books/
│   ├── standards/
│   └── references/
│
├── registry/
│   ├── skills.yaml
│   ├── domains.yaml
│   ├── frameworks.yaml
│   └── tools.yaml
│
├── indexes/
│   ├── skill-index/
│   └── knowledge-index/
│
├── policies/
│   ├── permissions.yaml
│   ├── trust.yaml
│   └── execution.yaml
│
└── evaluations/
    ├── skill-tests/
    ├── agent-tests/
    └── regression-tests/
```

------------------------------------------------------------------------

# 22. The Bigger Insight

The repository demonstrates an important transition in agent
engineering:

``` text
Old approach:

LLM
 +
Huge System Prompt
 +
Tool Descriptions
 +
RAG
```

toward:

``` text
New approach:

LLM
 |
 +-- Agent Policy
 |
 +-- Skill Router
 |      |
 |      +-- Domain Skills
 |      +-- Workflow Skills
 |      +-- Tool Skills
 |
 +-- Knowledge Retrieval
 |
 +-- Tool Registry
 |
 +-- Memory
 |
 +-- Evaluator
 |
 +-- Security / Permissions
```

This is much more scalable.

The model remains general-purpose while the **external capability layer
continuously expands**.

------------------------------------------------------------------------

# 23. Priority for Our Multi-Agent System

## P0 --- Build

1.  Standard `SKILL.md` format
2.  Skill metadata/frontmatter
3.  Skill registry
4.  Skill discovery/search
5.  Progressive loading
6.  Skill → agent routing
7.  Skill verification
8.  Trust classification
9.  Permission model

## P1 --- Add

10. Skill dependency graph
11. Skill composition
12. Framework mappings
13. Version management
14. Skill evaluation/regression tests
15. External repository ingestion
16. Automatic skill indexing

## P2 --- Advanced

17. Skill quality scoring
18. Agent-generated skill proposals
19. Automatic skill improvement
20. Skill usage analytics
21. Capability gap detection
22. Cross-agent skill sharing
23. Dynamic skill creation

------------------------------------------------------------------------

# 24. Final Recommendation

**Leverage this repository as a reference architecture, not merely as a
cybersecurity content dump.**

The most valuable ideas are:

1.  **Skills are modular capabilities.**
2.  **Metadata makes skills discoverable.**
3.  **Progressive disclosure keeps context manageable.**
4.  **Workflows make knowledge operational.**
5.  **Verification makes agent execution reliable.**
6.  **Framework mappings make skills structured and auditable.**
7.  **Skills should be reusable across multiple agents.**
8.  **External skills require trust, permissions and validation.**
9.  **Knowledge and executable skills should remain separate layers.**
10. **A shared Skill Registry should become a core component of our
    multi-agent architecture.**

### Strategic conclusion

We should build our multi-agent platform around:

``` text
             GENERAL-PURPOSE MODELS
                       |
                       v
                  ORCHESTRATOR
                       |
                       v
                 SKILL ROUTER
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
    KNOWLEDGE        SKILLS         TOOLS
       BASE          LIBRARY       REGISTRY
        |              |              |
        +--------------+--------------+
                       |
                       v
                 SPECIALIST AGENTS
                       |
                       v
                  VERIFICATION
                       |
                       v
                    OUTPUT
```

**Anthropic-Cybersecurity-Skills is therefore a strong reference for the
`SKILLS LIBRARY + SKILL ROUTER` portion of our architecture.**

We should take this same pattern beyond cybersecurity and build a
**general-purpose, dynamically discoverable skill ecosystem** for the
entire multi-agent system.

## Source

-   https://github.com/mukul975/Anthropic-Cybersecurity-Skills
