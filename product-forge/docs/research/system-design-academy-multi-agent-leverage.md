# System Design Academy → Multi-Agent System Leverage

Source: https://github.com/systemdesign42/system-design-academy

## Executive Summary

**Recommendation: HIGH VALUE — use as an architecture and engineering knowledge source for the multi-agent system.**

System Design Academy is not a multi-agent framework itself. Its value is that it supplies the distributed-systems, reliability, scalability, API, data, infrastructure, and AI-engineering concepts that an advanced multi-agent platform needs.

The repository groups material into:
- System Design Case Studies
- System Design Fundamentals
- System Design Interview
- AI Engineering
- Software White Papers

The AI Engineering section explicitly covers agents, context engineering, agentic design patterns, agent-to-agent protocols, LLM evaluation, AI infrastructure, graph-shaped memory, failure recovery, knowledge Q&A, MCP, multi-agent architectures, agent state/memory/consistency, RAG, research agents, and vector databases.

## What We Should Leverage

### 1. Distributed Systems as the Foundation

Treat every meaningful agent as a distributed-system component rather than simply an LLM prompt.

Use the repository's material on:
- distributed systems
- actor model
- message queues
- Kafka
- RPC
- service discovery
- load balancing
- caching
- consistency patterns
- consistent hashing
- gossip protocols
- high availability
- concurrency
- deployment patterns
- microservices

### Architectural implication

Our multi-agent platform should support:

```text
User / Trigger
      |
      v
Orchestrator
      |
      +---- Agent A
      +---- Agent B
      +---- Agent C
      |
      v
Shared State / Event Bus
      |
      +---- Memory
      +---- Knowledge
      +---- Artifacts
      +---- Observability
      |
      v
Evaluator / Verifier
      |
      v
Result
```

Agents should communicate through explicit contracts and events where appropriate, rather than relying on hidden prompt-to-prompt coupling.

---

## 2. Agent State, Memory and Consistency

One of the most important areas for us is:

**AI Agents: State, Memory, Consistency**

We should separate:

- ephemeral execution state
- durable task state
- working memory
- long-term knowledge
- agent identity/configuration
- artifacts
- event history
- checkpoints

### Required design principle

An agent must be able to stop, resume, retry, or recover without starting the entire task from zero.

This should lead to:

```text
Task
 |
 +--> Checkpoint
 +--> State
 +--> Events
 +--> Artifacts
 +--> Memory
 |
 +--> Resume
```

Do not make the LLM conversation transcript the only source of truth.

---

## 3. Multi-Agent Architecture Patterns

Use the repository's **Multi-Agent Architectures** and **Agentic Design Patterns** material as architectural reference.

We should support several execution patterns rather than forcing every problem into one topology.

### Sequential

```text
Planner -> Researcher -> Builder -> Reviewer
```

### Parallel

```text
             +-> Researcher A --+
Planner -----+-> Researcher B --+-> Synthesizer
             +-> Researcher C --+
```

### Hierarchical

```text
Supervisor
   |
   +-- Planning Agent
   +-- Research Agent
   +-- Coding Agent
   +-- Testing Agent
   +-- Security Agent
```

### Debate / Review

```text
Generator -> Critic -> Generator -> Verifier
```

### Event-driven

```text
Event -> Agent -> Event -> Agent -> Event
```

### Dynamic delegation

```text
Supervisor
    |
    +--> dynamically selects specialist
            |
            +--> executes
            |
            +--> reports result
```

The orchestration layer should select the topology based on task requirements.

---

## 4. Context Engineering

Prioritize **context engineering over prompt accumulation**.

The repository explicitly includes material on context engineering and context engineering vs prompt engineering.

Our agents should receive:

```text
System Instructions
+ Task State
+ Relevant Knowledge
+ Relevant Memory
+ Tool Capabilities
+ Prior Results
+ Constraints
+ Evaluation Criteria
```

Not:

```text
Everything we know
+
Entire conversation
+
Every previous agent output
```

### Context router

Introduce a context-selection layer:

```text
Task
  |
  v
Context Router
  |
  +--> Knowledge retrieval
  +--> Memory retrieval
  +--> Artifact retrieval
  +--> Previous agent results
  +--> Tool/schema information
  |
  v
Minimal useful context
  |
  v
Agent
```

This reduces context pollution and token cost.

---

## 5. Failure Recovery

The repository contains material on building agents that **don't start over when they fail**.

This should become a first-class capability.

Every long-running agent task should have:

- checkpoints
- retry boundaries
- idempotent operations
- partial-result persistence
- failure classification
- recovery strategies
- compensation/rollback where necessary
- resumability

Example:

```text
Task
 |
 +--> Step 1 ✓
 +--> Step 2 ✓
 +--> Step 3 ✗
        |
        +--> classify failure
        |
        +--> retry
        |
        +--> use alternative agent/tool
        |
        +--> resume from Step 3
```

Never blindly restart the entire workflow.

---

## 6. Event-Driven Agent Architecture

Borrow distributed-system ideas from:

- Kafka
- message queues
- webhooks
- WebSockets
- gossip
- actor model

For larger workloads, agents can communicate through an event layer.

Example:

```text
task.created
      |
      v
planner.completed
      |
      +--> research.requested
      +--> implementation.requested
      +--> security.review.requested
      |
      v
validation.completed
      |
      v
task.completed
```

This makes the system more asynchronous and scalable.

---

## 7. Idempotency

The repository's payment architecture material includes the importance of idempotent APIs.

Apply the same principle to agents.

A retried operation should not accidentally:

- create duplicate records
- submit the same deployment twice
- send duplicate messages
- create duplicate artifacts
- charge a user twice
- execute an irreversible tool twice

Use:

```text
operation_id
task_id
step_id
attempt_id
idempotency_key
```

for meaningful operations.

---

## 8. API Contracts Between Agents

Treat agent-to-agent communication like an API.

Each agent should have:

```yaml
agent:
  name:
  purpose:
  inputs:
  outputs:
  tools:
  constraints:
  capabilities:
  failure_modes:
  evaluation:
```

Agent outputs should preferably be structured.

Example:

```json
{
  "status": "completed",
  "summary": "...",
  "artifacts": [],
  "evidence": [],
  "confidence": 0.87,
  "issues": [],
  "next_actions": []
}
```

This is substantially safer than passing unrestricted natural-language blobs between agents.

---

## 9. Service Discovery and Capability Routing

Use the system-design concepts of service discovery and routing for agents.

Instead of hardcoding:

```text
Planner -> ResearchAgentV1
```

use capability-based routing:

```text
Task requirement
      |
      v
Capability Registry
      |
      +--> research
      +--> coding
      +--> security
      +--> data
      +--> testing
      |
      v
Best available agent
```

Agent registry should contain:

- capability
- version
- model
- cost
- latency
- reliability
- permissions
- tools
- domain expertise
- current availability

---

## 10. Reliability and High Availability

Borrow directly from distributed-system thinking.

The multi-agent system should anticipate:

- agent crashes
- model timeouts
- API failures
- tool failures
- rate limits
- malformed outputs
- stale state
- conflicting writes
- unavailable knowledge sources
- network failures

Use:

- timeouts
- retries
- exponential backoff
- circuit breakers
- dead-letter queues
- health checks
- fallback models/agents
- graceful degradation

---

## 11. Caching

Use caching for expensive and repeatable operations.

Potential caches:

```text
Knowledge retrieval cache
LLM response cache
Embedding cache
Tool result cache
Agent capability cache
Planning cache
Evaluation cache
```

But cache only when semantics permit it.

For mutable knowledge or state, define freshness and invalidation rules.

---

## 12. Observability

Treat agent execution like a production distributed system.

Trace:

```text
Task
 └── Workflow
      ├── Agent call
      │    ├── model
      │    ├── prompt/context version
      │    ├── tools
      │    ├── latency
      │    ├── tokens
      │    └── result
      ├── Agent call
      └── Evaluation
```

Record:

- task ID
- workflow ID
- agent ID
- parent agent
- model
- tool calls
- context sources
- latency
- token usage
- cost
- retries
- failures
- evaluation score
- artifacts
- decisions

This is essential for debugging autonomous systems.

---

## 13. Evaluation as a Distributed Control Loop

The repository includes **LLM Evaluation** material.

Do not rely on the agent declaring itself successful.

Use:

```text
Agent
  |
  v
Output
  |
  v
Evaluator
  |
  +--> pass -> continue
  |
  +--> fail -> repair
                  |
                  v
                Agent
```

For important tasks:

```text
Generator
   |
   v
Reviewer
   |
   v
Evaluator
   |
   +--> retry
   +--> revise
   +--> escalate
   +--> approve
```

Evaluation should be measurable and preferably independent of the generating agent.

---

## 14. RAG and Knowledge Architecture

Use the RAG, vector database, graph-shaped memory, and knowledge Q&A material as inputs to the knowledge layer.

Recommended separation:

```text
Knowledge Base
    |
    +--> documents
    +--> concepts
    +--> procedures
    +--> examples
    +--> architecture patterns
    +--> skills
    |
    v
Retrieval Layer
    |
    +--> semantic search
    +--> keyword search
    +--> graph traversal
    +--> metadata filtering
    |
    v
Context Builder
```

The system-design knowledge itself should become retrievable agent knowledge rather than being permanently placed in every agent's context.

---

## 15. MCP and Tool Architecture

The repository includes an MCP deep dive.

Use MCP-style thinking to separate:

```text
Agent reasoning
       |
       v
Tool interface
       |
       v
External capability
```

Agents should not need to understand the internal implementation of every tool.

This supports:

- replaceable tools
- permission boundaries
- reusable capabilities
- standardized interfaces
- easier testing

---

## 16. Case Studies as Architectural Training Data

The large set of company case studies is valuable because it teaches **trade-offs**, not just definitions.

Prioritize examples around:

### Scalability
- Netflix
- Instagram
- LinkedIn
- YouTube
- WhatsApp
- Discord
- Shopify

### Reliability
- Amazon S3
- Netflix chaos engineering
- payment systems

### Data
- Figma/Postgres
- Quora/MySQL sharding
- Google systems
- Dynamo
- Spanner

### Real-time
- gaming leaderboard
- presence
- live comments
- Disney+ Hotstar
- Uber

### Event/task automation
- Zapier

Use these as architectural exemplars when an agent is asked:

> "How should we design this?"

The agent should reason by analogy and trade-off rather than copy an architecture blindly.

---

# Recommended Knowledge-Base Integration

Do **not** simply dump the entire repository into one vector database.

Create structured knowledge domains:

```text
knowledge/
├── system-design/
│   ├── distributed-systems/
│   ├── consistency/
│   ├── concurrency/
│   ├── databases/
│   ├── caching/
│   ├── messaging/
│   ├── networking/
│   ├── APIs/
│   ├── scalability/
│   ├── reliability/
│   ├── microservices/
│   └── case-studies/
│
├── ai-engineering/
│   ├── agents/
│   ├── multi-agent/
│   ├── context-engineering/
│   ├── memory/
│   ├── agent-state/
│   ├── agentic-patterns/
│   ├── evaluation/
│   ├── rag/
│   ├── mcp/
│   ├── ai-infrastructure/
│   └── research-agents/
│
└── architecture-patterns/
    ├── event-driven/
    ├── actor-model/
    ├── saga/
    ├── orchestration/
    ├── choreography/
    ├── fault-tolerance/
    └── observability/
```

---

# How Agents Should Use This Knowledge

The knowledge should be **retrieval-driven**.

Example:

```text
User:
"Build a multi-agent research system."

        |
        v

Architecture Planner
        |
        +--> retrieve multi-agent patterns
        +--> retrieve agent state/memory
        +--> retrieve event-driven architecture
        +--> retrieve distributed systems
        +--> retrieve evaluation
        +--> retrieve RAG
        |
        v
Architecture Proposal
        |
        v
Design Reviewer
        |
        +--> retrieve reliability patterns
        +--> retrieve consistency patterns
        +--> retrieve failure recovery
        |
        v
Validated Architecture
```

The knowledge base should therefore be available to **all agents**, but each agent should retrieve only the subset relevant to its current responsibility.

---

# What NOT to Do

Do not:

1. Turn the entire repository into one giant prompt.
2. Give every agent every article.
3. Treat system-design case studies as copy/paste architectures.
4. Assume multi-agent automatically means better.
5. Add agents when a deterministic function is sufficient.
6. Use shared mutable state without consistency rules.
7. Let agents communicate only through unconstrained prose.
8. Retry non-idempotent operations blindly.
9. Depend on the LLM transcript as durable state.
10. Let an agent be the sole evaluator of its own output.

---

# Priority Matrix

| Area | Priority | Why |
|---|---:|---|
| Distributed systems | P0 | Foundation for scalable agents |
| Agent state/memory/consistency | P0 | Enables resumability and correctness |
| Multi-agent architectures | P0 | Directly relevant |
| Context engineering | P0 | Controls context quality/cost |
| Failure recovery | P0 | Required for autonomous execution |
| Evaluation | P0 | Prevents unreliable autonomous output |
| Event/message architecture | P1 | Enables asynchronous agents |
| API/contracts | P1 | Reliable agent interoperability |
| Observability | P1 | Required for production debugging |
| RAG/knowledge | P1 | Gives agents reusable expertise |
| MCP/tool architecture | P1 | Standardizes capabilities |
| Caching | P1 | Cost/performance |
| Case studies | P1 | Architectural pattern library |
| Interview material | P3 | Low direct value for runtime system |

---

# Core Architectural Principles We Should Adopt

## Principle 1 — Agents are distributed components

Design them like services, not chatbots.

## Principle 2 — State is externalized

Persist state, checkpoints, events and artifacts outside the model context.

## Principle 3 — Context is assembled dynamically

Retrieve only what the current agent needs.

## Principle 4 — Communication is contractual

Use structured inputs/outputs and explicit schemas.

## Principle 5 — Failure is normal

Every long-running workflow must support retry, recovery and resume.

## Principle 6 — Evaluation is independent

Generation and verification should be separate whenever practical.

## Principle 7 — Prefer event-driven execution for long workflows

Do not require one synchronous model call to own an entire workflow.

## Principle 8 — Use capability-based routing

Select agents based on capabilities, not hardcoded names.

## Principle 9 — Architecture is a trade-off

Use case studies to teach reasoning about cost, latency, consistency, reliability and complexity.

## Principle 10 — Multi-agent is a tool, not the default

Use multiple agents when specialization, parallelism, isolation, independent verification or asynchronous execution provides a real benefit.

---

# Final Recommendation

**Add System Design Academy to the core engineering knowledge layer.**

Its highest-value contribution to our multi-agent architecture is not any individual article. It is the combination of:

```text
Distributed Systems
        +
Production Architecture
        +
Reliability
        +
Data/Networking
        +
AI Agents
        +
Context Engineering
        +
Agent Memory/State
        +
Multi-Agent Architecture
        +
Evaluation
        +
MCP
```

This gives our agents the **systems-thinking layer** that many agent frameworks lack.

The goal should be to build an agent system that can reason:

> "What agent topology should I use, what state needs to be durable, how should agents communicate, what happens when one fails, how do I verify the result, and how will this scale?"

rather than simply:

> "Which prompt should I give the next agent?"

## Source

https://github.com/systemdesign42/system-design-academy

The repository currently organizes its material across System Design Case Studies, Fundamentals, Interviews, AI Engineering, and Software White Papers. Its AI section explicitly includes multi-agent architectures, agent state/memory/consistency, context engineering, agentic patterns, evaluation, MCP, RAG, AI infrastructure, and failure recovery. 
