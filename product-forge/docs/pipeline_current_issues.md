# Product Forge — Current Pipeline Issues (live analysis)

> **Analysis date:** 2026-09-27.
> **Evidence:** the live `smoke-all` run (`products/smoke-all/*`, `pipeline-run.log`, `call-ledger.jsonl`,
> `run-status.json`, `pipeline-state.json`), `scripts/dev/wired_audit.py` advisories, the open backlog, and
> `docs/pipeline_review_recommendations.md`. **Repository truth = the code** — if this doc disagrees, the code wins.
>
> Companion docs: `pipeline_review_recommendations.md`, `productforge_full_architecture.md` (§21), `Agent_llm_process.md`.

---

## 0. Executive summary

| # | Area | Issue (live) | Severity | Backlog |
|---|---|---|---|---|
| 1 | Cost / tokens | Reasoning model **over-generates** (~8–11k output tokens per call); tiny `add` CLI produced **11 features / 159 FR / 113 NFR / 75 US / 193 sections** | **High** | BI-0224, BI-0226 |
| 2 | Throughput | **Sectioned/per-feature** strategy → many **serial** calls; prompt grows 19k→29k chars across calls | **High** | BI-0225, BI-0226 |
| 3 | Wall-clock | `design` (stage 1) alone ran **~10 h** (approval `elapsed_time` 35,933 s); whole stage ≈ 297,965 tokens | **High** | BI-0221–0226 |
| 4 | Hidden cost | The HIL **`human` proxy** made **42 LLM calls / 450,785 prompt tokens** (not shown as a stage agent; prompt grows per call) | **Medium-High** | BI-0229 (+ new item) |
| 5 | Capability steering | **No per-agent reasoning/tool/structured control** — reasoning is effectively always on | **High** | BI-0221/0222/0223 |
| 6 | Structured output | Not used for spec/sectioned agents (free-text markdown only) | **Medium** | BI-0224 |
| 7 | Fallback / escalation | No capability fallback or escalate-on-failure routing | **Medium** | BI-0227 |
| 8 | Observability / state | `run-status.json` says **`state: failed`** while `stages` are all `running`, and `pipeline-state.json` has **no failed_stage/error** → inconsistent derived status (cause: `run_failed` emitted with `run_id: ""`) | **High** | BI-0220, BI-0229 |
| 8b | Logs / observability | **No SSOT for logs**: ~20 files in 4 trees, **two event streams**, convention paths (`product-forge/logs/`, `dashboard/logs/`) absent, backend log in `data/logs/`; per-agent logs have no prompt/response. See `LOGS-AND-OBSERVABILITY.md` | **High** | BI-0229 + new items |
| 9 | Tool use | **`tool_calls: 0`** across the entire run — the tool loop was never exercised | **Medium** | investigate |
| 10 | Backlog hygiene | **11** backend items missing `dashboard_impact`; **11** near-duplicate open pairs | **Low** | review (advisory) |
| 11 | Model registry drift | **3** `free-trial-fast` model ids not in registry; **1** live-provider mismatch | **Low** | — |

**Top priorities:** 8 (status truth) → 5 + 1/2/3 (capability steering + context/output discipline = the cost/wall-clock fix) → 4 (surface/hide the HIL cost).

---

## 1. Cost & token over-generation

**Observation (live `smoke-all`, `call-ledger.jsonl`):**
- `design` (stage 1): **297,965 tokens**, **$0.114**, model `deepseek-v4.1-flash` (opencode-go).
- `design` covered **193 sections**, defined **11 features (F-1..F-11)**, specified **159 functional / 113 non-functional / 75 user-story** items — for an idea that is *"a tiny CLI that adds two integers."*
- Per-call output is **8,000–11,000 tokens** (up to **6,600 reasoning tokens**), **36–78 s** each.

**Root cause:**
1. Reasoning model writes **exhaustively “to be safe”** to satisfy the structured spec + compliance.
2. **Per-feature/per-section** generation → **many calls**.
3. **Growing context** (prior sections accumulate in the prompt).
4. **Over-proportioned structure** — each atomic behaviour is specced like a full module.
5. **Reasoning always on** (no per-agent reasoning control).

**Impact:** cost and wall-clock scale with *shape*, not difficulty; small tasks are disproportionately expensive.

**Backlog:** BI-0224 (structured-output-first + deterministic render), BI-0226 (context discipline).

---

## 2. Throughput — serial, sectioned calls

- Expected `design` shape ≈ **11 features + 7 global sections = 18 calls**; measured **9 calls in 9.5 min** (older run) and a **~10 h** stage in the latest run.
- Prompt grows **~19k → ~29k chars** across a stage's calls.
- No parallelism between independent sections/features.

**Backlog:** BI-0225 (parallel section/feature generation), BI-0226 (compact pack + current item).

---

## 3. Wall-clock / latency (`smoke-all`)

- `pipeline-run.log`: stage `design` approval `elapsed_time = 35933.6 s` (~**9.98 h**).
- The run **stopped after stage 1 (`design`)**; `pipeline-state.json` shows `completed_stages = 7`, `failed_stage = None`, `error = None`, yet the run ended.
- This is the most visible symptom: a trivial project effectively never completes in a reasonable time.

**Backlog:** BI-0221/0222/0223 (reasoning + capability steering reduce per-call time), BI-0225/0226.

---

## 4. Hidden / anomalous LLM usage — HIL `human` proxy

**Observation:** `call-ledger` attributes **42 LLM calls / 450,785 prompt tokens / 10,442 output tokens** to agent **`human`** — by far the largest prompt-token consumer after `design`.

- Source: `core/human_proxy.py` → `decide()` calls `executor.execute_agent("human", stage_id, task)` **for every gate decision** (auto mode).
- The prompt grows per call (3,981 → 12,750 tokens) because the task includes accumulated context.
- **`human` is not a stage agent**, so it is invisible in the per-stage/per-agent summary and the "Defined/Covered" report.

**Impact:** a large, unreported share of tokens/latency; obscures true per-stage cost. It also makes "auto" runs look cheaper/faster than they are.

**Backlog:** BI-0229 (verbose-gated logging + surface loops/tool-calls); **new backlog item** recommended: *"Cap/streamline the auto-mode HIL proxy (single decision prompt, no growth; surface it in the ledger/summary)."*

---

## 5. Capability steering is not implemented

PF has the pieces (`config/agent-capabilities.json`, `core/model_catalog.py`, `core/model_gate.py`, `model_router`,
tools-per-agent, `call-ledger`) but **does not steer per-call capabilities**:
- No **per-agent capability vector** (reasoning level, tools, structured, vision, long-context, min output).
- No **capability-aware request builder** (enable reasoning/JSON/tool-subset only when needed).
- No **reasoning on/off** per role/stage.
- No **capability fallback / escalate-on-failure**.
- Tools disabled/never invoked (`tool_calls: 0`).

**Backlog:** BI-0221, BI-0222, BI-0223, BI-0227.

---

## 6. Structured output not used

Spec/sectioned agents (design, product-design-spec, architect, requirements) emit free-form markdown, then a
separate render is implied. No `json_schema`/structured-first path → more tokens and less-deterministic parsing.

**Backlog:** BI-0224 (structured-output-first + deterministic render).

---

## 7. Observability & state integrity

**Inconsistency (live):** `products/smoke-all/run-status.json` reports `state: "failed"` while all
`stages` are `"running"` and `current_stage: ""`; `pipeline-state.json` has no `failed_stage`/`error`.
This means the **derived run status disagrees with the state store** — hard to trust for dashboards/alerts.

Other gaps:
- Run ended after stage 1 without a clear terminal reason surfaced in the state store.
- Verbose logging is always on (should be flag-gated).
- Loop/tool-call counts are not in the agent-end summary for all agents.

**Backlog:** BI-0220 (E2E reliability epic), BI-0229 (verbose-gated logging + loops/tool-calls in summary).
**Completions noted in `productforge_full_architecture.md` §21:** run_status for **all** stage events; parallel human-wait; audit single-writer.

### 7b. Logs are scattered — no SSOT (full map in `LOGS-AND-OBSERVABILITY.md`)
- **Two event streams:** `products/.orchestration/events.jsonl` (dashboard SSE reads this) vs `products/<project>/events.jsonl` (heartbeats/failures written here) → the live feed can miss run events.
- **Attribution loss:** `1-design.log` logs `agent_complete` with `run_id = "-"`; `events.jsonl` logs `{"type":"run_failed","run_id":""}`. Terminal events don't carry the run id → `run-status` can't correlate failures.
- **Config vs reality:** `config/log-conventions.json` declares `product-forge/logs/pipeline-backend.log` and `dashboard/logs/dashboard.log`, but both dirs are **absent**; the backend log is actually written to `data/logs/pipeline-backend.log`.
- **Incomplete:** per-agent logs hold lifecycle + token counts only — **no prompt, no response, no tool calls**.
- **Overlap:** `pipeline-state.json`, `run-status.json`, `project-status.json`/`PROJECT-STATUS.md`, `agents-live.json`, `pipeline-runs.json` all describe "where are we", with no single precedence.
- **No query surface:** logs are read by opening files; no `GET /api/v1/logs`.

**Backlog:** BI-0229 (verbose-gated logging) + **new items** proposed in `LOGS-AND-OBSERVABILITY.md` §6
(unify into one SSOT; fix terminal-event run_id + derive status from the stream; prompt/tool capture; logs query API).

---

## 8. Backlog & process hygiene (advisory — `wired_audit`)

| Advisory | Count | Detail |
|---|---|---|
| `reciprocity` | **11** | backend (`product_forge`) items missing a recorded `dashboard_impact` decision (e.g. BI-0220…BI-0230) |
| `backlog-duplicates` | **11** | near-duplicate OPEN pairs (threshold 0.6), e.g. `e2e-smoke BI-0003 ↔ BI-0006`, `Dashboard BI-0079 ↔ BI-0081` |
| `tier-models` | **3** | `free-trial-fast` model ids not in the registry: `google/gemma-4-31b-it:free`, `nvidia/nemotron-3.5-lightning:free`, `qwen/qwen3.8-27b:free` |
| `tier-live` | **1** | `free-trial-fast` (openrouter): `deepseek-v4.1-flash` not present on the live provider |

Also: **ProductForge-Dashboard backlog = 146 open** vs product_forge 45 — the dashboard is far behind (intended: backend-first, but it is a large, growing queue).

**Impact:** low individually, but they hide real issues and inflate the backlog (compounding cost). **Action:** run the
reciprocity pass, merge duplicates, and refresh the tier registry.

---

## 9. Model / provider notes

- **Working tier:** `kctier` via `opencode-go` → `deepseek-v4.1-flash` (all 4 models verified 200).
- **OpenCode Zen free models are NOT API-usable** from this environment (`403 FreeTierError: "OpenCode's free tier can only be used from within OpenCode"`). Use `opencode-go` as the cross-provider fallback.
- Model gate/readiness preflight is healthy: `model-gate` = **61/61 OK**, `readiness` = **14/14 ready**, catalog refreshed 2026-09-26.

---

## 10. Recently addressed (for context — do not re-raise)

- **Intake of any file type** (`.md/.txt/.pdf/.docx/.doc/.rtf/images`) + text extraction → `core/intake_files.py` (**BI-PF-0232**).
- **Destination-tagged backlog ids** `BI-<TAG>-<nnn>` (PF / DASH / IN / `<PROJECT>`) → `core/backlog.py` (**BI-PF-0231**).
- Run-lifecycle fixes: time-budget stop → `FAILED`, dead-PID lock reclaim, agent/stage lifecycle events, per-agent readiness, model catalog/gate, capability hints, dedup-before-add advisory.

---

## 11. Priority order (recommended)

1. **Status truth (BI-0220 / BI-0229):** make `run-status.json` agree with `pipeline-state.json`; surface terminal reason.
2. **Surface/handle the HIL `human` proxy** (new item): one bounded decision per gate; include it in the ledger/summary.
3. **Capability steering (BI-0221 + BI-0222 + BI-0223):** biggest quality-safe efficiency win.
4. **Context discipline + parallel sections (BI-0226, BI-0225).**
5. **Structured-output-first + render (BI-0224):** biggest token cut.
6. **Fallback / escalate (BI-0227).**
7. **OSS role-prompt standardization (BI-0228).**
8. **Incremental artifact writes (BI-0230).**
9. Backlog hygiene: close reciprocity gaps, merge duplicates, refresh tier registry.

---

## Appendix A — Evidence snippets

- `pipeline-run.log` (tail):
  ```
  Stage 1 - design: 297965 tokens, $0.114094 cost, deepseek-v4.1-flash, opencode-go
    - Covered 193 sections: F-1: `add` command entry point, Requirements, Behaviour, Business rules, Validation, Edge cases.
    - Defined 11 features (F-1..F-11).
    - Specified 159 functional, 113 non-functional, 75 user-story items.
  Decision: {"type": "human_proxy", "details": "design in stage 1", "reason": "approve", "elapsed_time": 35933.6131067276}
  ```
- `call-ledger.jsonl` totals: `llm_calls=76, output_tokens=186710, reasoning_tokens=67402, cached_tokens=68608, tool_calls=0`.
- `products/smoke-all/run-status.json`: `"state": "failed"`, stages all `"running"`, `current_stage: ""`.
- `core/human_proxy.py:72`: `ex = executor.execute_agent("human", stage_id, task)` (per gate decision).

## Appendix B — Open backlog inventory (`product_forge`, 45)

- **Feature (36):** epic reliability BI-0220; capability steering BI-0221–0223; structured/parallel/context BI-0224–0226;
  fallback BI-0227; OSS prompts BI-0228; verbose/logging BI-0229; incremental writes BI-0230; product registry/page/BOM
  BI-0215–0217; AI-era ops/guardrails BI-0218–0219; multi-modal epic BI-0185–0194; modular-core epic BI-0195–0214;
  any-file intake BI-PF-0232.
- **tech-debt (8):** cards decoupled from `.opencode` (BI-0201), tools relocation (BI-0202), PR workflow (BI-0205),
  model downloader (BI-0206), capability gate placement (BI-0210), vendor catalog (BI-0211), multimodal E2E test (BI-0212),
  capability-gated composition (BI-0213).
- **change (1):** destination-tagged ids BI-PF-0231.
- **Dashboard scope:** 146 open (BI-0001–0149 …) — front-end build-out, intentionally behind backend.
