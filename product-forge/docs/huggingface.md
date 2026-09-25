# Hugging Face Datasets in Product Forge — Analysis & Proposal

**Status:** hand-authored analysis / proposal. Advisory only — no code, no store, nothing wired.
**Date:** 2026-09-24
**Scope:** global (whole of Product Forge)
**Related:** `docs/STRUCTURE-CONTRACT.md`, `docs/ADDING-TO-PRODUCT-FORGE.md`, `config/store-registry.json`,
`core/model_registry.py`, `core/model_fit.py`, `core/multi_model_review.py`

> This document describes an *opportunity*, not an implemented capability. Any adoption must go through
> the normal path first: backlog item(s) plus (if a new concern) a `config/store-registry.json`
> registration. Nothing here is a truth.

---

## 1. Framing

Product Forge is a **consumer of models, not a trainer of foundation models**. It takes an idea and
drives it through a multi-agent pipeline (ideation → design → architecture → review → implement →
code-review → validate → fix → document → package → pre-production → production → post-production)
to shippable software.

That means Hugging Face datasets are **not** a "feed them in and products get better" silver bullet.
Their real leverage falls into four buckets:

1. **Evaluation & model selection** — feed `core/model_registry.py`, `core/model_fit.py`,
   `core/multi_model_review.py`, and the quality gates.
2. **Test fixtures / seed data** — give the products the pipeline *builds* real corpora instead of
   template tests (validate stage, test framework).
3. **Knowledge / RAG corpora** — feed agent knowledge routing and the business domain packs.
4. **Distillation** — turn pipeline traces into training data for small *owned* local models.

---

## 2. Category fit — where each HF dataset family lands

| HF category | Best fit in Product Forge | Leverage |
|---|---|---|
| **evaluation** | LLM-as-judge calibration, Go/No-Go gate benchmarks, RCCA | High |
| **coding** | SWE-bench / HumanEval / MBPP to pick `implement` / `code-review` / `fix` models; code corpora for domain packs | High |
| **instruction tuning** | Bootstrap a small "pipeline agent" model from exported traces; format/summarize helpers | Medium (later) |
| **conversations** | Agent prompt design, multi-turn eval (MT-Bench), chat-companion dialog quality | Medium |
| **images** | `visual_qa` fixtures, wireframe → UI eval, aesthetic-regression baselines | Medium |
| **audio** | TTS/STT + wake-word testing for the dashboard voice companion | Medium (domain) |
| **scientific research** | RAG / domain data for `researcher` / `scout` and research-type products | Low–Med |
| **language** | Summarization / translation for `document`; context-length studies | Low–Med |
| **computer vision** | Only when the pipeline builds a CV product; fixtures | Low (domain) |

---

## 3. Highest-leverage plays (ranked)

### 1. Model-eval harness backed by HF evaluation/coding datasets (do first)
Continuously score every model in `config/model-tier.json` on pinned benchmarks, then write results
into the **existing model registry / `model_fit`**. This is the most on-brand option:
- The repo already has a model registry, model-fit scoring, multi-model review, and tier profiles.
- `wired_audit` already flags kctier ↔ model-tier drift — a benchmark source-of-truth closes that loop.
- It makes tier choices evidence-based instead of hand-curated.

Result: model selection stops being opinion and becomes measured, which is exactly the "product, not
prototype" bar the repo holds.

### 2. Fixture / golden-output factory for generated products (do second)
Pull small HF subsets as seed data **and expected outputs**, so the validate stage tests real behavior
rather than template output. Directly raises the quality of every product the pipeline ships.

### 3. Distillation loop (defer to a later phase)
Export `memory/episodic` + agent I/O as an instruction dataset, optionally warm-started from HF
instruction data, and fine-tune small local models (Ollama) for cheap/repetitive agents (`validate`,
formatting, `fix`). Converts rented API spend into owned weights.

---

## 4. Architecture fit (per the structure contract)

- **A dataset catalog is a new concern** → register it in `config/store-registry.json`
  (owner, kind, scope, concern; single writer, e.g. `core/dataset_catalog.py`). Reference datasets
  by id — never duplicate metadata.
- **All work goes to the backlog** (`core/backlog.py`), with dedup-before-add
  (`python -m core.backlog --similar "<title>"`) and a `dashboard_impact` decision.
- **API-first** — the dashboard consumes it only through the backend API; the API never writes the store.
- Add a `dataset-catalog` skill and, if recurring, a `data-curator` agent (recipe E/F).
- **Eval results belong to the model registry store**, not a parallel store (one truth per concern).

---

## 5. Risks & gates (must be satisfied before any adoption)

- **Licensing per dataset.** Licenses vary widely (research-only, non-commercial, CC-BY-NC,
  consent-limited e.g. Common Voice). Product Forge ships commercial products → commercial-use
  licenses only unless explicitly allowlisted. No license metadata = no use; route through
  `compliance-verifier` / `legal-privacy`.
- **PII / consent** in conversation and audio datasets → sanitize before any use.
- **Eval contamination.** Benchmark data must never leak into product prompts/context, or into any
  fine-tuning used for those benchmarks.
- **Provenance.** Pin dataset revision hashes; HF datasets mutate over time.
- **Size / bandwidth / cost.** Stream + cache locally. Never vendor datasets into the repo (the state
  store is already large — do not repeat that pattern).
- **One truth per concern.** One store, one writer, reference by id.

---

## 6. Recommendation

1. Start with **Play #1** (eval harness on HF evaluation/coding datasets)—smallest surface, highest
   payoff, most aligned with existing model-registry / quality-gate machinery.
2. Then **Play #2** (fixture factory).
3. Defer **Play #3** (distillation) to a later phase.

Before building anything:
- Open backlog item(s) with a `dashboard_impact` decision.
- Register the `dataset-catalog` concern in `config/store-registry.json`.
- Run a PoC: stream one small eval dataset (HF `datasets`), score 2–3 registry models, compare against
  current `model_fit` scores.

---

## 7. Illustrative datasets (examples, not endorsements)

| Purpose | Example datasets |
|---|---|
| Coding eval | SWE-bench, HumanEval, MBPP |
| General eval / judge | MT-Bench, LLM-judge suites |
| Conversations | LMSYS-Chat-1M, OpenAssistant (`oasst1`) |
| Instruction tuning | FLAN / Alpaca-style instruction sets |
| Audio | Common Voice, LibriSpeech |
| Images / CV | COCO, ImageNet subsets |
| Scientific research | Papers-with-Code-style, scientific QA sets |

> Verify the license and revision of any dataset before use.
