# LLM Models & Benchmark Standards — Condensed Analysis

> **Purpose**: Quick reference for choosing models and benchmarks for an agentic coding/productivity pipeline (e.g., a 15-agent framework like ProductForge). Last reviewed: 2026-09-02.

## 1. The Shortlist: 6 Benchmarks That Matter

| # | Benchmark | What it tests | Best for role/agent | Notes |
|---|---|---|---|---|
| 1 | **LMSYS Chatbot Arena** | Human pairwise voting → ELO | General assistant, architecture, design, research | Most credible "real user" ranking; hard to game; actively maintained |
| 2 | **Artificial Analysis** | Speed + cost + quality composite | Cost/performance decisions | Updated daily; best for $/quality tradeoffs |
| 3 | **SWE-bench Verified** | Real GitHub issues → does the PR fix pass tests? | Full coding agents | Coding gold standard; gamed but nothing better exists |
| 4 | **LiveCodeBench** | Fresh contest problems, low contamination | Pure coding skill | Cleanest coding eval; actively maintained |
| 5 | **Aider Polyglot** | Multi-language code editing (diff-style) | Code editing agents, refactors | Closest to real "edit this file" work |
| 6 | **Berkeley Function-Calling Leaderboard** | Tool/function call accuracy | Tool-using agents, orchestration | Standard for "can it call my API correctly?" |

### Honorable mentions (niche, still excellent)
- **τ-bench** — multi-step agent tasks (customer service, booking style). Best for agent orchestration.
- **GAIA** — research agents (web research + reasoning). Closest real eval for "give it a goal, see if it finishes."
- **FrontierMath / AIME** — hardest math reasoning. Use only if math is a core workload.
- **ARC-AGI** — abstract reasoning; hard, low scores even for frontier models.

### Cut from shortlist (stale or legacy)
- **HumanEval / MBPP** — saturated, contaminated, ignore
- **MMLU** — legacy, saturated, weak signal
- **Open LLM Leaderboard** — archived 2024
- **GPQA** — still used but narrow; not for agents

## 2. Model Recommendations by Role (as of 2026)

| Role / Agent type | Recommended models | Why |
|---|---|---|
| **General assistant / chat** | Claude Sonnet 4.5, GPT-5, Gemini 2.5 Pro, Kimi K2, GLM-4.5 | Broad capability, strong prose |
| **Coding agent (full PR/feature)** | Kimi K2, Qwen3-Coder, DeepSeek V3.5, GLM-4.5 | Strong on real code tasks, free tiers available |
| **Code editing (diff-style)** | DeepSeek V3.5, Gemini 2.5 Flash, Kimi K2 | Fast, accurate file edits |
| **Pure coding problem-solving** | Kimi K2, Qwen3-Coder, DeepSeek V3.5, o1-class | Fresh contest performance |
| **Tool-calling agent** | Claude Sonnet 4.5, GPT-5, Gemini 2.5 Pro, Kimi K2 | Structured tool use |
| **Multi-step agent / orchestrator** | Claude Sonnet 4.5, GPT-5, Kimi K2 | Long context, continuity |
| **Research agent (web + think)** | GPT-5, Claude Sonnet 4.5, Gemini 2.5 Pro | Grounded reasoning |
| **Long-context (1M+ tokens)** | Gemini 2.5 Pro, Kimi K2 | Big context windows |
| **Speed + cost leader** | Gemini 2.5 Flash, DeepSeek Flash, GPT-4o-mini | Cheapest per task |
| **Design / multimodal** | Claude Sonnet 4.5, Gemini 2.5 Pro, GPT-5, Kimi K2 | Visual reasoning |

### For a 15-agent ProductForge-style pipeline
- **Orchestrator (Agent 0)**: Claude Sonnet 4.5 or Kimi K2 — careful reasoning, long context
- **Coding agents (7a/7b/7c/7d)**: Kimi K2 or Qwen3-Coder — free, strong on code
- **Code review**: DeepSeek V3.5 or Kimi K2 — fast, accurate
- **UI/UX design**: Claude Sonnet 4.5 or Kimi K2 — visual reasoning
- **Architecture (Agent 3)**: Kimi K2 or Claude Sonnet 4.5 — structured thinking
- **Documentation**: Kimi K2 or Gemini 2.5 Flash — prose, long context
- **Speed-first**: Gemini 2.5 Flash or DeepSeek Flash

### Best free all-rounders
- **Best free all-rounder**: Kimi K2
- **Best free for pure coding**: Qwen3-Coder
- **Best free for speed/cost**: Gemini 2.5 Flash or DeepSeek Flash
- **Best free for reasoning + long context**: Kimi K2

## 3. Kimi K2 — Availability & Access

### OpenRouter (free tier confirmed)
- **Model ID**: `moonshotai/kimi-k2:free`
- **Paid**: `moonshotai/kimi-k2` at $0.57/M input, $2.30/M output
- **Context**: 131K tokens
- **Specs**: 1T total params, 32B active (MoE)
- **Strengths**: coding (LiveCodeBench, SWE-bench), tool use (τ-bench, AceBench), reasoning (ZebraLogic, GPQA)
- **Knowledge cutoff**: Dec 2024
- **Free tier**: rate-limited
- **Heavily used by**: Hermes Agent, OpenClaw, Claude Code

### Direct from Moonshot
- **Web chat**: `kimi.com` — free with quota
- **API**: `platform.moonshot.ai` — free credits on signup

### Other hosts
- HuggingFace Inference (rate-limited)
- Novita AI, DeepInfra (free credits)

### Newer Kimi variants to watch
- **Kimi K2.5** (Apr 2026, multimodal/visual)
- **Kimi K2.6** (May 2026)
- **Kimi K2.7-Code** (Jun 2026, code-specialist)
- **Kimi K3** (latest flagship, 2.8T params, "Open Frontier Intelligence")

### Using Kimi K2 via OpenRouter (OpenAI-compatible SDK)
```bash
OPENROUTER_API_KEY=sk-or-...
```

```python
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_OPENROUTER_API_KEY",
    base_url="https://openrouter.ai/api/v1"
)

response = client.chat.completions.create(
    model="moonshotai/kimi-k2:free",
    messages=[{"role": "user", "content": "Explain how to build a React app"}]
)

print(response.choices[0].message.content)
```

## 4. How to Pick a Model for Your Pipeline

1. **Start with LMSYS Chatbot Arena** for general intelligence ranking
2. **Check Artificial Analysis** for cost/speed/quality tradeoffs
3. **Run your own internal eval** on 20-50 real tasks from your repo — public benchmarks are gameable or off-target
4. **Use a router**: Kimi K2 (reasoning), DeepSeek Flash (speed), Gemini Flash (context) — don't rely on one model

## 5. TL;DR

- **Best free all-rounder**: Kimi K2
- **Best free coding**: Kimi K2 or Qwen3-Coder
- **Best free speed/cost**: Gemini 2.5 Flash / DeepSeek Flash
- **Best paid overall**: Claude Sonnet 4.5 / GPT-5
- **Most credible benchmarks**: LMSYS Arena, Artificial Analysis, SWE-bench Verified, LiveCodeBench, Aider Polyglot, Berkeley FC
- **No single benchmark is THE standard** — build your own internal eval on real tasks
