# Media Ingest + Segmentation/Tiling + Asset Store — Design (BI-0187)

## Goal
Ingest media (image/audio/video) → normalize → **tile images / segment audio / frame-sample video**
→ per-asset metadata + summaries, with a **project asset store** (single writer) and stable asset ids
that feed `BI-0186`'s `multimodal` media dicts (≤8 MB per part). Large media is split so it can be
map-reduced through the existing text machinery.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Asset store | **none** | `products/<p>/assets/` + `assets.json` index | new `core/asset_store.py` |
| Raw intake media | `products/intake/_files/<source>/` (verbatim, images only typed) | reuse for originals; **add** audio/video typing | `core/intake_files.py` (reuse) |
| Generic blob/dedupe | `core/artifact_registry.sha256()` (content hash) | reuse hashing pattern | `core/artifact_registry.py` (reuse) |
| Multimodal parts | `core/multimodal.py` consumes `{type,path|url|data,mime}`, ≤8 MB | asset store **produces** these from assets/tiles | `core/multimodal.py` (consume) |
| Modality + packs | `core/modality.py`, `core/capability_packs.py` (persist at preflight) | ingest persists actual media assets; modality considers them | reuse |
| Metadata probe | **none** (BI-0191 owns QA: loudness/perceptual/A-V sync) | dimensions/duration/codec/fps/sample-rate + degraded flags | BI-0187 owns metadata only |
| Segment libs | PIL/numpy/scipy present; **no cv2/librosa/av/ffmpeg** (undeclared) | guard every import; degrade gracefully | — |
| Stage fit | run-start preflight (`pipeline_executor.py:2758-2788`) already does modality+packs | ingest media assets here (before stage 0) | `core/pipeline_executor.py` |

**Blast radius:** intake_files (extend typing), preflight (call ingest), CLI, store-registry, dashboard
(read only). No new top-level dirs; single writer per store.

## Design decisions
- **New `core/asset_store.py`** = single writer of `products/<p>/assets.json` (+ `products/<p>/assets/`
  blob dir). API: `add(project_dir, path|bytes, type, name, source, item_id) -> asset`,
  `get/list/index`, `tiles/split(asset, …)` (image tiles / audio segments / video frames, stored as
  child blobs), `to_media(asset)` → the `multimodal` dict(s) for LLM attach (≤8 MB each), `active()`.
- **Asset schema:** `{asset_id, type, mime, name, sha256, bytes, source, item_id, path,
  metadata{dimensions|duration|fps|sample_rate|channels|codec}, children[{id,kind,path,index,range}],
  degraded, reason, at}`. `asset_id` = `AS-<sha8>-<n>` (stable, content-derived; dedupe by sha256).
- **Reuse, don't duplicate:** originals may already live in `intake_files`; `asset_store` references
  them by path and adds typed metadata (does not re-store the original bytes when already saved). Audio/
  video typing added to `intake_files.extract` (today audio/video fall through to `binary`).
- **Segmentation, lib-guarded & fail-closed:**
  - Image: PIL → tiles (grid + overlap) or downscale; child blobs ≤8 MB. PIL absent ⇒ keep original,
    `degraded=true, reason="pillow_missing"`.
  - Audio: stdlib `wave` for WAV duration/sample-rate → time segments; non-WAV via `ffprobe`
    (`shutil.which`) if present, else store-only + degraded.
  - Video: `ffprobe`/`ffmpeg` (`shutil.which`) → frame-sample + audio-track extraction; absent ⇒
    store-only + degraded (metadata from container/size).
  - **Never raise:** a missing segmenter degrades the asset, never fails ingestion.
- **Map-reduce:** `split()` returns child assets; caller feeds the set through the existing chunked/
  text map-reduce (BI-0186/llm_client chunking). Sizes honor the 8 MB part cap.
- **Modality from actual media:** ingest records detected modalities (from asset types) into the
  capability profile (`capability_packs.save_profile`) so media-presence can complement idea-text signals.
- **Related/standards:** expose `to_media()` so the pipeline can pass `media=` to `_call_llm`
  (BI-0186 producer). Leave loudness/perceptual-hash/A-V-sync QA to `BI-0191`.

## Plan (branch `feature/bi-0187-media-ingest`)
1. `docs/MEDIA-INGEST-DESIGN.md` (this file).
2. `core/asset_store.py` — store + hashing/dedupe + metadata + `split` (guarded) + `to_media`.
3. `core/intake_files.py` — add AUDIO_EXTS/VIDEO_EXTS typing (reuse storage).
4. `config/store-registry.json` — register `assets.json` + `assets/<id>` glob (kind=evidence, project).
5. Wire: call ingestion at run-start preflight (media found in intake/`uploads` for the project); CLI
   `pipeline.py media <project>` for manual ingest/list.
6. Tests `test_asset_store.py` — add/dedupe/index; image tile split (PIL present) + graceful degrade
   when forced absent; `to_media` shape matches `multimodal` contract; metadata present.
7. Gates: compileall, wired_audit (0 unwired, stores registered), workflow_matrix, pipeline tests, precheck.
8. Merge; close `BI-0187` through the loop.

## Acceptance
- Ingesting an image produces a stable `AS-*` asset with `sha256`, dimensions, and (PIL present) tiles;
  audio/video produce duration/metadata; every asset has a stable id + metadata.
- A large asset splits into ≤8 MB parts; `to_media()` output is accepted by `multimodal.parts_for`.
- Missing segmenter libs ⇒ `degraded=true` with a reason; ingestion never raises.
- Stores registered; `wired_audit` 0; `precheck` PASS.

## Out of scope (tracked separately)
Generator adapters (`BI-0188`), media agents (`BI-0190`), media QA/validators (`BI-0191`), E2E
(`BI-0212`), OCR/doc pack (`BI-0209`).
