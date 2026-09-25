# Knowledge Course → Skills Knowledge Base

## 1. Objective

Use high-value external courses and learning resources as **seed knowledge** for a reusable AI product-building system.

Instead of depending on external course links remaining available forever, an AI knowledge-acquisition pipeline should:

**Acquire → Read → Understand → Extract → Structure → Validate → Convert to Skills → Store → Index → Reuse**

The resulting knowledge becomes a durable internal **Skills + Knowledge Base** that product-building agents can use whenever relevant.

The goal is not to reproduce courses verbatim. The goal is to capture their useful concepts, methodologies, principles, patterns, checklists, examples, and practical procedures in a form that AI agents can actually apply.

---

## 2. Core Principle

Do not treat a course as a giant text file.

Treat it as a structured source of **operational knowledge**.

### Weak approach

```text
Course
  ↓
Huge summary
  ↓
Put everything into agent context
  ↓
Build product
```

Problems:

- Large token consumption
- Poor retrieval
- Difficult to reuse
- Knowledge becomes mixed together
- Agents may quote information instead of applying it
- Difficult to validate and update

### Recommended approach

```text
Course
  ↓
Course ingestion
  ↓
Module / lesson understanding
  ↓
Concept extraction
  ↓
Method / principle extraction
  ↓
Skill generation
  ↓
Validation / critique
  ↓
Structured Knowledge + Skills KB
  ↓
Knowledge Router
  ↓
Relevant agent
```

---

# 3. Candidate Course Domains

The Google course collection can provide useful seed knowledge across multiple product-building disciplines:

| Course / Domain | Useful knowledge for product building |
|---|---|
| Cybersecurity | Threat modeling, IAM, security controls, incident response, secure practices |
| Business Intelligence | KPIs, dashboards, reporting, business insights |
| Advanced Data Analytics | Statistics, regression, experimentation, advanced analysis |
| Digital Marketing | Acquisition, SEO, campaigns, analytics, growth |
| AI & Machine Learning | ML concepts, model development, evaluation, AI workflows |
| Data Analytics | Data cleaning, SQL, analysis, visualization |
| Project Management | Requirements, planning, risks, dependencies, delivery |
| UX Design | User research, personas, journeys, wireframes, usability |
| IT Automation | Automation, scripting, Python, operational workflows |
| IT Support | Systems, networking, troubleshooting, IT operations |

These are **seed domains**, not the limit of the architecture. Additional courses, books, documentation, repositories, standards, internal company knowledge, and other authoritative resources can be added later.

> Note: Before ingestion, verify current course access, licensing, and whether the material may legally be downloaded, processed, stored, and transformed. A public URL does not automatically grant rights to reproduce course content.

---

# 4. Knowledge Acquisition Pipeline

The recommended system separates **knowledge acquisition** from **knowledge execution**.

```text
                         SOURCE
                           │
                           ▼
                  ┌─────────────────┐
                  │ Acquisition      │
                  │ Agent            │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │ Course Parser    │
                  │ / Reader         │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │ Learning /       │
                  │ Understanding    │
                  │ Agent            │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │ Knowledge        │
                  │ Extractor        │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │ Skill Generator  │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │ Critic /         │
                  │ Validator        │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │ Knowledge +      │
                  │ Skills KB        │
                  └─────────────────┘
```

## Acquisition Agent

Responsible for:

- Locating the authorized course material
- Capturing course/module/lesson structure
- Recording source metadata
- Processing the material in manageable chunks
- Detecting missing or inaccessible sections
- Maintaining provenance

## Learning / Understanding Agent

Responsible for understanding:

- Concepts
- Definitions
- Principles
- Relationships between concepts
- Methodologies
- Examples
- Exercises
- Practical applications
- Prerequisites
- Limitations

## Knowledge Extractor

Converts learning material into structured knowledge.

Extract:

- Concepts
- Principles
- Methods
- Frameworks
- Patterns
- Best practices
- Anti-patterns
- Checklists
- Decision rules
- Examples
- Common mistakes
- Validation criteria

## Skill Generator

Transforms applicable knowledge into reusable agent skills.

## Critic / Validator

Reviews the extracted knowledge before it enters the trusted KB.

Questions include:

- Is the extracted knowledge supported by the source?
- Is it actually useful?
- Is the procedure complete?
- Are prerequisites missing?
- Are assumptions clearly identified?
- Is this fact, methodology, opinion, or example?
- Can another agent execute this skill?
- Are there contradictions?
- Is the knowledge outdated?
- Does the skill have clear inputs and outputs?

---

# 5. Skills vs Knowledge

These should be separate but connected.

## Knowledge

Answers:

> **What do we know?**

Examples:

- What is threat modeling?
- What are common usability principles?
- What statistical methods are appropriate for a given problem?
- What are common dashboard KPIs?

## Skill

Answers:

> **How should an agent perform this task?**

Example:

```yaml
skill: threat_modeling

when_to_use:
  - new_product
  - major_architecture_change
  - security_sensitive_feature

inputs:
  - product_requirements
  - architecture
  - data_flows
  - trust_boundaries

process:
  - identify_assets
  - identify_threats
  - identify_attack_surfaces
  - assess_risk
  - propose_mitigations
  - prioritize_controls

outputs:
  - threat_model
  - risk_register
  - recommended_controls

validation:
  - assets_are_identified
  - trust_boundaries_are_defined
  - major_attack_surfaces_are_reviewed
  - mitigations_are_actionable
```

The same pattern can be used for UX research, data cleaning, dashboard design, statistical analysis, project planning, security review, ML evaluation, and other domains.

---

# 6. Recommended Knowledge Base Structure

```text
knowledge/
│
├── domains/
│   ├── cybersecurity/
│   ├── data-analytics/
│   ├── advanced-data-analytics/
│   ├── business-intelligence/
│   ├── ai-ml/
│   ├── ux/
│   ├── project-management/
│   ├── digital-marketing/
│   ├── it-support/
│   └── it-automation/
│
├── skills/
│   ├── ux/
│   │   ├── user-research/
│   │   ├── persona-generation/
│   │   ├── journey-mapping/
│   │   ├── usability-testing/
│   │   └── ux-review/
│   │
│   ├── cybersecurity/
│   │   ├── threat-modeling/
│   │   ├── security-review/
│   │   ├── iam-review/
│   │   └── incident-response/
│   │
│   ├── data/
│   │   ├── data-cleaning/
│   │   ├── sql-analysis/
│   │   ├── statistical-analysis/
│   │   └── dashboard-design/
│   │
│   └── project-management/
│       ├── requirements/
│       ├── planning/
│       ├── risk-analysis/
│       └── delivery-review/
│
├── playbooks/
├── checklists/
├── patterns/
├── anti-patterns/
├── examples/
├── concepts/
└── sources/
```

This structure should evolve as more courses and sources are added.

---

# 7. Preserve Source Provenance

Even after knowledge has been extracted, preserve the original source metadata.

Example:

```yaml
skill: threat_modeling

domain: cybersecurity

source:
  provider: Google
  course: <course name>
  source_url: <original URL>
  module: <module name>
  lesson: <lesson name>

extracted_from:
  - concept
  - methodology
  - example
  - exercise

knowledge:
  ...

usage:
  when_to_use:
  inputs:
  process:
  outputs:

validation:
  ...

metadata:
  created_at:
  last_verified:
  version:
```

This provides two benefits:

1. The internal KB remains useful even if the external link later disappears.
2. Agents can trace important knowledge back to its origin when deeper verification is required.

---

# 8. Four-Level Knowledge Architecture

Use progressive depth rather than loading everything into the agent.

```text
Level 1 — Knowledge Index
"What knowledge exists?"

        ↓

Level 2 — Skill / Playbook
"How do I perform this?"

        ↓

Level 3 — Detailed Knowledge
"What are the concepts, reasoning, and evidence?"

        ↓

Level 4 — Source Material
"Where did this knowledge originate?"
```

This enables efficient retrieval.

### Example

An agent needs to perform a UX review:

```text
Product task
   ↓
Knowledge Router
   ↓
Find UX Review skill
   ↓
Load skill
   ↓
Execute review
   ↓
Need more detail?
   ↓
Retrieve relevant UX concepts
   ↓
Still uncertain?
   ↓
Retrieve source material
```

The agent does **not** need the entire UX course in its context.

---

# 9. Knowledge Router

The Knowledge Router determines what information an agent needs for the current task.

Example:

```text
User:
"Build an AI-powered financial dashboard."

                    ↓

             Knowledge Router

       ┌────────────┼────────────┐
       ▼            ▼            ▼
      UX          Data/BI       AI/ML
       │            │            │
       ▼            ▼            ▼
 Dashboard UX    KPIs       Model evaluation

       ┌────────────┼────────────┐
       ▼            ▼            ▼
 Security       Analytics       PM
       │            │            │
       ▼            ▼            ▼
 IAM/security   Statistics    Requirements
```

The router retrieves only the relevant skills and supporting knowledge.

---

# 10. Integration with a Multi-Agent Product System

The knowledge system should be separated from the execution agents.

```text
                  PRODUCT REQUEST
                         │
                         ▼
                ┌──────────────────┐
                │  Orchestrator    │
                └────────┬─────────┘
                         │
                         ▼
                ┌──────────────────┐
                │ Knowledge Router │
                └────────┬─────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
    UX Skills       Security Skills    Data/AI Skills
        │                │                │
        ▼                ▼                ▼
     UX Agent        Security Agent    Data/AI Agent
        │                │                │
        └────────────────┼────────────────┘
                         ▼
                  Product Architecture
                         │
                         ▼
                    Implementation
                         │
                         ▼
                  Validation / Review
```

The same Knowledge Base can be used by:

- A single agent
- A multi-agent system
- OpenCode
- Other coding agents
- Research agents
- Product/UX agents
- Automated workflows

**Multi-agent architecture is not required for the Knowledge Base.**

It simply becomes more valuable when multiple specialized agents need the same shared knowledge.

---

# 11. Relationship to OpenCode / Agent Skills

The knowledge system should provide reusable skills that an OpenCode-style agent system can load when needed.

Conceptually:

```text
OpenCode / Agent Runtime
        │
        ├── Orchestrator
        ├── Coding Agent
        ├── Research Agent
        ├── Review Agent
        └── Knowledge Router
                   │
                   ▼
            Skills Knowledge Base
                   │
          ┌────────┼─────────┐
          ▼        ▼         ▼
         UX    Security     Data
          │        │         │
          └────────┼─────────┘
                   ▼
            Relevant Skills
```

The agent should not automatically load every skill.

Skills should be **progressively loaded based on task requirements**.

---

# 12. Token Efficiency

This architecture directly supports efficient use of LLM context.

## Avoid

```text
Agent
 ↓
All 10 courses
 ↓
Huge context
 ↓
Product task
```

## Prefer

```text
Product request
      ↓
Task analysis
      ↓
Identify required domains
      ↓
Retrieve relevant skills
      ↓
Load only necessary knowledge
      ↓
Execute
      ↓
Retrieve deeper knowledge only if necessary
```

This keeps context smaller and makes knowledge retrieval more targeted.

The Knowledge Base therefore complements the broader **LLM/token optimization and orchestration layer** rather than replacing it.

---

# 13. Knowledge Acquisition vs Knowledge Execution

These are different system responsibilities.

## Knowledge Acquisition

Happens periodically or when new sources are added.

```text
External source
   ↓
Acquire
   ↓
Understand
   ↓
Extract
   ↓
Generate skills
   ↓
Critique
   ↓
Publish to KB
```

## Knowledge Execution

Happens whenever a product task is performed.

```text
Product task
   ↓
Determine required knowledge
   ↓
Retrieve skills
   ↓
Retrieve supporting concepts
   ↓
Execute
   ↓
Validate
```

The expensive learning/extraction process can therefore happen once and the resulting skills can be reused many times.

---

# 14. Example: UX Knowledge

A UX course should not simply become a collection of summaries.

It should produce reusable capabilities such as:

```text
user-research
persona-generation
user-journey-mapping
problem-definition
information-architecture
wireframe-review
usability-testing
accessibility-review
UX-evaluation
```

An agent building a new product might automatically invoke:

```text
problem-definition
       ↓
user-research
       ↓
persona-generation
       ↓
journey-mapping
       ↓
information-architecture
       ↓
UX-review
```

---

# 15. Example: Cybersecurity Knowledge

Potential reusable skills:

```text
threat-modeling
security-requirements
authentication-review
authorization-review
IAM-review
data-protection-review
attack-surface-review
secure-architecture-review
incident-response
security-checklist
```

A product containing user accounts and sensitive data could automatically trigger appropriate security skills.

---

# 16. Example: Data / BI Knowledge

Potential reusable skills:

```text
data-requirements
data-cleaning
SQL-analysis
data-quality-review
statistical-analysis
KPI-definition
dashboard-design
dashboard-review
business-insight-generation
```

The agent can apply these during product development instead of merely explaining analytics concepts.

---

# 17. Cross-Domain Intelligence

The biggest value is not the individual courses.

It is the **combination of knowledge across disciplines**.

For example:

> Build an AI-powered financial dashboard.

The system can automatically identify:

```text
AI/ML
  → model selection and evaluation

Data Analytics
  → data cleaning and analysis

Advanced Analytics
  → forecasting/statistics

Business Intelligence
  → KPIs and dashboard design

UX
  → dashboard usability

Cybersecurity
  → authentication, authorization, data protection

Project Management
  → requirements, milestones, risks

IT Automation
  → deployment and operational automation
```

This turns the Knowledge Base into a **cross-functional product engineering intelligence layer**.

---

# 18. Important Quality Rules

The system should distinguish between:

### Facts
Information directly supported by a source.

### Principles
General rules or ideas derived from the material.

### Methods
Repeatable ways of performing a task.

### Skills
Operational procedures an agent can execute.

### Examples
Illustrations that should not automatically become universal rules.

### Opinions
Statements that may require attribution rather than being treated as objective truth.

### Assumptions
Claims requiring validation before application.

This classification reduces hallucinated or overgeneralized knowledge.

---

# 19. Do Not Blindly Trust Extracted Knowledge

The ingestion pipeline itself needs quality control.

Recommended lifecycle:

```text
RAW
 ↓
EXTRACTED
 ↓
STRUCTURED
 ↓
REVIEWED
 ↓
VALIDATED
 ↓
PUBLISHED
 ↓
VERSIONED
```

Only validated knowledge should become trusted reusable skills.

Potential metadata:

```yaml
status: validated
confidence: high
source_verified: true
reviewed_by: knowledge-critic
version: 1.0
last_verified:
```

---

# 20. Updating the Knowledge Base

External courses and technologies can change.

The KB should therefore support:

- Source versioning
- Last-verified timestamps
- Change detection
- Re-ingestion
- Skill versioning
- Deprecation
- Conflict detection
- Source provenance

Example:

```text
Source changes
      ↓
Re-ingestion
      ↓
Compare with existing knowledge
      ↓
Detect changes
      ↓
Update affected concepts
      ↓
Update affected skills
      ↓
Revalidate
      ↓
Publish new version
```

The system can also retain historical versions where useful.

---

# 21. Legal / Access Consideration

The architecture should only ingest and transform material that the system is authorized to access and process.

Do not assume:

```text
Public URL = permission to copy everything
```

The preferred approach is to:

- Use authorized course access
- Respect terms of service and licensing
- Store derived knowledge rather than unnecessary verbatim course content
- Preserve source attribution/provenance
- Avoid redistributing copyrighted course material
- Use public documentation or permissively licensed resources where appropriate

The objective is **knowledge transformation and application**, not unauthorized course redistribution.

---

# 22. Recommended End State

The final architecture should look like:

```text
                     EXTERNAL KNOWLEDGE
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
           Courses      Documentation   Other Sources
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                 KNOWLEDGE ACQUISITION
                            │
                            ▼
                  KNOWLEDGE EXTRACTION
                            │
                            ▼
                     SKILL GENERATION
                            │
                            ▼
                    CRITIC / VALIDATOR
                            │
                            ▼
              ┌─────────────────────────┐
              │ SKILLS + KNOWLEDGE KB   │
              └────────────┬────────────┘
                           │
                    KNOWLEDGE ROUTER
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
           UX Agent    Data/AI Agent   Security Agent
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                   PRODUCT BUILD SYSTEM
                           │
                           ▼
                    VALIDATION / QA
```

---

# 23. Final Recommendation

Yes: **have an AI system go through the courses end-to-end and build an internal Skills Knowledge Base.**

But architect it as a **Knowledge Acquisition + Skills Engineering pipeline**, not as "download courses and put them into RAG."

The preferred model is:

```text
COURSE
  ↓
UNDERSTAND
  ↓
EXTRACT
  ↓
STRUCTURE
  ↓
TURN INTO SKILLS
  ↓
CRITIQUE
  ↓
VALIDATE
  ↓
STORE WITH PROVENANCE
  ↓
INDEX
  ↓
RETRIEVE ONLY WHEN NEEDED
  ↓
APPLY TO PRODUCT DEVELOPMENT
```

This gives the system a durable internal body of cross-disciplinary knowledge while keeping runtime agents efficient.

It also gives us a clean separation between:

1. **Knowledge acquisition**
2. **Knowledge storage**
3. **Knowledge retrieval**
4. **Agent skills**
5. **Multi-agent orchestration**
6. **LLM/token optimization**
7. **Product execution**
8. **Validation**

The Google courses can therefore become the **first seed layer** of a much larger product-building intelligence system, with additional courses, documentation, GitHub repositories, books, standards, and internal organizational knowledge added later.
