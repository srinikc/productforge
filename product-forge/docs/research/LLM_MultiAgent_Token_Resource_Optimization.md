# LLM + Multi-Agent Token & Resource Optimization

## Practical Architecture --- Separate from ULMI and UAR

### Purpose

This document defines the **practical optimization layer** for a
multi-agent AI system using knowledge of:

-   LLM model capabilities
-   token behavior and token economics
-   context-window constraints
-   inference/request patterns
-   tool-call behavior
-   caching
-   model selection
-   agent orchestration
-   parallel execution
-   memory and artifact handling
-   cost, latency and quality

**ULMI (Universal LLM Interface)** and **UAR (Universal Agent Runtime)**
are intentionally kept separate as future standardization proposals.

The immediate objective is simpler:

> Build a multi-agent system that intelligently uses LLMs and minimizes
> unnecessary tokens, requests, tool calls, latency and cost while
> preserving required quality.

------------------------------------------------------------------------

# 1. Scope

## Included

``` text
LLM Models
     +
Multi-Agent Orchestration
     +
Token Optimization
     +
Request Optimization
     +
Context Optimization
     +
Model Capability Matching
     +
Tool Optimization
     +
Caching
     +
Memory / Artifact Strategy
     +
Cost / Latency / Quality Control
```

## Explicitly separate

``` text
ULMI
Universal LLM Interface
        ↓
Future interoperability standard

UAR
Universal Agent Runtime
        ↓
Future standardized runtime architecture
```

They should not be required dependencies for the first implementation.

------------------------------------------------------------------------

# 2. Core Architecture

``` text
                         USER
                           |
                           v
                 MULTI-AGENT ORCHESTRATOR
                           |
             +-------------+-------------+
             |             |             |
          Planner       Research       Coding
           Agent          Agent         Agent
             |             |             |
             +-------------+-------------+
                           |
                           v
                OPTIMIZATION CONTROLLER
                           |
       +-------------------+-------------------+
       |                   |                   |
       v                   v                   v
  TOKEN/CONTEXT        MODEL CAPABILITY    EXECUTION
   OPTIMIZER              ROUTER           OPTIMIZER
       |                   |                   |
       +-------------------+-------------------+
                           |
                           v
                    LLM MODEL LAYER
                           |
       +-------------------+-------------------+
       |                   |                   |
     OpenAI            Anthropic          DeepSeek
       |                   |                   |
     Gemini              Qwen          Llama / OSS
       |                   |                   |
       +-------------------+-------------------+
                           |
                    Local Models
```

The optimization controller is the important practical component.

------------------------------------------------------------------------

# 3. The Optimization Objective

The system should optimize four major resources simultaneously:

``` text
                QUALITY
                   ^
                   |
                   |
 COST <-------- OPTIMIZER --------> LATENCY
                   |
                   |
                TOKENS
```

The target is not simply:

> Use the fewest tokens.

The target is:

> **Use the minimum computation required to achieve the required quality
> within the available cost and latency constraints.**

------------------------------------------------------------------------

# 4. What the Optimizer Knows

The optimizer maintains knowledge about every configured model.

## Model capability profile

``` text
model
provider
context_window
input_token_cost
output_token_cost
cached_input_cost
reasoning_capability
vision_capability
audio_capability
tool_calling
structured_output
streaming
parallel_tool_support
coding_capability
latency_profile
availability
rate_limits
```

Example:

``` yaml
model:
  provider: example-provider
  name: example-model

  capabilities:
    reasoning: high
    coding: high
    vision: yes
    tool_calling: yes
    structured_output: yes

  limits:
    context_tokens: 128000

  economics:
    input_cost: ...
    output_cost: ...
    cached_input_cost: ...

  performance:
    latency: medium
```

The values must come from current provider/model information rather than
assumptions.

------------------------------------------------------------------------

# 5. Agent Requirements

Agents should describe what they need rather than always specifying a
model.

Example:

``` yaml
agent:
  name: research_agent

  requirements:
    reasoning: medium
    web: true
    structured_output: true

  context:
    preferred_tokens: 30000
    maximum_tokens: 50000

  execution:
    max_turns: 8
    max_tool_calls: 20

  budget:
    max_cost: 2.00

  quality:
    minimum_confidence: 0.80
```

The optimizer then chooses an appropriate model.

------------------------------------------------------------------------

# 6. Model Selection

The decision should consider:

``` text
Required capability
Context size
Task complexity
Quality requirement
Cost
Latency
Tool support
Modality
Current availability
Remaining task budget
```

Conceptually:

``` text
                 AGENT TASK
                     |
                     v
             REQUIREMENT ANALYZER
                     |
                     v
              MODEL CANDIDATES
                     |
       +-------------+-------------+
       |             |             |
     Cheap         Medium        Strong
       |             |             |
       +-------------+-------------+
                     |
                     v
              CAPABILITY FIT
                     |
                     v
             COST / QUALITY
                ANALYSIS
                     |
                     v
                BEST FIT
```

The rule should be:

> **Choose the cheapest model that is sufficiently capable for the
> current step.**

Not:

> Always use the strongest model.

------------------------------------------------------------------------

# 7. Task Complexity Routing

A simple first version:

``` text
                    TASK
                     |
                     v
              COMPLEXITY CHECK
               /      |       \
              /       |        \
          Simple   Moderate   Complex
             |         |          |
          Small      Medium     Strong
           model      model      model
```

Possible categories:

### Simple

-   extraction
-   classification
-   formatting
-   basic summarization
-   deterministic transformation

### Moderate

-   normal research
-   ordinary coding
-   comparison
-   multi-step reasoning

### Complex

-   architecture
-   difficult debugging
-   conflicting evidence
-   complex planning
-   high-risk synthesis

------------------------------------------------------------------------

# 8. Token Optimization Before Every LLM Request

Before sending a request:

``` text
NEW LLM REQUEST
      |
      v
What context is actually required?
      |
      v
Remove irrelevant history
      |
      v
Remove duplicates
      |
      v
Retrieve relevant memory
      |
      v
Compress older information
      |
      v
Reference large artifacts
      |
      v
Estimate tokens
      |
      v
Check budget
      |
      v
SEND
```

The model should not automatically receive the entire agent history.

------------------------------------------------------------------------

# 9. Context Budget vs Context Limit

These are different.

``` text
Preferred context
       ↓
Optimization target

Maximum runtime context
       ↓
Runtime safety ceiling

Model context window
       ↓
Hard physical/provider constraint

Task budget
       ↓
Global resource constraint
```

Example:

``` text
Preferred context = 30K
Runtime maximum  = 40K
Model maximum    = 128K
```

If context reaches 30K, the agent should normally **optimize**, not
stop.

------------------------------------------------------------------------

# 10. Context Overflow Strategy

Suppose:

``` text
Current context = 28K
New information = 15K
Total = 43K
Preferred = 30K
Runtime max = 40K
```

Use:

``` text
43K
 |
 v
Deduplicate
 |
 v
Remove low-value history
 |
 v
Compress old content
 |
 v
Convert repeated prose → structured state
 |
 v
Move large content → artifact store
 |
 v
Retrieve only relevant sections
 |
 v
Try again
```

If still too large:

``` text
Split task
      |
      +-- Subtask A
      +-- Subtask B
      +-- Subtask C
```

or:

``` text
Use a larger-context capable model
```

or, if necessary:

``` text
Escalate / ask user
```

------------------------------------------------------------------------

# 11. Agent Context Packs

Each agent gets a tailored context package.

``` text
GLOBAL STATE
     |
     +-- User requirements
     +-- Current task
     +-- Relevant memory
     +-- Relevant findings
     +-- Relevant tool results
     +-- Artifact references
             |
             v
       RELEVANCE FILTER
             |
             v
       AGENT CONTEXT PACK
             |
             v
            LLM
```

This prevents context duplication across agents.

------------------------------------------------------------------------

# 12. Agent-to-Agent Token Optimization

Avoid:

``` text
Research Agent
      |
  15,000-token report
      |
Coding Agent
      |
  15,000 tokens added
```

Prefer:

``` text
Research Agent
      |
Structured findings
      |
Artifact Store
      |
Coding Agent
      |
Retrieve only relevant findings
```

Example:

``` json
{
  "finding": "Refresh token handling has an expiry bug",
  "evidence": [
    "auth.py:142",
    "tests/auth_test.py:87"
  ],
  "confidence": 0.94,
  "severity": "high",
  "recommended_action": "modify refresh-token logic"
}
```

Large supporting material remains available through references.

------------------------------------------------------------------------

# 13. Request Optimization

Token savings are not enough.

Reduce unnecessary inference requests.

Bad:

``` text
LLM
 ↓
tool
 ↓
LLM
 ↓
tool
 ↓
LLM
 ↓
tool
 ↓
LLM
```

Better where dependencies permit:

``` text
LLM
 ↓
parallel tools
 ↓
consolidated result
 ↓
LLM
```

Track:

``` text
LLM request count
tool-call count
retry count
agent handoffs
workflow depth
```

------------------------------------------------------------------------

# 14. Tool-Call Optimization

Repeated tool calls should be detected.

Example:

``` text
Agent A → read auth.py
Agent B → read auth.py
Agent C → read auth.py
```

Possible optimization:

``` text
              read auth.py
                    |
               cached result
              /      |      \
             A       B       C
```

Apply to:

-   file reads
-   web searches
-   database queries
-   API calls
-   repository searches
-   OCR
-   document parsing
-   embeddings
-   shell commands

------------------------------------------------------------------------

# 15. Tool Result Compression

A tool may return far more information than the next LLM needs.

Instead of:

``` text
Tool
 ↓
100K tokens
 ↓
LLM
```

use:

``` text
Tool
 ↓
Result Optimizer
 ↓
Relevant findings
Errors
Changed lines
Summary
References
 ↓
LLM
```

Keep the complete tool output available as an artifact when required.

------------------------------------------------------------------------

# 16. Tool Cache

Implement exact-result caching first.

``` text
Request
   |
   v
Cache lookup
   |
 +---+---+
 |       |
 HIT     MISS
 |        |
reuse    execute
          |
          v
        cache
```

Cache keys should consider:

``` text
tool
arguments
environment
permissions
data version
timestamp / TTL
```

Do not reuse stale results when freshness matters.

------------------------------------------------------------------------

# 17. Semantic Cache

A later version can recognize equivalent requests.

For example:

``` text
"Find authentication implementation"

"Locate login logic"

"Where is authentication handled?"
```

can potentially map to one cached result if semantic similarity and
freshness rules permit.

Use semantic caching only after reliable exact caching is working.

------------------------------------------------------------------------

# 18. Parallel Agent Execution

Independent tasks should run concurrently.

Sequential:

``` text
Planner
  ↓
Financial
  ↓
Competitor
  ↓
Risk
  ↓
Final
```

Parallel:

``` text
              Planner
                 |
        +--------+--------+
        |        |        |
        v        v        v
    Financial Competitor Risk
        |        |        |
        +--------+--------+
                 |
                 v
              Final
```

For independent work:

``` text
Total latency ≈ planning + max(parallel tasks) + synthesis
```

rather than the sum of every independent task.

------------------------------------------------------------------------

# 19. Dependency-Aware Orchestration

Parallelization should be based on dependencies.

``` text
             TASK
              |
        +-----+-----+
        |     |     |
        A     B     C
        |     |
        +--+--+
           |
           D
           |
           E
```

A, B and C can potentially run concurrently.

D must wait for its dependencies.

E waits for D.

This is where the multi-agent graph itself becomes an optimization
mechanism.

------------------------------------------------------------------------

# 20. Deterministic Work Should Not Use an LLM

Before invoking a model, ask:

> Can ordinary code do this?

Use deterministic code for:

-   parsing
-   counting
-   sorting
-   filtering
-   schema validation
-   hashing
-   file metadata
-   simple transformations
-   duplicate detection
-   arithmetic
-   state comparisons

``` text
TASK
 |
 +-- deterministic? --> CODE
 |
 +-- semantic? -------> LLM
```

This can remove large numbers of unnecessary model requests.

------------------------------------------------------------------------

# 21. Adaptive Reasoning

Reasoning capability should be treated as a resource.

``` text
Task difficulty
      |
      v
Reasoning requirement
      |
 +----+------+ 
 |           |
Low         High
 |           |
efficient   stronger
model       reasoning model
```

Do not automatically spend maximum reasoning on simple tasks.

Use stronger reasoning when:

-   complexity is high
-   evidence conflicts
-   the task is high impact
-   previous attempts fail
-   validation detects uncertainty

Exact controls depend on the model/provider.

------------------------------------------------------------------------

# 22. Escalation Strategy

Start economically.

``` text
             TASK
               |
               v
        Efficient model
               |
       +-------+-------+
       |               |
    sufficient       insufficient
       |               |
    accept          validate
                       |
                  +----+----+
                  |         |
               pass       fail
                  |         |
                accept   stronger model
```

This creates a **progressive compute strategy**.

------------------------------------------------------------------------

# 23. Confidence and Risk

Use confidence as one routing signal, but do not blindly trust
self-reported model confidence.

Better:

``` text
Model confidence
+
Evidence quality
+
Validation result
+
Task risk
+
Historical performance
```

Then decide:

``` text
Low risk + adequate result
        → accept

Medium risk
        → validate

High risk / weak evidence
        → independent check / stronger model
```

------------------------------------------------------------------------

# 24. Critic Optimization

Do not run a critic after every response.

``` text
Agent output
     |
     v
Risk classifier
   /       \
 low       high
  |          |
accept     critic
```

Examples:

  Task                 Validation
  -------------------- --------------------------
  Formatting           None
  Simple extraction    Lightweight
  Coding               Tests
  Architecture         Review
  Financial analysis   Independent verification
  Critical decision    Strong verification

------------------------------------------------------------------------

# 25. Loop Detection

Multi-agent systems can become expensive through repeated loops.

Example:

``` text
A → B → A → B → A → B
```

Detect:

-   repeated task
-   repeated tool call
-   repeated error
-   repeated output
-   no state change
-   identical retrieval
-   oscillating decisions

Then:

``` text
STOP
OR
ESCALATE
OR
CHANGE MODEL
OR
CHANGE STRATEGY
```

------------------------------------------------------------------------

# 26. State-Change Detection

After an action:

``` text
Before state
     |
   action
     |
After state
     |
Changed meaningfully?
   /          \
 NO            YES
 |              |
avoid repeat   continue
```

Example:

``` text
Run tests
  ↓
3 failures

Run same tests
  ↓
same 3 failures

Runtime:
No meaningful state change
→ do not blindly repeat
```

------------------------------------------------------------------------

# 27. Context Compression Strategy

Compression should preserve information hierarchy.

``` text
Raw history
    ↓
Remove duplicate content
    ↓
Remove irrelevant content
    ↓
Summarize old discussion
    ↓
Preserve decisions
    ↓
Preserve constraints
    ↓
Preserve unresolved issues
    ↓
Preserve evidence references
    ↓
Compact state
```

Critical information should be stored separately from free-form
summaries.

------------------------------------------------------------------------

# 28. Structured State

Use a state object such as:

``` json
{
  "requirements": [],
  "constraints": [],
  "decisions": [],
  "open_questions": [],
  "evidence": [],
  "artifacts": [],
  "completed_actions": [],
  "failed_actions": [],
  "next_actions": []
}
```

This makes context compaction and agent handoff safer.

------------------------------------------------------------------------

# 29. Memory Strategy

Separate active context from long-term memory.

``` text
             AGENT
               |
       +-------+-------+
       |       |       |
    Context  Memory  Artifacts
      ~30K    large     large
       |       |       |
       +-------+-------+
               |
              LLM
```

Memory hierarchy:

``` text
L0 Current turn
L1 Current agent state
L2 Current task
L3 Workflow state
L4 Project memory
L5 Long-term memory
L6 External knowledge
```

Retrieve only the relevant level.

------------------------------------------------------------------------

# 30. Artifact-Based Architecture

Large information should live outside the active prompt.

Examples:

``` text
artifact://research/company-analysis
artifact://code/auth.patch
artifact://data/customer-analysis
artifact://tests/results
artifact://document/extracted-text
```

Agents pass references instead of copying complete content.

Benefits:

-   lower token usage
-   lower context pressure
-   easier reuse
-   versioning
-   auditing
-   rollback

------------------------------------------------------------------------

# 31. Prompt Construction for Cache Efficiency

Where provider caching supports it, keep stable content stable.

Recommended structure:

``` text
[STABLE SYSTEM]
[STABLE AGENT RULES]
[STABLE TOOL DEFINITIONS]
[STABLE PROJECT CONTEXT]
--------------------------
[DYNAMIC TASK]
[DYNAMIC CONTEXT]
[DYNAMIC TOOL RESULTS]
```

This can improve prefix/cache reuse.

Provider caching behavior is model/provider specific and must be
measured rather than assumed.

------------------------------------------------------------------------

# 32. Token Accounting

Track every LLM request.

Example:

``` text
Agent: Researcher
Model: Example Model

Request #1
Input tokens:          8,500
Cached input tokens:  6,000
Output tokens:         1,200

Request #2
Input tokens:         14,000
Cached input tokens:  9,000
Output tokens:         2,000

TOTAL
Input:                22,500
Cached:               15,000
Output:                3,200
Requests:                  2
```

The system should distinguish:

``` text
input tokens
cached input tokens
output tokens
reasoning tokens, where exposed
```

------------------------------------------------------------------------

# 33. Token Budget Allocation

Do not allocate the same budget to every agent.

Example:

``` text
GLOBAL TASK = 100K token budget

Planner       10K
Research      30K
Coding        35K
Validation    10K
Final         10K
Reserve        5K
```

A dynamic version can reallocate unused budget.

``` text
Coding under budget
       |
       v
Unused allocation
       |
       +--> Research
       +--> Validation
       +--> Final
```

------------------------------------------------------------------------

# 34. Cost Budget

Track cost at multiple levels.

``` text
Global task
   |
   +-- agent budget
   |
   +-- model budget
   |
   +-- provider budget
   |
   +-- tool budget
```

Before an expensive action:

``` text
Remaining budget?
       |
   +---+---+
   |       |
  YES      NO
   |       |
execute   escalate/
          stop
```

------------------------------------------------------------------------

# 35. Latency Optimization

Latency comes from more than model generation.

Track:

``` text
queue latency
model latency
time-to-first-token
generation latency
tool latency
network latency
serialization time
agent waiting time
```

Reduce latency through:

-   parallel tools
-   parallel agents
-   fewer requests
-   cache reuse
-   smaller context
-   faster appropriate models
-   avoiding unnecessary retries

------------------------------------------------------------------------

# 36. Quality-Cost-Latency Tradeoff

The optimizer should not blindly minimize cost.

Think:

``` text
                  QUALITY
                    ^
                    |
             high   |       ●
                    |
                    |
        ●           |
        +-----------+------------> COST
       low
```

The goal is to find a point that satisfies the required quality at
acceptable cost and latency.

------------------------------------------------------------------------

# 37. Recommended Runtime Decision Loop

Before each expensive operation:

``` text
1. Is an LLM actually required?
2. Can deterministic code do it?
3. Can an existing result be reused?
4. Can the task be parallelized?
5. What context is actually required?
6. What context can be removed?
7. Can a tool result be compressed?
8. Which model capability is required?
9. What is the cheapest adequate model?
10. What is the remaining budget?
11. Has this action already been attempted?
12. Did the previous action change state?
13. Is validation required?
14. Should the system escalate?
15. Is another request likely to improve the result?
```

This is the heart of the optimization controller.

------------------------------------------------------------------------

# 38. Recommended Optimization Controller

``` text
                 AGENT ACTION
                      |
                      v
             +------------------+
             | LLM NECESSARY?   |
             +--------+---------+
                      |
              +-------+-------+
              |               |
             NO              YES
              |               |
            CODE       CACHE / REUSE?
                              |
                       +------+------+
                       |             |
                      YES            NO
                       |             |
                     reuse       CAPABILITY
                                  ANALYSIS
                                      |
                                      v
                                MODEL ROUTER
                                      |
                                      v
                              CONTEXT OPTIMIZER
                                      |
                                      v
                               TOKEN ESTIMATOR
                                      |
                                      v
                               BUDGET CHECK
                                      |
                                      v
                                  LLM CALL
                                      |
                                      v
                               OUTPUT ANALYZER
                                      |
                           +----------+----------+
                           |                     |
                       TOOL NEEDED?          FINAL?
                           |                     |
                          YES                   YES
                           |                     |
                    TOOL OPTIMIZER             DONE
                           |
                           v
                     TOOL EXECUTION
                           |
                           v
                    RESULT OPTIMIZER
                           |
                           v
                    STATE / ARTIFACT
                           |
                           v
                    LOOP CONTROLLER
                           |
                      CONTINUE / STOP
```

------------------------------------------------------------------------

# 39. What the Multi-Agent Orchestrator Should Manage

The orchestrator handles:

``` text
task decomposition
agent creation
dependencies
parallelism
agent handoffs
workflow state
completion
failure handling
```

The optimization controller handles:

``` text
model selection
context selection
token budget
request minimization
tool reuse
caching
cost
latency
quality/risk
```

This separation keeps agents simpler.

------------------------------------------------------------------------

# 40. Agent Definition Should Be Declarative

Example:

``` yaml
agent:
  name: coding_agent

  purpose:
    - inspect code
    - implement changes
    - run tests

  requirements:
    coding: high
    tool_calling: true
    reasoning: medium

  context:
    preferred_tokens: 40000
    maximum_tokens: 60000

  execution:
    max_turns: 10
    max_tool_calls: 25

  budget:
    max_cost: 3.00

  quality:
    tests_required: true

  escalation:
    allowed: true
```

The optimizer interprets these requirements.

------------------------------------------------------------------------

# 41. What Happens When an Agent Exceeds Its Preferred Context?

Preferred limit:

``` text
30K
```

At 30K:

``` text
Do not automatically stop.

Instead:
    optimize
    retrieve
    compress
    reference artifacts
```

If the runtime maximum is reached:

``` text
split
or
change model
or
escalate
```

If the physical model limit is reached:

``` text
request must be reduced
or
task must be split
```

------------------------------------------------------------------------

# 42. What Happens When an Agent Needs More Output?

If:

``` text
max output = 5K
```

and the model stops because output is exhausted:

``` text
finish_reason = length
        |
        v
Runtime analyzes:
        |
   +----+----+
   |         |
complete   incomplete
   |         |
 stop      continue?
             |
       only if useful
```

Avoid blindly generating continuation requests.

------------------------------------------------------------------------

# 43. Optimization Metrics

The system should measure:

## Token metrics

``` text
input tokens
cached input tokens
output tokens
reasoning tokens
context size
tokens per successful task
```

## Request metrics

``` text
LLM requests
tool calls
retries
agent handoffs
cache hits
cache misses
```

## Performance

``` text
latency
time-to-first-token
tool duration
workflow duration
parallelism
```

## Economics

``` text
cost per request
cost per agent
cost per task
cost per successful result
```

## Quality

``` text
success rate
validation rate
escalation rate
rework rate
error rate
```

------------------------------------------------------------------------

# 44. Optimization KPIs

Useful dashboard:

``` text
Cost / task
Tokens / task
LLM requests / task
Tool calls / task
Cache hit rate
Context compaction rate
Model escalation rate
Parallelization ratio
Average latency
Task success rate
Rework rate
```

A particularly useful KPI is:

> **Cost per successful completed task**

because minimizing raw tokens can otherwise reduce quality.

------------------------------------------------------------------------

# 45. Optimization Learning Loop

Over time, collect historical data.

``` text
Task
 |
 v
Model selection
 |
 v
Execution
 |
 v
Result
 |
 v
Quality / cost / latency
 |
 v
Telemetry
 |
 v
Optimization data
 |
 v
Improve routing policy
```

Eventually the optimizer can learn:

``` text
Task type X
→ Model A
→ 93% success
→ $0.08
→ 2.4 sec

Task type X
→ Model B
→ 95% success
→ $0.42
→ 4.1 sec
```

Then choose based on the required quality threshold.

------------------------------------------------------------------------

# 46. Important Principle: Optimize Successful Work

A cheap failed task is not necessarily an optimization.

Example:

``` text
Model A
$0.02
60% success

Model B
$0.10
95% success
```

For a high-value task, Model B may be the better choice.

Therefore:

``` text
Optimization =
Cost + Latency + Tokens
             +
Quality + Reliability
```

------------------------------------------------------------------------

# 47. Recommended Implementation Order

## Phase 1 --- Basic visibility

Implement:

-   model registry
-   token telemetry
-   request telemetry
-   tool-call telemetry
-   cost tracking
-   context-size tracking

## Phase 2 --- Immediate optimization

Implement:

-   context filtering
-   context compaction
-   model routing
-   deterministic-task bypass
-   tool-result compression
-   exact tool caching

## Phase 3 --- Agent graph optimization

Implement:

-   dependency graph
-   parallel agents
-   parallel tools
-   structured agent messages
-   artifact references
-   loop detection
-   state-change detection

## Phase 4 --- Advanced optimization

Implement:

-   semantic cache
-   dynamic token budgets
-   dynamic cost allocation
-   confidence/risk routing
-   model escalation
-   adaptive reasoning
-   historical performance routing

## Phase 5 --- Learning optimizer

Implement:

-   task/model performance database
-   quality prediction
-   cost prediction
-   latency prediction
-   automatic routing policy improvement

------------------------------------------------------------------------

# 48. Minimal Practical Version

A useful first version does not need a huge infrastructure.

``` text
             MULTI-AGENT GRAPH
                    |
                    v
            OPTIMIZATION LAYER
                    |
       +------------+------------+
       |            |            |
    Context       Model        Tool
    Manager       Router       Cache
       |            |            |
       +------------+------------+
                    |
                  Models
                    |
       +------------+------------+
       |            |            |
    OpenAI      Anthropic     DeepSeek
       |            |            |
       +------------+------------+
                    |
             Token / Cost Logs
```

This is enough to start measuring and improving real workloads.

------------------------------------------------------------------------

# 49. ULMI and UAR --- Kept Separate

## ULMI

**Universal LLM Interface**

Purpose:

> Standardize how applications communicate with different LLM providers.

It can eventually normalize:

``` text
requests
responses
usage
capabilities
errors
tool calls
streaming
```

But it is **not required for the optimization concepts above**.

## UAR

**Universal Agent Runtime**

Purpose:

> A broader standardized runtime architecture for managing agents,
> models, tools, memory, context and execution.

It is a future architectural proposal.

It is **not required to build the initial optimizer**.

------------------------------------------------------------------------

# 50. Relationship Between the Three

``` text
                 MULTI-AGENT SYSTEM
                        |
                 ORCHESTRATOR
                        |
                OPTIMIZATION LAYER
                        |
       +----------------+----------------+
       |                |                |
    Tokens           Models           Tools
    Context        Capability        Requests
    Cache           Routing           Cache
       |                |                |
       +----------------+----------------+
                        |
                    LLM Models


FUTURE STANDARDIZATION:

ULMI
 ↓
standard model interface

UAR
 ↓
standard agent/runtime architecture
```

The **optimization layer is the practical implementation target**.

ULMI/UAR remain separate conceptual standards.

------------------------------------------------------------------------

# 51. Final Architecture Recommendation

For the current project:

``` text
                         USER
                           |
                           v
                 MULTI-AGENT ORCHESTRATOR
                           |
       +-------------------+-------------------+
       |                   |                   |
    Planner             Research            Coding
     Agent                Agent              Agent
       |                   |                   |
       +-------------------+-------------------+
                           |
                           v
              +-----------------------------+
              |   OPTIMIZATION CONTROLLER   |
              |                             |
              | Context Optimizer           |
              | Token Budget Manager        |
              | Model Capability Router     |
              | Request Optimizer           |
              | Tool Optimizer              |
              | Cache Manager               |
              | Cost Controller             |
              | Quality/Risk Controller     |
              | Loop Detector               |
              | Parallel Scheduler          |
              | Telemetry                   |
              +--------------+--------------+
                             |
                             v
                       MODEL LAYER
                             |
        +--------------------+--------------------+
        |                    |                    |
      OpenAI              Anthropic           DeepSeek
        |                    |                    |
      Gemini                Qwen             Llama / OSS
        |                    |                    |
        +--------------------+--------------------+
                             |
                       Local Models
```

------------------------------------------------------------------------

# 52. Final Principle

The multi-agent system should not ask:

> **"Which is the best LLM?"**

It should ask:

> **"What is the cheapest, fastest and smallest amount of computation
> that can reliably accomplish this specific step?"**

That means optimizing:

``` text
MODEL
+
TOKENS
+
CONTEXT
+
REQUESTS
+
TOOLS
+
CACHE
+
MEMORY
+
PARALLELISM
+
REASONING
+
VALIDATION
+
COST
+
LATENCY
```

while maintaining:

``` text
QUALITY
+
RELIABILITY
```

This is the **practical Token & Resource Optimization architecture**.

ULMI and UAR can remain separate as **future standardization
proposals**, rather than becoming mandatory components of the
implementation.
