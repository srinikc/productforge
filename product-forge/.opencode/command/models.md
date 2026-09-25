---
description: Switch all pipeline agents between model tiers (recommended / cheap / hybrid / zenfree / orouterfree) or list current models. Usage: /models recommended | /models cheap | /models hybrid | /models zenfree | /models orouterfree | /models list
agent: build
model: opencode/mimo-v2.5-free
---

$ARGUMENTS

You are switching the model tier for the multi-agent pipeline in this folder. The tier is chosen by the argument (must be one of: recommended, cheap, hybrid, zenfree, orouterfree, list). If the argument is missing, show the usage and the tier tables below, then ask which tier to apply.

## Tier model assignments (model IDs are used as `opencode-go/<id>` or `opencode/<id>` or `openrouter/<id>:free`)

### Tier: recommended (default) — Go paid models, best quality
| Agent file | model |
|---|---|
| ideation | opencode-go/mimo-v2.5 |
| design | opencode-go/minimax-m3 |
| architect | opencode-go/qwen3.7-max |
| review | opencode-go/qwen3.7-plus |
| implement | opencode-go/kimi-k2.7-code |
| code-review | opencode-go/kimi-k2.7-code |
| validate | opencode-go/deepseek-v4-flash |
| fix | opencode-go/kimi-k2.7-code |

### Tier: cheap — Go paid models, budget-optimized
| Agent file | model |
|---|---|
| ideation | opencode-go/hy3 |
| design | opencode-go/mimo-v2.5 |
| architect | opencode-go/qwen3.7-plus |
| review | opencode-go/minimax-m3 |
| implement | opencode-go/deepseek-v4-flash |
| code-review | opencode-go/deepseek-v4-flash |
| validate | opencode-go/mimo-v2.5 |
| fix | opencode-go/deepseek-v4-flash |

### Tier: hybrid — Recommended for stages 0-3, cheap for stages 4-7
| Agent file | model |
|---|---|
| ideation | opencode-go/mimo-v2.5 |
| design | opencode-go/minimax-m3 |
| architect | opencode-go/qwen3.7-max |
| review | opencode-go/qwen3.7-plus |
| implement | opencode-go/deepseek-v4-flash |
| code-review | opencode-go/deepseek-v4-flash |
| validate | opencode-go/mimo-v2.5 |
| fix | opencode-go/deepseek-v4-flash |

### Tier: zenfree — OpenCode Zen free models (zero cost, rate-limited)
**Providers:** `opencode` (Zen) + `opencode-go` (Ox Alpha)
**Rate limits:** Dynamic capacity-based; free models rotate; 20 req/min typical.
**Use case:** Zero-cost prototyping, non-sensitive code only.

| Agent file | model | Context | Why this model for this role |
|---|---|---|---|
| ideation | opencode/mimo-v2.5-free | 200K | Xiaomi MiMo V2.5 — safe alternative (muse-spark excluded: sends prompts to Meta for training) |
| design | opencode/mimo-v2.5-free | 200K | Xiaomi MiMo V2.5, strong reasoning + multimodal (text+image) for design extraction |
| architect | opencode/hy3-free | 190K | Tencent Hy3, 64K output — deepest reasoning in free tier for architecture & ADRs |
| review | opencode/nemotron-3-ultra-free | 1M | NVIDIA 550B MoE, strong instruction following (#4) — best for critique & analysis |
| implement | opencode/mimo-v2.5-free | 200K | Best free coding model (SWE-bench ~68%), tool-calling optimized for agentic coding |
| code-review | opencode/big-pickle | 200K | Stealth model, strong at spotting issues (SWE-bench ~68%, tool calling + structured output) |
| validate | opencode/nemotron-3.5-lightning-free | 1M | NVIDIA 30B MoE (3B active), fast inference — ideal for running test suites quickly |
| fix | opencode/mimo-v2.5-free | 200K | Strongest free coding model for iterative bug fixes |

> **Note:** Free models rotate — check `opencode models | grep free` for current lineup. Do NOT use for sensitive/proprietary code.

### Tier: orouterfree — OpenRouter free models (zero cost, rate-limited)
**Provider:** `openrouter` (base URL: `https://openrouter.ai/api/v1`, `@ai-sdk/openai-compatible`)
**Rate limits:** 20 req/min per model; 50 req/day (no credits) or 1,000/day (with $10+ credits).
**Use case:** Zero-cost access to best-in-class free coding models via OpenRouter auto-router fallback.
**Auto-router:** Use `openrouter/free` to let OpenRouter pick the best free model for each request.

| Agent file | model | Context | Why this model for this role |
|---|---|---|---|
| ideation | openrouter/ox-alpha:free | 1M | Reasoning model, 1M ctx, zero-retention — ideal for capturing full product plan |
| design | openrouter/cohere/north-mini-code:free | 256K | Agentic coding model trained for terminal/harness tasks, fast (69 tok/s) |
| architect | openrouter/nvidia/nemotron-3-ultra:free | 1M | 55B active MoE, 1M ctx — best free for long-context architecture reasoning |
| review | openrouter/poolside/laguna-s-2.1:free | 262K | Strong code reviewer (Terminal-Bench 70.2%), built for tool-calling review |
| implement | openrouter/poolside/laguna-m.1:free | 262K | Best free coding agent (CursorBench 47.6%), built for tool-calling agentic coding |
| code-review | openrouter/poolside/laguna-s-2.1:free | 262K | Same as review — purpose-built for code review |
| validate | openrouter/cohere/north-mini-code:free | 256K | Fast (69 tok/s), 256K ctx — great for running test suites quickly |
| fix | openrouter/poolside/laguna-m.1:free | 262K | Best free agentic coder for iterative fixes |

> **Alternative:** Use `openrouter/free` for any agent to let OpenRouter pick the best free model dynamically.
> **Rate limits:** 20 req/min per model; 50 req/day (no credits) or 1,000/day (with $10+ credits). Add $10 credits for higher limits.

## Procedure

1. If the argument is `list`: read each file in `.opencode/agent/*.md`, extract the `model:` line from frontmatter, and print a table of agent → current model. Also read `products/<project>/pipeline.json` to show per-project tier. Then stop.
2. **Ensure the required provider exists in `opencode.json`:**
   - If tier is `zenfree`: check if `opencode.json` has a `"opencode"` provider entry. If not, add it:
     ```json
     "opencode": {
       "name": "OpenCode Zen",
       "options": {
         "baseURL": "https://opencode.ai/zen/v1"
       }
     }
     ```
   - If tier is `orouterfree`: check if `opencode.json` has an `"openrouter"` provider entry. If not, add it:
     ```json
     "openrouter": {
       "name": "OpenRouter",
       "options": {
         "baseURL": "https://openrouter.ai/api/v1",
         "apiKey": "{env:OPENROUTER_API_KEY}"
       }
     }
     ```
   - For `recommended`, `cheap`, `hybrid` tiers: ensure `"opencode-go"` provider exists (it should already).
3. **Update per-project tier storage:**
   - Read `products/index.json` to get list of projects
   - For each project, read `products/<project>/pipeline.json`
   - Update the `model_tier` field with the new tier
   - Update the `agents` object with new model assignments
   - Write back to `products/<project>/pipeline.json`
4. **Update agent files (global default):**
   - For each agent file in `.opencode/agent/`:
     - Read the file.
     - Locate ONLY the `model:` line inside the YAML frontmatter (the block between the leading `---` and the closing `---`).
     - Replace its value with the tier's model for that agent. Leave every other line untouched (do not reformat the file, do not touch `permission`, `description`, body, etc.).
5. After updating, print a diff-style summary:
   ```
   MODEL TIER UPDATED
   ══════════════════
   Tier: [tier name]
   
   Per-Project Updates:
   - myworld: pipeline.json updated with new tier and agent models
   
   Agent File Updates:
   - ideation.md: [old model] → [new model]
   - design.md: [old model] → [new model]
   - architect.md: [old model] → [new model]
   - review.md: [old model] → [new model]
   - implement.md: [old model] → [new model]
   - code-review.md: [old model] → [new model]
   - validate.md: [old model] → [new model]
   - fix.md: [old model] → [new model]
   
   Note: Changes apply to NEW pipeline runs. Restart opencode for full effect.
   ```
6. Tell the user: the change applies to NEW pipeline runs. Restart opencode for full effect (config is not hot-reloaded), and note that an in-flight pipeline run keeps its already-spawned agents' models.

## Per-Project Tier Storage

The model tier is stored in two places:
1. **Agent files** (`.opencode/agent/*.md`): Global default for all projects
2. **Pipeline.json** (`products/<project>/pipeline.json`): Per-project override

When running a pipeline:
1. Check `products/<project>/pipeline.json` for project-specific tier
2. If not set, fall back to agent file defaults
3. Per-project tier takes precedence over global defaults

This allows different projects to use different model tiers without affecting each other.

IMPORTANT: edit only the frontmatter `model:` line in each agent file. Preserve the exact YAML structure otherwise.