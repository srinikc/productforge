# Agent LLM Process — analysis, loops, verbosity, and improvements

> Scope: how Product Forge calls the LLM per agent, why agents can be slow/verbose,
> how that compares to a normal chat session, what the industry does, and what we
> should change (quality-preserving). Companion doc: `agents_prompts_instructions.md`.

## 1. How an agent calls the LLM (call shapes)

Per agent, generation uses one of these **strategies** (`core/agent_requirements.py` +
`core/orchestrator/agent_runner.py`):

| Strategy | When | LLM calls | Tools |
|---|---|---|---|
| single | default; plain writers | 1 (+ continuations + retries + fallback candidates) | 0 unless the agent has tools |
| sectioned | `generation: sectioned` (design, product-design-spec) | 1 per configured section (+ continuations) | 0 |
| per-feature | `per_feature_agents` (design, product-design-spec) | 1 per feature **+** 1 per global section | 0 |
| tool-loop | agents with tools (implement*, devops, fix, validate, package) | 1 per iteration (≤ `max_iters`) + final | file/read/run tools |
| + retries | transient/429/rate | + retries (≤ `PIPELINE_MAX_RETRIES`) | — |
| + continuations | `finish_reason=length` | + ≤ 3 (default) / 6 (verbose) | — |
| + fallbacks | provider/model failure | + 1 per candidate in the tier fallback chain | — |

**Observed (smoke-all, `design`, per-feature):** expected ≈ **11 features + 7 global
sections ≈ 18 calls**; measured 9 calls in 9.5 min; each call **8,000–11,000 output
tokens** + up to 6,600 reasoning tokens, 36–78 s, `finish_reason=stop` (no truncation,
no retries). So it is **not looping** — it is *many long, verbose, serial* calls.

## 2. Why a normal chat session “does better”

- A session = **one focused instruction → one concise answer**, then a **human steers**
  the next turn. The human is the loop controller and the context is curated by hand.
- The pipeline = **N sequential calls**, each fed a **large assembled prompt**
  (instructions + context + knowledge + prior sections) and asked to emit a **complete
  structured spec** (FR/NFR/US ids, all sections) to satisfy the compliance checklist.
  The model writes **exhaustively “to be safe”**, and a **reasoning model** (deepseek)
  adds reasoning tokens and long outputs.
- Net: the difference is **call count × required structure × verbose model + growing
  context**, without human steering — not the model’s capability.

## 3. Loop / retry / timeout parameters (where enforced)

These are **enforced in code, not stated to the agent**:

| Parameter | Value | Where |
|---|---|---|
| per-call wall cap | 600 s (`PIPELINE_AGENT_MAX_SECONDS`) | `llm_client._call_llm_single` |
| per-agent budget | 900 s (`PIPELINE_AGENT_BUDGET_SECONDS`) | `agent_runner._generate_agent_artifacts` + llm_client |
| HTTP retries | 2 (`PIPELINE_MAX_RETRIES`), 429 backoff (1 if fallbacks) | `llm_client` |
| continuations | 3 default / 6 verbose | `agent_requirements.continuation` |
| reasoning/tool `max_iters` | 3 (depth=medium) | `agent_runner._generate_with_tools` |
| heartbeat | after 120 s, every 60 s | `stage_runner._start_heartbeat` |
| compliance retries | 2 | `stage_runner` stage loop |
| per-call max output | from agent contract | `context_manager.get_contract` |

**Gap:** agents are **not told** their budget, retry/loop caps, heartbeat, or timing —
so the model cannot self-limit. There is no “output budget / be concise” contract in the
agent cards beyond a generic conciseness guard.

## 4. Industry / OSS practice (research)

- **Anthropic — Building Effective Agents / Effective Context Engineering:** start with
  the **simplest** thing; prefer **workflows** (prompt chaining, routing, parallelization,
  **orchestrator-workers**, **evaluator-optimizer**) over free agents; **curate context**;
  don’t stuff every edge case; **compaction** for long horizons.
- **Plan-and-Execute / ReWOO (LangChain/arXiv):** **planner once**, cheap **executors per
  step**; ReWOO ≈ **2 LLM calls** total vs N in ReAct. *Don’t call the big model per step.*
- **ReAct (JetBrains/IBM):** 1 LLM call per tool action → **latency compounds**; **route
  intermediate steps to faster models** and use **aggressive per-call timeouts**.
- **Agentic workload characterisation (arXiv):** 84.6–99.5% of input tokens are **reused**;
  **decode dominates** wall time (91–98%); workloads are **long-tailed**. Trajectory
  reduction (99% of tokens are input) is the main cost lever.
- **Verbosity research (arXiv “Verbosity ≠ Veracity”, NeuralTrust, structured-output
  studies):** LLMs **over-generate by default**; control via **system-prompt constraints,
  structured formats, stop sequences, few-shot calibration, provider effort/verbosity** —
  **without degrading quality**. If capping, keep it **generous** (tight caps → retries).
- **“When Agents Go Quiet” (OGC):** generating **format-heavy prose** stalls; **deferred
  rendering** (emit **structured data**, render documents deterministically) cuts
  generation tokens **48–72%** and removes stalling.
- **Anthropic multi-agent harness (InfoQ):** **planner / generator / evaluator** split +
  **context resets** with **structured JSON handoff artifacts** + a **separate evaluator**.

## 5. Best recommendations (quality-preserving) — feasibility of section “D”

| # | Change | Quality impact | Feasible now? |
|---|---|---|---|
| 1 | **Structured JSON output + deterministic render** for spec agents | Neutral/positive (less prose, same facts) | Yes (new renderer + prompt change) |
| 2 | **Plan-once + parallel section/feature calls** | Neutral (order-independent sections) | Yes (ThreadPool over sections) |
| 3 | **Stop context growth**: compact shared pack + current feature only | Positive (less confusion) | Yes |
| 4 | **Verbosity control**: provider effort + structure + stop seq; generous max_tokens | Neutral | Yes (config + request params) |
| 5 | **Role-based model routing** (strong planner, fast sections) | Neutral/positive | Yes (tier has models; router exists) |
| 6 | **Evaluator-optimizer** (separate check, few-shot criteria) | Positive | Partial (compliance exists) |
| 7 | **Ledger-driven adaptive strategy** (direct/chunked/deferred) | Positive | Yes (ledger already records) |
| 8 | **Bounded loops** (3–4) | Neutral | Already bounded |

**Opinion.** The pipeline is **over-proportioned**, not broken: many **serial, verbose,
prose-heavy** calls with a **growing context**. The highest-value, quality-preserving fixes
are **(1) generate data + render deterministically**, **(2) parallelize sections/features**,
and **(3) stop context growth**; then **(4) verbosity control** and **(5) model routing**.
Feature count does **not** need capping. All of this is feasible without harming output.

## 6. Logging / verbosity (requested)

- Today: `[LLM]` per call, `[HEARTBEAT]`, `[Estimate]`, per-agent `Calls: llm=… tools=…`,
  ledger records, events. These should become **parameter-gated** (e.g. `PIPELINE_VERBOSE`
  / `logLevel`): **on now**, off/minimal later.
- **Add to the summary**: **LLM loops (calls) per agent** and **tool calls**, plus
  input/output/reasoning tokens and tool payload — already captured in the ledger; only
  need to surface “loops” explicitly in the agent-end summary + final report.

## 7. Open items

1. Surface **loops (LLM calls) + tool calls** in the agent summary and final report.
2. Make all this logging **verbose-flag based**.
3. Implement D-1..D-5 (structured+render, parallel sections, context discipline,
   verbosity control, routing) — after review.
