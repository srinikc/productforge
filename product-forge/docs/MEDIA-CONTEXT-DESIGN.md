# Media Context Pipeline — Design (BI-PF-0287)

## Goal
Close the missing link so media actually reaches agents: a selector that, per agent call, **attaches
native media parts only when the chosen model accepts the modality**, otherwise supplies a **bounded
text summary**; and **charges media tokens** against the context budget. Producing agents persist to the
asset store + summary + ref; consuming agents never get raw bytes by default.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Prompt build | `agent_runner._build_agent_prompt` (text only, reads files as UTF-8) | unchanged + media summary block | `agent_runner` |
| LLM call | `_generate_agent_artifacts` → `self._call_llm(prompt, agent_id, stage_id)` | pass `media=parts` | `agent_runner` |
| Wrapper | `_call_llm(self, prompt, agent_id, stage_id, pin_model="")` — **drops media** | `media=None` threaded to `llm_client._call_llm` (already supports it) | `agent_runner` |
| Media builder | `multimodal.build` (gated by `model_inputs`, ≤8 MB, fail-closed) | reuse | reuse |
| Asset→parts | `asset_store.to_media` (children-first) — **orphaned** | call it | new `media_context` |
| Model choice | `self._get_agent_model_config(agent_id, stage_id)["model"]` | gate modality on it | reuse |
| Token accounting | `prompt_chars//4` only; media bytes never counted | add media tokens to `prompt_tokens_est` | `llm_client` |
| Summary fallback | none | bounded summary from asset metadata + `docs/media/analysis.md` | new `media_context` |
| Store | none needed | pure selector | — |

**Blast radius:** `agent_runner` (3 sites), `llm_client` (media token add), new module, tests. No new store; single writer preserved.

## Design decisions (modular)
- **New `core/media_context.py`** — pure selector, no store:
  - `for_agent(project_dir, agent_id, model_name, contract=None) -> (parts, summary_text, media_tokens)`.
  - Selects assets relevant to the agent (media agents by modality; others: assets referenced by upstream
    **asset ids** in artifacts, else none — never guess).
  - If `set(modality) ⊆ multimodal.model_inputs(model_name)` ⇒ **native parts** via `asset_store.to_media`
    (children/tiles/segments/frames first; ≤8 MB each or URI). Else ⇒ **summary only** (fail-closed).
  - `estimate_tokens(parts)` — image ≈ tiles×patches, audio ≈ seconds, video ≈ sampled frames; conservative.
  - `summary_text` — bounded (≤`PIPELINE_MEDIA_SUMMARY_CHARS`, default 2000), assembled from asset
    metadata (+ `docs/media/analysis.md` when present). Plain-text projects ⇒ `([], "", 0)` (no-op).
- **Thread `media`**: `_call_llm(..., media=None)` → `self.llm._call_llm(..., media=media)`; in
  `_generate_agent_artifacts`, build `(parts, summary, mtoks)` before the call, append `summary` to the
  prompt's context block, pass `media=parts`.
- **Token accounting**: add `media_tokens` to the estimate used by `llm_client` (so chunk/decision reacts);
  media attached only to the first chunk (already the behavior).
- **Opt-in & safe**: `PIPELINE_MEDIA_CONTEXT` = `off|summary|native` (default `summary` — text-only models
  still get value; `native` attaches parts). Fail-closed, never raises; unknown model ⇒ summary only.
- **Reuse, never duplicate**: `multimodal`, `asset_store`, `model_catalog`, `capability_packs`,
  `llm_client`. Generators remain `PIPELINE_GENERATORS=0` default.

## Plan (branch `feature/bi-pf-0287-media-context`)
1. `docs/MEDIA-CONTEXT-DESIGN.md` (this file).
2. `core/media_context.py` — selector + summary + token estimate (pure).
3. `core/orchestrator/agent_runner.py` — thread `media` through `_call_llm`; build media in
   `_generate_agent_artifacts`; append summary to prompt.
4. `core/orchestrator/llm_client.py` — count `media_tokens` in the fit decision (small, additive).
5. `config/env-flags.json` — `PIPELINE_MEDIA_CONTEXT`, `PIPELINE_MEDIA_SUMMARY_CHARS`.
6. Tests `test_media_context.py` — no-op for text-only/no assets; summary path for text-only model;
   native parts path for a vision model; token estimate > 0 for parts; fail-closed on unknown model.
   **e2e:** monkeypatch `_call_llm` wrapper to assert `media=` parts flow through for a media agent.
7. Gates: compileall, wired_audit (0 unwired), workflow_matrix, pipeline tests, precheck.
8. Merge; close `BI-PF-0287` through the loop.

## Acceptance
- With a media asset + a **vision-capable** model + `PIPELINE_MEDIA_CONTEXT=native`, the agent's LLM call
  receives media parts; with a **text-only** model it receives the **summary** (never raw); no assets ⇒ no-op.
- Media tokens are charged (fit/chunk reacts) — no silent context overflow.
- Plain-text projects byte-identical; `precheck` PASS; no new store.

## Out of scope (tracked separately)
Media chunking/map-reduce over children + markdown asset-ref resolution (`BI-PF-0288`), media QA
(`BI-0191`), real generator transport (`BI-0188` follow-up).
