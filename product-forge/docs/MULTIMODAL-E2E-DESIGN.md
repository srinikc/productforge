# Multimodal End-to-End Acceptance — Design (BI-0212)

## Goal
One hermetic (fake-adapter, no-network) e2e test per modality that proves the **real** control-flow
chain stitches together: idea → capability detect → pack enable → model strategy → generator selection →
adapter (fake) → **asset store** → **media context** (summary/native) → **media QA** → assertions — plus
a text-only regression guard and an optional live smoke behind a flag.

## 360° — verified chain (all built, this session)
| Step | Module | Surface |
|---|---|---|
| detect modality | `core/modality.py` | `detect`, `capabilities_for_project`, `generators_needed` |
| enable packs | `core/capability_packs.py` | `resolve`, `save_profile`, `active_packs` |
| strategy gate | `core/model_strategy.py` | `gate_a`, `assess` |
| composition | `core/pipeline_composition.py` | `effective_definition` (4m stage) |
| generator select | `core/generator_adapters.py` | `select`, `generate`, `models_for_output` |
| asset store | `core/asset_store.py` | `add`, `list_assets`, `to_media`, `modalities` |
| media context | `core/media_context.py` | `for_agent` (summary/native), `chunk_media` |
| media QA | `core/media_qa.py` | `validate_project` |
| generator catalog | `config/generators.json` | kind/provider_kind/billing_unit/license |

**Blast radius:** one test file (+ design doc). No production change unless the e2e exposes a gap.

## Design decisions
- **Hermetic:** no network. `generator_adapters.generate` already returns a structured non-fabricated job
  when transport is unconfigured — the test asserts that contract (not a real artifact). Media *assets*
  are produced by feeding a **deterministic tiny fixture** through `asset_store.add` (the real sink).
- **Per-modality golden path:** for image/video/audio/3d — idea text → `modality.detect` →
  `capability_packs.resolve` enables the pack → `generator_adapters.select(kind)` yields a generator with
  correct `billing_unit`/license → asset lands in the store → `media_context.for_agent` returns a summary
  (text model) or native parts (vision model) → `media_qa.validate_project` runs.
- **Async path:** for video/music/3d (`async:true` in the catalog), assert `submit`→`status`→`cancel`
  lifecycle + a persisted job.
- **Regression guard:** a plain-text idea enables **no** pack, adds **no** media asset, and `for_agent`
  is a no-op — i.e. the text path is unchanged.
- **Cost:** assert `billing_unit` is present and `generate`/`cost` book the correct unit (no network).
- **Live smoke (optional):** gated by `PF_E2E_LIVE=1`; skipped otherwise (keeps suite fast/offline).
- **No new production module** unless the test reveals a real integration gap (then fix in the same item).

## Plan (branch `feature/bi-0212-multimodal-e2e`)
1. `docs/MULTIMODAL-E2E-DESIGN.md` (this file).
2. `test-framework/tests/pipeline/test_multimodal_e2e.py` — per-modality golden path + async lifecycle +
   text regression + cost unit + scripted (not live) assertions.
3. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck. Fix any gap the e2e exposes
   in-place (same branch) with a test.
4. Merge; close `BI-0212` through the loop.

## Acceptance
- One green test per modality; a text-only project produces no media artifacts/cost.
- Async (submit→status→cancel) works for video/music/3d; billing_unit asserted.
- Suite stays fast and offline; optional live smoke skipped by default.
- `precheck` PASS.

## Out of scope
Real generator transport, model downloader, sensor/IoT pack, OCR pack.
