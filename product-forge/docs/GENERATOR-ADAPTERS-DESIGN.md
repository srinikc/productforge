# Generator-Model Adapters — Design (BI-0188)

## Goal
Register generator models (image/video/audio/music/3d) + provider adapters (direct, aggregator,
self-host open-weights) behind a **uniform adapter contract** (`submit/status/fetch/cancel/cost`),
persist outputs to the asset store, and expose them to the modality layer so `generators_needed()`
reports 0 for a supported modality once its generator is registered. Every generator carries license +
open-weights/free metadata and is only offered when permitted.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Generator catalog | **none** (`config/generators.json` absent) | new catalog | new `core/generator_adapters.py` |
| Generator transport | **none** (no real media API callers; `video_generation.py` only emits cmd strings) | adapters per provider shape | `generator_adapters` |
| Provider kinds | `provider_kinds` (kinds/headers/extract/supports/order_candidates); FEATURES = chat-shaped | extend FEATURES additively (image_gen/tts/stt/music/3d) | `provider_kinds` (same owner) |
| Provider creds | `credentials` has fal/replicate/kie (aggregator), openai/gemini/elevenlabs/deepgram (direct); `has()`/`key_for()` | reuse; self-host = no key | `credentials` (reuse) |
| Model catalog | `model_catalog` (OpenRouter+Zen chat); 11 image-out / 4 audio-out chat models; **0 video/3d** | do NOT write it; union in `modality` | reuse |
| Modality needs | `generators_needed` → `models_for_output` → catalog `output_modalities`; returns `['video','3d']` live | **union** generator registry into `models_for_output` | `core/modality.py` |
| Output sink | `asset_store.add(...)` (sha256, dedupe, probe) ; `to_media` | persist generator outputs here | `asset_store` (reuse) |
| Packs | `capability_packs` declares `generator_providers[]`, `providers_kind[]`, `models[]` | consume for selection | reuse |
| Cost/ledger | `call_ledger.append`, `credentials.check_budget` | log `kind="generator"`, budget-check paid calls | reuse |
| Async jobs | none | job store for video/music/3d | new project store |

**Blast radius:** `modality` (small additive union), pipeline preflight (optional use), CLI, store-registry.

## Design decisions
- **New `core/generator_adapters.py`** — single concern: run media generation; owns **`config/generators.json`**
  (global catalog) + **`products/<p>/generator-jobs.json`** (project async-job store). Does **not** touch
  `model-catalog.json` or provider creds (reuse).
- **Catalog entry schema:** `{id, kind(image-gen|video-gen|tts|stt|music|3d), output_modalities[],
  provider, provider_kind(direct|aggregator|self-host), model_ref, endpoint, async(bool),
  billing_unit(token|image|second|char|track|mesh|megapixel), unit_price, free(bool),
  open_weights(bool), license, requires_key(bool)}`. Seed with FREE open-weights (FLUX.1-schnell
  Apache-2.0, Wan 2.2 Apache-2.0, Kokoro, Whisper, ACE-Step) + representative paid/aggregator entries.
- **Adapter contract (uniform):** `submit(kind, payload) -> job`, `status(job)`, `fetch(job) -> artifact`,
  `cancel(job)`, `cost(job)`. **Provider shaped, not per-model classes:** a table maps
  provider+kind → an adapter; direct (OpenAI Images / Imagen / ElevenLabs), aggregator (fal/replicate/kie),
  self-host (`requires_key=false`).
- **Sync vs async:** sync (image-gen/tts) → `submit` returns a completed job with inline artifact;
  async (video/music/3d) → remote job id, `status` polls (backoff, `PIPELINE_GENERATOR_MAX_SECONDS`/
  `PIPELINE_GENERATOR_POLL_SECONDS`), `fetch` downloads. Webhook optional.
- **Fail-closed & degrade:** no key for a paid candidate or none available ⇒
  `{"ok": False, "error": "no_generator_available"}` (never fabricate); missing self-host lib ⇒
  `degraded=True` (never raise) — mirroring `asset_store._probe`.
- **Reuse provider_kinds:** selection = `capability_packs.resolve(modalities)` → `generator_providers` →
  `provider_kinds.order_candidates(candidates, prefer_kind=pack.providers_kind)` → first where
  `credentials.has(provider) or requires_key==False` and `provider_kinds.supports(provider, feature)`.
  Extend `provider_kinds.FEATURES`/`_PROVIDER_FEATURES` **additively** with generator providers/features.
- **Make `generators_needed()` 0:** extend `core/modality.models_for_output` to **union**
  `generator_adapters.models_for_output(modality)` with the catalog list (owner-extends-owner; no
  second writer). Acceptance uses **video/3d** (image/audio already non-empty from chat models).
- **Persistence & accounting:** outputs → `asset_store.add(source="generator", item_id=<BI>)`; append
  `call_ledger` `kind="generator"`; `credentials.check_budget` before paid calls. Off by default via
  `PIPELINE_GENERATORS=0`.

## Plan (branch `feature/bi-0188-generator-adapters`)
1. `docs/GENERATOR-ADAPTERS-DESIGN.md` (this file).
2. `config/generators.json` — catalog (free open-weights + paid/aggregator), with license/open_weights/free.
3. `core/generator_adapters.py` — catalog accessors, selection, `generate(kind, payload, project_dir)`,
   contract methods, async job store, budget/ledger, fail-closed/degrade.
4. `core/provider_kinds.py` — additive FEATURES/_PROVIDER_FEATURES for generator providers.
5. `core/modality.py` — union generator registry into `models_for_output`.
6. `config/store-registry.json` — register `generators.json` (config/global) + `generator-jobs.json`
   (control/project). `config/env-flags.json` — `PIPELINE_GENERATORS`, `PIPELINE_GENERATOR_MAX_SECONDS`,
   `PIPELINE_GENERATOR_POLL_SECONDS`.
7. CLI `pipeline.py generate <project> <kind> "<prompt>"` (dry-run when no key/lib). 
8. Tests `test_generator_adapters.py` — catalog loads + license/open_weights present; selection picks a
   key-less self-host candidate when no keys; fail-closed `no_generator_available`; `models_for_output`
   unions; `generators_needed(['video'])` → `[]` once a video generator is registered.
9. Gates: compileall, wired_audit (0 unwired, stores registered), workflow_matrix, pipeline tests, precheck.
10. Merge; close `BI-0188` through the loop.

## Acceptance
- An agent can call a non-text kind end-to-end through the adapter interface (image + audio; real call
  attempted, `no_generator_available` when unconfigured — no fabrication).
- Aggregator provider usable with one key; a self-host provider usable with no key.
- `generators_needed()` reports 0 for a modality once its generator is registered; each generator carries
  license info and is only offered when permitted.
- `wired_audit` 0; stores registered; `precheck` PASS.

## Out of scope (tracked separately)
Media agents (`BI-0190`), media QA/validators (`BI-0191`), model downloader/cache (`BI-0206`),
per-unit cost model (`BI-0194`), E2E (`BI-0212`).
