# Multimodal LLM Plumbing — Design (BI-0186)

## Goal
`llm_client` builds **text-only** messages today, so image/audio/video-capable models never receive
media. Add a **multimodal message builder** that attaches media parts (image/audio/video/file) to the
request, **gated by the selected model's `input_modalities`** (from `config/model-catalog.json`), with a
**fail-closed** path when the model lacks the modality.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Message build | `_call_llm_single` L312: `messages=[{"role":"user","content": prompt}]` (plain string); `_build_api_request_messages` L~: passes messages through | optional media parts in `content` array (OpenAI multimodal shape) | `core/orchestrator/llm_client.py` |
| Model modality metadata | `config/model-catalog.json` has `input_modalities`/`output_modalities`; `model_catalog.capabilities(model)` returns the dict | consult `input_modalities` before attaching | `core/model_catalog.py` |
| Call entrypoints | `_call_llm(prompt, agent_id, stage_id, pin_model="")`; `_call_llm_single(..., allow_template, fast_fail)` | add optional `media` arg (default None); no behavior change when absent | `llm_client` |
| Provider shaping | `provider_kinds.extract_content/headers` (BI-0193) | add `build_user_content(prompt, media, model_caps)` | `core/provider_kinds.py` (or small helper) |
| Continuation | continuation re-sends `{"role":"user","content":prompt}` (L426-429) | attach media only on the FIRST user message | `llm_client` |
| Capability packs | `core/capability_packs.py` (BI-0189) declares modality→providers/models | media types map to the same modality names | reuse |
| Error path | none | missing modality ⇒ skip media + record `degraded`/warning (never crash) | `llm_client` |

**Blast radius / consumers:** all `_call_llm` callers (agent_runner has ~15 call sites) — kept
backward-compatible (media optional; text-only path byte-identical). No new store; no config change.

## Design decisions
- **Media is a caller-supplied list, not auto-scraped.** `media=[{"type":"image","path|url|data":...}]`
  passed to `_call_llm(..., media=...)`. The pipeline/agents decide what media to attach; we never
  guess. Default `None` ⇒ exact current behavior.
- **Gate on the model's input modalities (fail-closed).** A new `multimodal.parts_for(model_name, media)`
  reads `model_catalog.capabilities(model).input_modalities`; only parts whose modality is supported are
  attached. Unsupported parts are **dropped with a warning** and reported in the result token_info as
  `degraded_media:[...]` (never silently sent to a text-only model, never an exception).
- **OpenAI multimodal content shape (shared across kinds).** `content` becomes a list:
  `[{"type":"text","text":prompt}, {"type":"image_url","image_url":{"url":...}}, {"type":"input_audio",...}]`.
  Text-only ⇒ `content` stays the plain string (unchanged request → zero regression risk).
- **Data vs URL:** local `path` is read + base64 data-URL encoded (size-capped, e.g. 8 MB); `url` passes
  through; `data` (already base64) wrapped. Fail-closed on unreadable/oversized (drop + warn).
- **New module `core/multimodal.py`** (small, pure): `MODALITY_TO_PART`, `model_inputs(model_name)`,
  `coerce(media)` → normalized parts, `parts_for(model_name, media)` → (supported, dropped), `user_content`
  (prompt, parts). Keeps `llm_client` thin and testable. Imported by `llm_client` ⇒ on runtime path.
- **Continuation-safe:** media attached only on the first user message; continuations reuse the existing
  text-only flow (media already seen by the model).
- **Chunking-safe:** when a prompt is chunked (artifact-splitting path), media is attached only to the
  first chunk's request to avoid duplicating large payloads; other chunks stay text.

## Plan (branch `feature/bi-0186-multimodal-llm`)
1. `docs/MULTIMODAL-LLM-DESIGN.md` (this file).
2. `core/multimodal.py` — modality→part mapping, normalize/coerce, `parts_for`, `user_content`.
3. `core/orchestrator/llm_client.py` — thread optional `media` through `_call_llm` →
   `_call_llm_single`; build `content` via `multimodal.user_content`; first-message-only; report
   `degraded_media` in token_info.
4. Tests `test_multimodal.py` — image part attached for a vision model; dropped for a text-only model
   (fail-closed, warning, no exception); text-only request unchanged; oversized/unreadable dropped.
5. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
6. Merge; close `BI-0186` through the loop.

## Acceptance
- With `media` + a vision-capable model, the request `content` is a list containing the media part.
- With a text-only model, media parts are **dropped** and reported (`degraded_media`), never sent; no crash.
- Absent `media`, the request is byte-identical to today (no regression).
- `wired_audit` 0; `precheck` PASS.

## Out of scope (tracked separately)
Media ingest/asset store (`BI-0187`), generator adapters (`BI-0188`), media agents (`BI-0190`),
validators (`BI-0191`), E2E (`BI-0212`), provider-specific non-OpenAI media shapes.
