# Model Tiers Configuration

## Available Tiers

The `/models` command supports switching between different model tier configurations. Each tier assigns specific models to each agent in the pipeline.

---

### Tier: recommended (default) — Go paid models, best quality

**Provider:** `opencode-go`

**Characteristics:** Maximum quality, highest cost, best for production

| Agent file | model | Context | Use Case |
|---|---|---|---|
| ideation | opencode-go/mimo-v2.5 | 200K | Best reasoning for capturing full product plan |
| design | opencode-go/minimax-m3 | 200K | Strong multimodal for design extraction |
| architect | opencode-go/qwen3.7-max | 200K | Deepest architecture reasoning |
| review | opencode-go/qwen3.7-plus | 200K | Strong critique and analysis |
| implement | opencode-go/kimi-k2.7-code | 200K | Best coding agent (SWE-bench ~70%) |
| code-review | opencode-go/kimi-k2.7-code | 200K | Same as implement for review |
| validate | opencode-go/deepseek-v4-flash | 200K | Fast inference for test suites |
| fix | opencode-go/kimi-k2.7-code | 200K | Strongest for iterative bug fixes |

---

### Tier: cheap — Go paid models, budget-optimized

**Provider:** `opencode-go`

**Characteristics:** Good quality, reduced cost, suitable for smaller projects

| Agent file | model | Context | Use Case |
|---|---|---|---|
| ideation | opencode-go/hy3 | 190K | Efficient reasoning, lower cost |
| design | opencode-go/mimo-v2.5 | 200K | Strong design extraction |
| architect | opencode-go/qwen3.7-plus | 200K | Good architecture reasoning |
| review | opencode-go/minimax-m3 | 200K | Efficient critique |
| implement | opencode-go/deepseek-v4-flash | 200K | Fast coding, acceptable quality |
| code-review | opencode-go/deepseek-v4-flash | 200K | Fast review |
| validate | opencode-go/mimo-v2.5 | 200K | Fast test execution |
| fix | opencode-go/deepseek-v4-flash | 200K | Quick bug fixes |

---

### Tier: hybrid — Recommended for stages 0-3, cheap for stages 4-7

**Provider:** `opencode-go`

**Characteristics:** Best of both worlds - use premium for creative stages, budget for execution

| Stage Range | Agent | Model | Rationale |
|---|---|---|---|
| 0-3 (Ideation, Design, Architect, Review) | ideation | opencode-go/mimo-v2.5 | Premium for creative work |
| 0-3 | design | opencode-go/minimax-m3 | Premium for design |
| 0-3 | architect | opencode-go/qwen3.7-max | Premium for architecture |
| 0-3 | review | opencode-go/qwen3.7-plus | Premium for review |
| 4-7 (Implement, Code-Review, Validate, Fix) | implement | opencode-go/deepseek-v4-flash | Budget for execution |
| 4-7 | code-review | opencode-go/deepseek-v4-flash | Budget for review |
| 4-7 | validate | opencode-go/mimo-v2.5 | Balanced for testing |
| 4-7 | fix | opencode-go/deepseek-v4-flash | Budget for fixes |

---

### Tier: zenfree — OpenCode Zen free models (zero cost, rate-limited)

**Provider:** `opencode` (Zen) + `opencode-go` (Ox Alpha)

**Rate limits:** Dynamic capacity-based; free models rotate; 20 req/min typical

**Use case:** Zero-cost prototyping, non-sensitive code only

| Agent file | model | Context | Why this model for this role |
|---|---|---|---|
| ideation | opencode/mimo-v2.5-free | 200K | Xiaomi MiMo V2.5 — safe alternative |
| design | opencode/mimo-v2.5-free | 200K | Strong reasoning + multimodal |
| architect | opencode/hy3-free | 190K | 64K output — deepest reasoning in free tier |
| review | opencode/nemotron-3-ultra-free | 1M | NVIDIA 550B MoE, strong instruction following (#4) |
| implement | opencode/mimo-v2.5-free | 200K | Best free coding model (SWE-bench ~68%) |
| code-review | opencode/big-pickle | 200K | Stealth model, strong at spotting issues |
| validate | opencode/nemotron-3.5-lightning-free | 1M | NVIDIA 30B MoE, fast inference |
| fix | opencode/mimo-v2.5-free | 200K | Strongest free coding model for fixes |

> **Note:** Free models rotate — check `opencode models | grep free` for current lineup

---

### Tier: orouterfree — OpenRouter free models (zero cost, rate-limited)

**Provider:** `openrouter` (base URL: `https://openrouter.ai/api/v1`, `@ai-sdk/openai-compatible`)

**Rate limits:** 20 req/min per model; 50 req/day (no credits) or 1,000/day (with + credits)

**Use case:** Zero-cost access to best-in-class free coding models via OpenRouter auto-router fallback

| Agent file | model | Context | Why this model for this role |
|---|---|---|---|
| ideation | openrouter/ox-alpha:free | 1M | Reasoning model, 1M ctx, zero-retention |
| design | openrouter/cohere/north-mini-code:free | 256K | Agentic coding model, fast (69 tok/s) |
| architect | openrouter/nvidia/nemotron-3-ultra:free | 1M | 55B active MoE, 1M ctx — best free architecture |
| review | openrouter/poolside/laguna-s-2.1:free | 262K | Strong code reviewer (Terminal-Bench 70.2%) |
| implement | openrouter/poolside/laguna-m.1:free | 262K | Best free coding agent (CursorBench 47.6%) |
| code-review | openrouter/poolside/laguna-s-2.1:free | 262K | Purpose-built for code review |
| validate | openrouter/cohere/north-mini-code:free | 256K | Fast (69 tok/s), great for test suites |
| fix | openrouter/poolside/laguna-m.1:free | 262K | Best free agentic coder for fixes |

---

### Tier: premium — Premium paid models, maximum quality

**Provider:** `opencode-go` (premium tier)

**Characteristics:** Top-tier models, highest cost, enterprise-grade quality

| Agent file | model | Context | Use Case |
|---|---|---|---|
| ideation | opencode-go/qwen3.7-max | 200K | Maximum reasoning capability |
| design | opencode-go/qwen3.7-max | 200K | Premium design extraction |
| architect | opencode-go/qwen3.7-max | 200K | Deepest architecture analysis |
| review | opencode-go/qwen3.7-max | 200K | Thorough critique |
| implement | opencode-go/kimi-k2.7-code | 200K | Best coding agent |
| code-review | opencode-go/kimi-k2.7-code | 200K | Premium review |
| validate | opencode-go/deepseek-v4-flash | 200K | Fast testing |
| fix | opencode-go/kimi-k2.7-code | 200K | Premium bug fixing |

---

### Tier: education — Discounted models for learning/education

**Provider:** `opencode-go` (education tier)

**Characteristics:** Student/educator pricing, good for learning, some limitations

| Agent file | model | Context | Use Case |
|---|---|---|---|
| ideation | opencode-go/mimo-v2.5 | 200K | Good reasoning for learning |
| design | opencode-go/mimo-v2.5 | 200K | Sufficient for design learning |
| architect | opencode-go/qwen3.7-plus | 200K | Good architecture understanding |
| review | opencode-go/minimax-m3 | 200K | Adequate for learning review |
| implement | opencode-go/mimo-v2.5 | 200K | Learning to code with guidance |
| code-review | opencode-go/mimo-v2.5 | 200K | Learning review patterns |
| validate | opencode-go/mimo-v2.5 | 200K | Understanding testing |
| fix | opencode-go/mimo-v2.5 | 200K | Learning debugging |

---

## Switching Tiers

```bash
/models list                    # See current tier and all options
/models recommended              # Switch to recommended tier
/models cheap                   # Switch to cheap tier
/models hybrid                  # Switch to hybrid tier
/models zenfree                 # Switch to zenfree tier
/models orouterfree            # Switch to orouterfree tier
/models premium                # Switch to premium tier
/models education               # Switch to education tier
```

## Per-Project Override

Model tiers can be overridden per project in `products/<project>/pipeline.json`:

```json
{
  "model_tier": "hybrid",
  "agents": {
    "ideation": { "model": "opencode-go/mimo-v2.5" },
    "design": { "model": "opencode-go/minimax-m3" }
  }
}
```

## Implementation Notes

- Changes apply to NEW pipeline runs only
- Restart opencode for full effect
- In-flight pipeline runs keep their spawned agents' models
- Provider configurations in `opencode.json` must exist for tier to work
