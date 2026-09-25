# Product Factory --- Conversation & Idea Ingestion Architecture

## 1. Purpose

Product Factory should act as the persistent bridge between **thinking
and building**.

Users may think, research, discuss, refine, and make decisions in
ChatGPT, Gemini, Claude, other AI interfaces, or ordinary documents.
They should then be able to move that useful context into Product
Factory without manually copying and pasting it.

The target lifecycle is:

> **Think anywhere → Capture → Understand → Remember → Connect to a
> project → Plan → Build → Verify → Preserve traceability**

The Factory should therefore support two primary intents:

1.  **Save this thinking** --- preserve a conversation as an idea,
    research item, decision, or knowledge.
2.  **Build this** --- use the conversation as project context and turn
    it into requirements, architecture, implementation work, code,
    tests, and verification.

The Factory must preserve both the **original source conversation** and
the **structured knowledge derived from it**.

------------------------------------------------------------------------

# 2. Core Architectural Principle

External AI interfaces are **sources and front doors**.

Product Factory is the **persistent system of record** for product
knowledge, decisions, execution, and verification.

``` text
ChatGPT ───────┐
Gemini ────────┤
Claude ────────┤
Browser ───────┤
Documents ─────┤
Factory Chat ──┤
APIs ──────────┘
       │
       ▼
Factory Context Gateway
       │
       ▼
Conversation / Input Ingestion
       │
       ▼
Conversation Compiler
       │
       ▼
Factory Context
       │
       ├── Idea Database
       ├── Project Context
       ├── Knowledge
       └── Decisions / Requirements
       │
       ▼
Product Factory
       │
       ├── Plan
       ├── Build
       ├── Test
       └── Verify
```

Do **not** make ChatGPT conversation format the internal data model.

Instead, define a canonical internal representation called
**FactoryContext** and create adapters for each external source.

------------------------------------------------------------------------

# 3. Supported Ingestion Channels

Product Factory should support four complementary channels.

## 3.1 AI App / MCP Integration --- Primary

The preferred experience is an explicit action from an AI interface:

-   "Save this to Product Factory."
-   "Save this as an idea."
-   "Add this to Project X."
-   "Use this conversation to implement the feature in Project X."

Conceptually:

``` text
ChatGPT / Gemini / Claude
          │
          ▼
     Factory MCP
          │
          ▼
   Factory Backend
```

The same Factory backend should be reusable across AI providers.

MCP is the preferred integration boundary where supported because it
avoids building a provider-specific backend for every AI interface.

------------------------------------------------------------------------

## 3.2 Browser Companion / Extension --- Universal Bridge

A browser extension can provide an explicit "Send to Factory" action
from supported AI websites.

``` text
ChatGPT / Gemini / Claude webpage
              │
              ▼
      Factory Browser Extension
              │
              ▼
        Factory Intake API
```

Potential actions:

-   Send to Factory
-   Save as Idea
-   Add to Project
-   Build in Factory
-   Attach to existing decision
-   Save as research

The browser connector should be treated as an adapter rather than the
core Factory architecture because external website UIs can change.

The extension should show a user preview before transmission:

``` text
Send to Product Factory

Source:
ChatGPT — Product Factory Architecture

Destination:
AI Product Factory

Action:
Add to project

Captured:
✓ 86 messages
✓ 12 candidate decisions
✓ 8 requirements
✓ 4 open questions

[Cancel] [Send]
```

------------------------------------------------------------------------

## 3.3 Conversation Export / Import --- Fallback and Migration

Historical conversations can be imported through exported data.

``` text
ChatGPT Export
      │
      ▼
Factory Importer
      │
      ▼
ConversationPackage
      │
      ▼
Conversation Compiler
      │
      ▼
FactoryContext
```

This is appropriate for:

-   importing old conversations
-   bulk migration
-   historical idea discovery
-   recovery
-   archival ingestion

It should not be the normal real-time workflow.

------------------------------------------------------------------------

## 3.4 Factory-Native Conversation

Product Factory should eventually have its own conversation interface.

``` text
Factory Chat
     │
     ▼
FactoryContext
     │
     ▼
Project / Idea / Knowledge
```

This removes the need for external integration when users choose to work
directly inside the Factory.

------------------------------------------------------------------------

# 4. Factory Context Gateway

Create a first-class subsystem:

## Factory Context Gateway

Responsibilities:

-   receive external conversations
-   receive individual ideas
-   receive documents and references
-   authenticate sources
-   normalize inputs
-   deduplicate conversations
-   preserve provenance
-   route inputs to the Conversation Compiler
-   attach information to ideas/projects
-   initiate implementation workflows

Suggested adapters:

``` text
Factory Context Gateway
│
├── REST API
├── MCP Server
├── ChatGPT App / Integration
├── Gemini Integration
├── Claude Integration
├── Browser Connector
├── Shared-Link Importer
├── Chat Export Importer
└── Factory-native Chat
```

All adapters produce the same internal representation.

------------------------------------------------------------------------

# 5. Factory Intake API

The canonical entry point should be something like:

``` http
POST /api/v1/intake
```

Example:

``` json
{
  "source": {
    "type": "conversation",
    "platform": "chatgpt",
    "conversation_id": "external-id",
    "source_url": "optional"
  },
  "destination": {
    "type": "project",
    "project_id": "proj_123"
  },
  "intent": "implement",
  "content": {
    "messages": []
  }
}
```

Supported destination types:

``` text
idea
project
knowledge
decision
research
```

Supported intent types:

``` text
idea
research
project_context
implementation
decision
reference
```

The API should also support non-conversation inputs:

``` text
conversation
message
requirement
document
url
github_repo
design
decision
feedback
artifact
```

------------------------------------------------------------------------

# 6. ConversationPackage

Create a first-class entity for imported conversations.

``` text
ConversationPackage
───────────────────
id
tenant_id
user_id

source_platform
source_conversation_id
source_url

captured_at

raw_content
normalized_content

conversation_hash

participants
metadata

compiler_status
```

The original conversation must remain available.

Raw conversation is **evidence**, not merely temporary input.

Associated entities can include:

``` text
Conversation
├── Message
├── Idea
├── Requirement
├── Decision
├── Constraint
├── Assumption
├── Proposal
├── Question
└── Reference
```

------------------------------------------------------------------------

# 7. Conversation Compiler

The Conversation Compiler turns unstructured conversation into durable
Factory knowledge.

Pipeline:

``` text
Raw conversation
       │
       ▼
Normalize
       │
       ▼
Segment
       │
       ▼
Identify user intent
       │
       ▼
Extract candidate knowledge
       │
       ├── Ideas
       ├── Requirements
       ├── Decisions
       ├── Constraints
       ├── Assumptions
       ├── Questions
       ├── Alternatives
       └── References
       │
       ▼
Resolve contradictions
       │
       ▼
Link existing Factory knowledge
       │
       ▼
Produce FactoryContext
```

Use at least two conceptual passes.

### Pass 1 --- Extraction

Determine what the conversation contains.

### Pass 2 --- Adjudication

Determine what the Factory should treat as accepted knowledge, proposed
information, unresolved information, or rejected information.

This prevents AI speculation from silently becoming engineering truth.

------------------------------------------------------------------------

# 8. Preserve Source vs Interpretation

This distinction is fundamental.

If ChatGPT says:

> "You could use PostgreSQL."

Factory records:

``` text
Proposal
PostgreSQL

source: ChatGPT
status: proposed
```

If the user says:

> "Yes, let's use PostgreSQL."

Factory records:

``` text
Decision
PostgreSQL

source: user
status: accepted
```

If Factory's architecture agent recommends it:

``` text
Technical Recommendation
PostgreSQL

source: Factory Architecture Agent
status: recommended
```

Every derived object should carry:

``` text
source
author
confidence
status
provenance
```

------------------------------------------------------------------------

# 9. FactoryContext

Everything downstream should receive structured context rather than
repeatedly receiving the complete transcript.

Example:

``` json
{
  "project": {
    "id": "proj_123"
  },

  "intent": [
    "Add conversational ingestion to Product Factory"
  ],

  "requirements": [],

  "decisions": [],

  "constraints": [],

  "assumptions": [],

  "open_questions": [],

  "proposals": [],

  "source_conversations": [],

  "related_artifacts": []
}
```

Context should be filtered for each agent.

Examples:

``` text
Product Agent
→ product context

Architecture Agent
→ technical context

UX Agent
→ UX context

AI Agent
→ AI/model context

Security Agent
→ security context

Engineering Agent
→ implementation context
```

This integrates with the Factory's agent, skill, knowledge-base,
checklist, and verification architecture.

------------------------------------------------------------------------

# 10. Save-as-Idea Workflow

User says:

> "Save this conversation as an idea."

Flow:

``` text
AI Interface
     │
     ▼
factory.save_idea()
     │
     ▼
Create ConversationPackage
     │
     ▼
Conversation Compiler
     │
     ▼
Generate Idea Candidate
     │
     ▼
Link related existing ideas
     │
     ▼
Idea Database
```

Suggested Idea entity:

``` text
Idea
────
Title
Problem
Opportunity
Summary
Original conversation
Extracted reasoning
Potential users
Potential value
Related ideas
Evidence
Status
```

No implementation should automatically start.

------------------------------------------------------------------------

# 11. Add-to-Project Workflow

User says:

> "Add this discussion to Project X."

Flow:

``` text
Conversation
     │
     ▼
Ingest
     │
     ▼
Compile
     │
     ▼
Retrieve existing Project Context
     │
     ▼
Compare
     │
     ▼
Impact Analysis
     │
     ├── New information
     ├── Changed requirements
     ├── Conflicts
     ├── New decisions
     └── New implementation needs
     │
     ▼
Project Context
```

Adding a conversation must not blindly overwrite existing project
information.

The Factory should identify deltas and conflicts.

------------------------------------------------------------------------

# 12. Build-from-Conversation Workflow

This is the primary execution workflow.

User says:

> "Take this conversation and implement it in Project X."

The Factory should not immediately write code.

Instead:

``` text
Conversation
     │
     ▼
Compile
     │
     ▼
Project comparison
     │
     ▼
Impact analysis
     │
     ▼
Requirement delta
     │
     ▼
Architecture delta
     │
     ▼
Implementation plan
     │
     ▼
Verification plan
     │
     ▼
Human approval
     │
     ▼
Execution
     │
     ▼
Verification
```

Create a **ChangePackage**:

``` text
ChangePackage
─────────────
project
source_conversation

new_requirements
modified_requirements
removed_requirements

architecture_changes

ux_changes

ai_changes

data_changes

security_changes

implementation_tasks

test_tasks

verification_tasks

risks
open_questions
```

------------------------------------------------------------------------

# 13. Human Approval Boundary

Use explicit approval before consequential execution.

``` text
Conversation
     │
     ▼
Analysis
     │
     ▼
Implementation Plan
     │
     ▼
────────────────────
   HUMAN APPROVAL
────────────────────
     │
     ▼
Execution
     │
     ▼
Verification
```

Higher-risk actions should require explicit authorization:

``` text
production deployment
database migration
billing changes
security changes
permissions changes
destructive operations
```

Lower-risk operations may eventually be automated according to project
policy.

------------------------------------------------------------------------

# 14. MCP Server Design

Expose a small set of high-level Factory tools rather than exposing
every internal function.

## Context

``` text
factory.search
factory.get_project_context
factory.get_idea
```

## Ingestion

``` text
factory.ingest_conversation
factory.save_idea
factory.attach_context
```

## Planning

``` text
factory.analyze_impact
factory.create_change_plan
```

## Execution

``` text
factory.execute_change
factory.run_phase
```

## Verification

``` text
factory.run_verification
factory.get_quality_report
```

## Artifacts

``` text
factory.get_artifact
factory.create_artifact
```

The external AI should interact with these high-level capabilities,
while the Factory internally orchestrates its agents, skills, tools,
models, queues, and verification.

------------------------------------------------------------------------

# 15. Long-Running Factory Tasks

Building a feature may take minutes or longer.

Do not keep an MCP request synchronously open for the entire workflow.

Instead:

``` text
factory.execute_change()
       │
       ▼
Task ID
       │
       ▼
Factory Orchestrator
       │
       ├── Product Agent
       ├── Architecture Agent
       ├── Coding Agent
       ├── Test Agent
       └── Verification Agent
```

Represent the task as:

``` text
Task
├── id
├── status
├── progress
├── current_phase
├── artifacts
├── blockers
└── result
```

The external interface can query task state and retrieve results.

------------------------------------------------------------------------

# 16. Authentication and Authorization

Never give an external AI a Factory master API key.

Use user-scoped authorization.

``` text
ChatGPT
   │
   ▼
OAuth / MCP Authorization
   │
   ▼
Factory Identity Layer
   │
   ▼
User-scoped token
   │
   ▼
Factory Authorization
```

Potential scopes:

``` text
factory:read
factory:write
factory:ideas
factory:projects
factory:execute
factory:deploy
```

For example, an integration may be allowed to:

``` text
read project
save idea
create plan
```

but not:

``` text
deploy production
```

unless explicitly authorized.

------------------------------------------------------------------------

# 17. ChatGPT Integration

The Factory should be exposed as a ChatGPT-compatible app/MCP service
where supported.

Desired interaction:

``` text
User:
"Save this discussion to Product Factory."
```

The AI invokes:

``` text
factory.save_idea(...)
```

Or:

``` text
User:
"Add this to my AI Billing project."
```

The AI invokes:

``` text
factory.attach_context(...)
```

Or:

``` text
User:
"Use everything we've discussed here to implement this in Project X."
```

The AI invokes the appropriate ingestion and planning operations.

The integration should remain explicitly user-directed rather than
assuming unrestricted access to all ChatGPT conversations.

------------------------------------------------------------------------

# 18. Gemini and Other AI Interfaces

Use the same Factory MCP backend wherever the AI interface supports
compatible remote MCP/tool integration.

Conceptually:

``` text
                     Factory MCP
                         │
          ┌──────────────┼──────────────┐
          │              │              │
       ChatGPT         Gemini         Claude
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼
                  Same Factory
```

Do not create separate Factory business logic for each provider.

Build thin provider adapters around the common Factory interface.

------------------------------------------------------------------------

# 19. Browser Extension Architecture

The browser connector should be a separate adapter.

``` text
Browser Extension
       │
       ├── ChatGPT adapter
       ├── Gemini adapter
       ├── Claude adapter
       └── Generic adapter
       │
       ▼
Conversation extraction
       │
       ▼
User preview
       │
       ▼
Factory Intake API
```

The extension should explicitly capture only the conversation/context
selected by the user.

Avoid relying on undocumented provider APIs.

------------------------------------------------------------------------

# 20. Database Architecture

Start with a relational core.

Recommended:

``` text
PostgreSQL
```

Core entities:

``` text
users
projects
ideas
conversations
messages
requirements
decisions
constraints
assumptions
proposals
artifacts
change_packages
tasks
sources
provenance
```

For semantic retrieval:

``` text
PostgreSQL + pgvector
```

Do not start with a separate graph database unless real Factory usage
demonstrates that a graph database is necessary.

------------------------------------------------------------------------

# 21. Provenance and Traceability

Every derived object should be traceable back to its source.

Example:

``` text
Requirement R-183
       │
       ├── source: Conversation C-72
       ├── source messages: 31, 35, 41
       ├── extracted by: Conversation Compiler
       ├── confirmed by: user
       └── implemented by: Change C-91
```

Then:

``` text
Feature F-27
     │
     ▼
Requirement R-183
     │
     ▼
Decision D-42
     │
     ▼
Conversation C-72
     │
     ▼
Original discussion
```

This provides end-to-end traceability:

``` text
Idea
 ↓
Conversation
 ↓
Decision
 ↓
Requirement
 ↓
Architecture
 ↓
Code
 ↓
Test
 ↓
Verification
```

------------------------------------------------------------------------

# 22. Preserve Observable Reasoning, Not Hidden Chain-of-Thought

The Factory should not attempt to capture private/internal model
chain-of-thought.

Instead preserve observable reasoning artifacts:

``` text
User statements
Assistant proposals
Alternatives discussed
Explicit rationale
Decisions
Rejected approaches
Requirements
Constraints
Questions
References
Final instructions
```

The Factory can then perform its own explicit analysis and record its
own reasoning artifacts.

This is more auditable and more appropriate for engineering
traceability.

------------------------------------------------------------------------

# 23. Continuous Project Association

The Factory should eventually associate multiple conversations with a
project over time.

Instead of:

``` text
Project
├── Chat 1
├── Chat 2
├── Chat 3
├── Chat 4
└── Chat 5
```

organize them around project knowledge:

``` text
Project
│
├── Ideas
├── Requirements
├── Decisions
├── Research
├── Conversations
├── Architecture
├── Implementation
└── Verification
```

Each conversation can contribute to one or more Factory objects.

Example:

``` text
ChatGPT Chat #37
       │
       ├── Requirement R-184
       ├── Decision D-52
       ├── Idea I-91
       └── Architecture Proposal A-12
                         │
                         ▼
                   Implementation
                         │
                         ▼
                       Tests
                         │
                         ▼
                   Verification
```

------------------------------------------------------------------------

# 24. Reverse Traceability

The Factory should also work in reverse.

User can ask:

> "Why did we build this feature this way?"

The Factory should retrieve:

``` text
Feature
 ↓
Implementation
 ↓
Architecture Decision
 ↓
Requirement
 ↓
Source Conversation
```

Or:

> "What did we previously discuss about AI billing?"

The Factory searches its conversation archive and returns the relevant
discussions and derived knowledge.

This turns the Factory into a persistent product memory system.

------------------------------------------------------------------------

# 25. Product Factory Top-Level Architecture

The existing Factory architecture should be extended as follows:

``` text
PRODUCT FACTORY
│
├── 01 Context Gateway
│   ├── AI integrations
│   ├── MCP
│   ├── Browser
│   ├── Imports
│   └── Factory Chat
│
├── 02 Knowledge & Memory
│   ├── Ideas
│   ├── Requirements
│   ├── Decisions
│   ├── Research
│   └── Provenance
│
├── 03 Product Intelligence
│   ├── Product
│   ├── UX
│   ├── Business
│   └── AI Strategy
│
├── 04 Engineering
│   ├── Architecture
│   ├── Code
│   ├── Data
│   ├── Infrastructure
│   └── Security
│
├── 05 Agent System
│   ├── Agents
│   ├── Skills
│   ├── Knowledge
│   └── Model Routing
│
├── 06 Execution
│   ├── Plans
│   ├── Tasks
│   ├── Builds
│   └── Deployments
│
├── 07 Verification
│   ├── Factory Checklist
│   ├── Independent Verification
│   ├── Tests
│   ├── Security
│   └── Quality Gates
│
└── 08 Traceability
    ├── Idea → Requirement
    ├── Requirement → Decision
    ├── Decision → Architecture
    ├── Architecture → Code
    ├── Code → Tests
    └── Everything → Source Conversation
```

------------------------------------------------------------------------

# 26. Implementation Roadmap

Build in this order.

## Phase 1 --- Factory Context Model

Implement:

``` text
FactoryContext
ConversationPackage
Provenance
Idea
Decision
Requirement
ChangePackage
```

## Phase 2 --- Intake API

Implement:

``` text
POST /api/v1/intake
GET /api/v1/conversations/:id
GET /api/v1/ideas/:id
POST /api/v1/projects/:id/context
```

## Phase 3 --- Conversation Compiler

Implement:

``` text
raw conversation
→ normalized
→ extracted
→ adjudicated
→ FactoryContext
```

## Phase 4 --- Project Impact Engine

Implement:

``` text
FactoryContext
→ existing project
→ delta analysis
→ ChangePackage
```

## Phase 5 --- MCP Server

Expose Factory capabilities to external AI systems.

## Phase 6 --- ChatGPT Integration

Build the supported ChatGPT app/MCP interface.

## Phase 7 --- Gemini / Other AI Integrations

Reuse the same Factory MCP interface wherever supported.

## Phase 8 --- Browser Companion

Implement the universal browser-based bridge.

## Phase 9 --- Bulk Import

Support:

``` text
ChatGPT exports
Gemini exports
Markdown
JSON
PDF
documents
```

## Phase 10 --- Full Think-to-Product Loop

``` text
Think
 ↓
Capture
 ↓
Understand
 ↓
Remember
 ↓
Connect
 ↓
Plan
 ↓
Approve
 ↓
Build
 ↓
Verify
 ↓
Trace
```

------------------------------------------------------------------------

# 27. Recommended Priority

The recommended priority is:

  ------------------------------------------------------------------------
  Component                                 Priority Reason
  --------------------- ---------------------------- ---------------------
  FactoryContext                                  P0 Canonical internal
                                                     model

  ConversationPackage                             P0 Preserve source
                                                     evidence

  Intake API                                      P0 Stable integration
                                                     boundary

  Conversation Compiler                           P0 Turns conversations
                                                     into useful knowledge

  Provenance                                      P0 Prevents loss of
                                                     source/decision
                                                     traceability

  Project Impact Engine                           P0 Enables conversation
                                                     → implementation

  MCP Server                                      P1 Best external AI
                                                     integration boundary

  ChatGPT App                                     P1 High-value
                                                     conversational
                                                     workflow

  Gemini integration                              P1 Same common Factory
                                                     interface

  Browser Extension                               P1 Universal fallback

  Export Importer                                 P2 Historical/bulk
                                                     migration

  Factory-native Chat                             P2 Integrated native
                                                     experience

  Advanced Knowledge                              P3 Add only when
  Graph                                              justified by usage
  ------------------------------------------------------------------------

------------------------------------------------------------------------

# 28. Target User Experience

The desired experience is:

``` text
User is thinking with ChatGPT
          │
          ▼
40-message discussion
          │
          ▼
"Send to Product Factory → Save as Idea"
          │
          ▼
Idea preserved
          │
          │
          ▼
Weeks later:
"Use that idea in Project X"
          │
          ▼
Factory retrieves:
├── Original conversation
├── Extracted reasoning
├── Requirements
├── Decisions
├── Constraints
└── Related Factory knowledge
          │
          ▼
Impact Analysis
          │
          ▼
Change Package
          │
          ▼
User Approval
          │
          ▼
Factory Agents
          │
          ▼
Implementation
          │
          ▼
Testing
          │
          ▼
Independent Verification
          │
          ▼
Traceability
```

The user should never need to manually reconstruct the context by
copying dozens of messages.

------------------------------------------------------------------------

# 29. Strategic Outcome

The resulting Product Factory is more than a product-generation engine.

It becomes:

> **A persistent product knowledge, decision, and execution system that
> can receive ideas and work from any AI interface and turn them into
> verified product changes.**

The Factory remembers:

-   where an idea originated
-   what was discussed
-   what alternatives were considered
-   what the user actually decided
-   what requirements resulted
-   how architecture evolved
-   what was implemented
-   how it was tested
-   how it was verified

The central chain becomes:

``` text
THINK
  ↓
CAPTURE
  ↓
UNDERSTAND
  ↓
REMEMBER
  ↓
CONNECT
  ↓
PLAN
  ↓
BUILD
  ↓
VERIFY
  ↓
TRACE
```

This **Context Gateway + Conversation Compiler + FactoryContext +
Provenance + Project Impact Engine** should therefore be treated as a
foundational Product Factory subsystem, alongside agents, skills,
knowledge bases, engineering checklists, execution, and independent
verification.
