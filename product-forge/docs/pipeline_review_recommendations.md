# Pipeline review — consolidated findings & recommendations (single review point)

> Everything gathered on the agent↔LLM process, in one place, with the agreed
> recommendation set and the backlog IDs that will implement them.
> Companion docs: `Agent_llm_process.md`, `agents_prompts_instructions.md`,
> `agent_prompt_Comparision.md`.

## 1. What we observed (live, `smoke-all`)
- `design` (per-feature sectioned): expected ≈ **11 features + 7 global sections = 18 calls**; measured **9 calls in 9.5 min**.
- Each call: **8,000–11,000 output tokens**, up to **6,600 reasoning tokens**, **36–78 s**, `finish_reason=stop`, **no retries/truncation**.
- Prompt grows **19k → 29k chars** across calls (prior sections accumulate).
- So: **not a loop bug** — *many long, verbose, serial* calls on a reasoning model.
- Live telemetry now works: `[LLM]` per call, `[HEARTBEAT]`, `[Estimate]`, per-agent `Model/Started/Ended/Duration/Artifacts/Calls`, `call-ledger.jsonl`, `work-estimate.json`, `run-status.json`, events.

## 2. Root cause
1. **Verbose model over-generation** (deepseek reasoning) — output ~10× what a trivial feature needs.
2. **Sectioned/per-feature strategy** → many calls.
3. **Growing context** per section call.
4. **Over-proportioned structure** (each atomic behaviour specced like a full module).
5. **Reasoning always on** (no per-agent reasoning control).

## 3. Why a normal chat session “does better”
A session = **one focused instruction → one concise answer**, with a **human steering** the next turn. The pipeline = **N sequential calls**, each with a large assembled prompt and a **complete structured spec** demanded by compliance → the model writes exhaustively “to be safe”. Same model, different *shape*.

## 4. Industry / OSS findings (condensed)
- **Anthropic (Building Effective Agents / Context Engineering):** simplest thing that works; workflows (chaining, routing, parallelization, **orchestrator-workers**, **evaluator-optimizer**); curate context; compaction.
- **Plan-and-Execute / ReWOO:** planner once + cheap executors; ReWOO ≈ **2 calls** vs N (ReAct).
- **ReAct:** 1 call per tool action → latency compounds; route intermediate steps to faster models; aggressive timeouts.
- **Agentic workload (arXiv):** 84.6–99.5% input-token reuse; **decode dominates** wall time; long-tailed. Input tokens dominate cost.
- **Verbosity research / OGC:** LLMs over-generate by default; control with **structure + instructions + provider effort + generous caps** (quality-safe); **deferred rendering** (data → template) cuts generation tokens 48–72%.
- **Adaptive routing:** Route-to-Reason (−60% tokens), RADAR (per-query reasoning budget), Ares (per-step reasoning effort), gsd-2 (complexity tiers + capability scoring + escalate-on-failure).
- **Structured outputs:** strict JSON schema when supported; else synthetic tool/JSON mode (OpenAI/LangChain/vLLM).
- **Tool selection:** 3–5 relevant tools/request improves selection up to ~89% and ~80% faster.

## 5. Capability steering (the “crux” design)
Generalize **tools-per-agent** to **all model capabilities**:
- **Per-agent capability vector**: `needs_reasoning(+level)`, `needs_tools`, `needs_structured`, `needs_vision`, `needs_long_context`, `min_context`, `min_output`.
- **Per-model capabilities** (already in `model-catalog.json`): tools/reasoning/structured_outputs/context/max_output/modalities/supported_parameters.
- **Request builder** per call: enable reasoning only if needed+supported; use json_schema when needed+supported; pass only the relevant tool subset; trim context.
- **Fallback/suggest**: if the model lacks a needed capability → route to a fitting candidate (Model-Gate) or **degrade + flag + suggest**.
- **Escalate-on-failure**: bump to a stronger tier on compliance/quality failure.
- PF already has: `capabilities` config, `model_catalog`, `model_gate`, router, tools-per-agent, ledger → **extend, don’t rebuild**.

## 6. OSS role-prompt sources to borrow from (keep PF artifacts/quality)
- **MetaGPT** (SOP roles; full Inception-Prompt templates), **ChatDev** (dual-agent review, `<END>` termination, dehallucination), **CrewAI** (role/goal/backstory), **AI-tools system prompts** (Claude Code/Cursor/Devin/v0/Windsurf/Manus/…), **Anthropic prompt library**, **12-factor-agents**, **OpenAI structured-outputs cookbook**.
- Borrow **structure**: role/goal/backstory, tool contract, do/don’t, output schema, information diet, termination. **Keep** PF’s artifact contracts, compliance, and stage rules.

## 7. Recommendations → backlog (product_forge)
| # | Recommendation | Backlog |
|---|---|---|
| 1 | Capability vector per agent | **BI-0221** |
| 2 | Capability-aware request builder | **BI-0222** |
| 3 | Reasoning on/off by role/stage/context | **BI-0223** |
| 4 | Structured-output-first + deterministic render | **BI-0224** |
| 5 | Parallel section/feature generation | **BI-0225** |
| 6 | Context discipline (compact pack + current item) | **BI-0226** |
| 7 | Capability fallback + escalate-on-failure | **BI-0227** |
| 8 | OSS role-prompt review + standardize role sections | **BI-0228** |
| 9 | Verbose-gated logging + loops/tool-calls in summary | **BI-0229** |
| 10 | Incremental section/feature artifact writes | **BI-0230** |
| — | Parent epic (earlier) | BI-0220 |

## 8. Recommended order
1. **BI-0229** (verbose flag + loops in summary) — observability first.
2. **BI-0221 + BI-0222 + BI-0223** — capability vector + request builder + reasoning control (biggest efficiency win, quality-safe).
3. **BI-0226** (context discipline) and **BI-0225** (parallel sections).
4. **BI-0224** (structured+render) — biggest token cut.
5. **BI-0227** (fallback/escalate).
6. **BI-0228** (OSS role-prompt review) — after the above, using `agent_prompt_Comparision.md`.
7. **BI-0230** (incremental writes).

## 9. Decision points
- **Reasoning default**: propose **on** for planning/architecture/security/consensus; **off/low** otherwise (config-driven, per-agent override).
- **Structured output**: propose **on for spec/sectioned agents** (design, product-design-spec, architect, requirements), plain markdown elsewhere.
- **Escalate-on-failure**: propose **on** (retry next tier on compliance/quality failure).
- **No caps on features or tight output caps** — control via structure + effort + reasonable budgets.
