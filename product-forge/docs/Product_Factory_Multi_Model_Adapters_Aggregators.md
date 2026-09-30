# Provider Adapters, Model Registry, Routing and Result Aggregators

## 1. Core idea

For a multi-model AI Product Factory, **provider adapters, model registries, routers, generators, and result aggregators are different responsibilities**.

They should not be treated as the same thing.

The simplest mental model is:

```text
Product Factory
      |
      v
Orchestrator / Agent Workflow
      |
      +--> Model Router
      |       |
      |       v
      |   Model Registry
      |       |
      |       v
      |   Provider Adapter
      |       |
      |       v
      +--> LLM Provider / Model
      |
      +--> Result Aggregator / Validator
```

---

## 2. What is a Provider Adapter?

A **provider adapter** is software that hides the differences between provider APIs.

For example, Product Factory may support:

- OpenAI
- Anthropic
- Google Gemini
- DeepSeek
- MiniMax
- OpenRouter
- Other future providers

Without adapters, application code has to know how to call every provider separately.

With adapters, Product Factory can use one internal interface such as:

```python
response = llm.generate(request)
```

The adapter translates that common request into the API format required by the selected provider and normalizes the response back into Product Factory's internal format.

### Adapter responsibilities

An adapter can handle:

- Provider API endpoint
- Authentication and API keys
- Request format
- Response format
- Streaming
- Tool/function calling
- Provider-specific parameters
- Multimodal input formats where supported
- Error handling
- Retries where supported/configured
- Usage/token information
- Provider-specific response normalization

### What an adapter does NOT do

An adapter does not make different models equivalent.

It cannot:

- Increase a model's context window
- Give a model reasoning capability it does not have
- Make a text-only model understand images
- Make a weak model behave like a stronger model
- Guarantee the same quality from every model
- Decide which model is best for a particular Product Factory task

Those responsibilities belong elsewhere.

---

## 3. Model Registry

The **model registry** describes what each model can and cannot do.

Typical metadata includes:

| Attribute | Example |
|---|---|
| Provider | OpenAI |
| Model | Model-X |
| Context window | 128K |
| Max output | Provider/model specific |
| Text input | Yes |
| Image input | Yes |
| Audio input | Yes/No |
| Video input | Yes/No |
| Tool calling | Yes |
| Structured output | Yes |
| Reasoning | High/medium/limited/etc. |
| Reasoning controls | Model-specific |
| Streaming | Yes |
| Input price | Provider/model specific |
| Output price | Provider/model specific |
| Latency characteristics | Measured/estimated |
| Availability | Current status |
| Model version | Version/date |
| Quality/evaluation data | Product Factory evaluation |
| License/usage restrictions | Provider-specific |

This registry is important because an adapter only knows **how to communicate with a model**.

The registry tells Product Factory **what the model is capable of**.

---

## 4. Model Router

The **router** decides which model should handle a particular task.

For example:

```text
Task:
Generate a complex architecture

Requirements:
- Long context
- Strong reasoning
- Structured output
- Budget <= $0.50
```

The router checks the model registry.

```text
Candidate models
       |
       +-- Context sufficient?
       +-- Reasoning capability?
       +-- Structured output?
       +-- Cost?
       +-- Availability?
       +-- Task evaluation score?
       |
       v
Selected model
```

The router then passes the request to the appropriate provider adapter.

### Important distinction

```text
Router       = Which model should I use?
Adapter      = How do I call that model?
Model        = Performs the actual inference/generation.
```

---

## 5. Capability mismatch

This is one of the most important design considerations.

Suppose Product Factory asks:

```json
{
  "task": "analyze_image",
  "reasoning": "high",
  "context_required": 128000,
  "tool_calling": true
}
```

The router checks model capabilities.

### Case A — Fully compatible

The selected model supports the requested capabilities.

The adapter translates the request and calls the provider.

### Case B — Context too small

The model has only a 32K context window.

The system should NOT expect the adapter to magically solve this.

Possible policies:

```text
Reject request
       OR
Select larger-context model
       OR
Use context manager / retrieval / summarization
```

### Case C — Reasoning control unavailable

The user/application requests:

```text
reasoning = high
```

but the model does not expose a configurable reasoning control.

The system can:

```text
Select another model
       OR
Map the request to the closest supported behavior
       OR
Reject the requirement
```

The adapter should not pretend that unsupported capabilities exist.

### Case D — Vision unsupported

If the selected model cannot accept images:

```text
Router
   |
   +--> choose vision-capable model
```

Alternatively, a separate vision-processing component could extract information first, but that changes the workflow and may lose information.

---

# 6. Common API

Product Factory should ideally expose its own normalized internal interface.

For example:

```python
request = {
    "task": "generate_code",
    "requirements": {
        "reasoning": "high",
        "min_context_tokens": 128000,
        "tool_calling": True,
        "input_modalities": ["text", "image"],
        "max_cost": 0.50
    },
    "prompt": "Build a React dashboard",
    "model": "auto"
}

response = llm_service.generate(request)
```

The application does not need to know whether the final model is from OpenAI, Anthropic, Gemini, DeepSeek, or another provider.

Internally:

```text
llm_service
     |
     v
Model Router
     |
     v
Model Registry
     |
     v
Selected Provider Adapter
     |
     v
Provider API
     |
     v
Provider Model
```

---

# 7. What third-party libraries can provide

A major advantage is that Product Factory does NOT need to implement every provider adapter itself.

Libraries/gateways such as LiteLLM can provide a common interface across many model providers and handle significant portions of:

- Provider integrations
- Common request/response interfaces
- Model routing
- Token/usage handling
- Cost tracking
- Retries
- Fallbacks

Product Factory can build its own higher-level capability and policy layer above this.

Conceptually:

```text
Product Factory
       |
       v
Product Factory LLM Service
       |
       +--> Capability Policy
       +--> Model Registry
       +--> Task Router
       +--> Cost Policy
       +--> Quality Policy
       |
       v
Third-party LLM Gateway / Adapter Layer
       |
       +--> OpenAI
       +--> Anthropic
       +--> Gemini
       +--> DeepSeek
       +--> Other providers
```

A third-party gateway reduces integration work, but Product Factory should not blindly delegate all model-selection decisions to it.

---

# 8. What is a Result Aggregator?

A **result aggregator is different from a provider aggregator**.

### Provider aggregation

Makes multiple providers accessible through a common interface.

Example:

```text
One API
   |
   +--> OpenAI
   +--> Anthropic
   +--> Gemini
   +--> DeepSeek
```

### Result aggregation

Combines outputs produced by multiple agents, models, tools, or workflow branches.

Example:

```text
GPT
 |
 +--> Architecture

Claude
 |
 +--> Code review

DeepSeek
 |
 +--> Implementation

Playwright
 |
 +--> Test results

       |
       v

Result Aggregator
       |
       v
Consolidated Product Result
```

---

# 9. Are result aggregators third-party libraries?

Yes, to a degree.

Frameworks such as:

- LangGraph
- LangChain
- Haystack
- Other agent/workflow frameworks

provide mechanisms for collecting, merging, reducing, joining, or passing results between workflow branches.

However, **there is no universal result aggregator that knows how your Product Factory should decide between arbitrary AI outputs**.

For example:

```text
Model A says:
Use PostgreSQL.

Model B says:
Use MongoDB.

Model C says:
Use PostgreSQL for transactional data.
```

A generic library can collect these results.

But deciding:

```text
Which architecture should Product Factory adopt?
Why?
What evidence supports it?
Are there conflicts?
What tests are required?
```

is Product Factory-specific logic.

Therefore, the usual architecture is:

```text
Third-party framework
        +
Product Factory aggregation rules
        +
Validation/tests
        +
Optional reviewer LLM
```

---

# 10. Result aggregation example

Suppose Product Factory is implementing a feature.

```text
Requirements
      |
      +--> Architecture Agent
      |
      +--> Coding Agent
      |
      +--> Security Agent
      |
      +--> Test Agent
      |
      v
Result Aggregator
      |
      +--> Merge findings
      +--> Detect conflicts
      +--> Compare against requirements
      +--> Collect test results
      +--> Identify unresolved issues
      |
      v
Validation / Decision Gate
```

The aggregator should not simply concatenate answers.

A mature aggregator should preserve:

- Source of each result
- Agent/model used
- Timestamp/version
- Evidence
- Confidence where meaningful
- Conflicts
- Validation status
- Test evidence
- Unresolved issues

This is especially important for your Product Factory because you want **traceability and reliable autonomous execution**.

---

# 11. Generator vs Adapter vs Aggregator

These three are easy to confuse.

| Component | Main question |
|---|---|
| Adapter | "How do I communicate with this provider/model?" |
| Generator | "How do I produce this artifact?" |
| Aggregator | "How do I combine outputs from multiple sources?" |
| Router | "Which model/agent should perform this task?" |
| Registry | "What can each model/agent do?" |
| Validator | "Is the result actually correct?" |
| Orchestrator | "What should happen next?" |

Example:

```text
User Requirement
      |
      v
Orchestrator
      |
      v
Router
      |
      v
Model Registry
      |
      v
Adapter
      |
      v
LLM
      |
      v
Code Generator
      |
      v
Tests
      |
      v
Result Aggregator
      |
      v
Validator
      |
      +---- FAIL ---> Repair workflow
      |
      +---- PASS ---> Next gate
```

---

# 12. Recommended Product Factory approach

Do NOT build a separate microservice for every one of these initially.

Start with a modular internal architecture:

```text
product_factory/
│
├── llm/
│   ├── adapters/
│   ├── model_registry/
│   ├── router/
│   ├── capability_manager/
│   └── usage_cost/
│
├── generators/
│   ├── requirements/
│   ├── architecture/
│   ├── code/
│   ├── tests/
│   └── documentation/
│
├── aggregation/
│   ├── result_aggregator/
│   ├── conflict_resolver/
│   └── evidence_merger/
│
├── validation/
│   ├── requirements/
│   ├── code/
│   ├── tests/
│   └── security/
│
└── orchestration/
    ├── workflows/
    ├── state/
    └── gates/
```

Later, components that need independent scaling can become services.

---

# 13. The most important architectural principle

Do not design:

```text
Product Factory
      |
      +--> GPT
      +--> Claude
      +--> Gemini
```

Instead design:

```text
Product Factory
      |
      v
Capability / Model Abstraction
      |
      +--> Router
      +--> Registry
      +--> Adapter Layer
      |
      v
Any supported model/provider
```

This means adding a new model should ideally require:

```text
1. Add model metadata
2. Verify provider adapter support
3. Run capability/evaluation tests
4. Add pricing/limits
5. Enable routing policy
```

rather than rewriting your agents and workflows.

---

## 14. One-line mental model

Remember these seven words:

```text
Registry  = KNOW
Router    = CHOOSE
Adapter   = TRANSLATE
Model     = THINK / GENERATE
Generator = PRODUCE
Aggregator = COMBINE
Validator = VERIFY
```

And:

```text
Orchestrator = COORDINATE EVERYTHING
```

This separation is particularly important for your Product Factory because it allows **multi-model support without making the entire product dependent on any particular LLM provider**.
