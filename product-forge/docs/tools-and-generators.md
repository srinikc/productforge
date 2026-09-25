# Tools, Models, Adapters, Generators & Multi-Modal Agents — reference

Owner: Product Forge backend. Companions: `docs/multimodal_orchestration.md`,
`docs/multimodal_selection_dynamic.md`, `docs/model-tier-timing-and-multimodal-flow.md`.
This file is the **selection + wiring reference**: the existing text pipeline, the media/IoT layer
that plugs into it, the models (downloadable vs API), the tools/SDKs, the adapters/generators, and the
end-to-end flow. Backlog items are in §13.

---

## 1. Vocabulary

- **Model** — a weights artifact for one task (image-gen, TTS, ASR, OCR, VLM, forecast, …): either
  **open-weights** (download + run locally) or **API-hosted** (call a provider; never hold weights).
- **Adapter** — the *plumbing*: code that speaks ONE provider's transport and returns artifacts in our
  uniform shape `submit/status/fetch/cancel/cost`. Hides sync-vs-async + vendor differences.
- **Generator** — a **model whose OUTPUT is media** (image/video/audio/music/3D), invoked via an adapter.
- **Kind** — `chat, vision, image-gen, video-gen, tts, stt, music-gen, 3d-gen, embedding, rerank,
  ocr/doc-parse, timeseries/sensor`.
- **provider_kind** — `self-host` · `direct` · `aggregator`.
- **billing_unit** — `token | image | second | char | track | mesh | request | sample`.
- **Capability pack** — the per-project switch that enables a modality's agents + tools + models + stages.

---

## 2. Adapters — what / why / how

**What:** a class per (kind × provider_kind), one contract:
```
submit(kind,payload)->job · status(job) · fetch(job)->artifact · cancel(job) · cost(job)->(units,price,cur)
```
**Why:** (1) API shapes differ — chat is sync, video/music/3D are **async jobs**
(submit→poll/webhook→fetch); (2) transports differ (local GPU vs direct HTTPS vs aggregator portal);
(3) licensing/cost must be enforced centrally; (4) the router/agents must be provider-agnostic.
**How:** a model entry names `provider` + `provider_kind`; the registry maps it to an adapter; the router
resolves `(kind, modality, cost, free/paid)` → model → adapter; the executor drives async via the job
manager; cost is booked; the artifact lands in the asset store.
**Families to build:** `LocalModelAdapter` (self-host) · `DirectVendorAdapter` (per vendor) ·
`AggregatorAdapter` (generic) · `ModelDownloaderAdapter` (weights) · `ProviderKeyRegistry`.

## 3. Generators — what / why / how

**What:** catalog models with media `output_modalities` + `kind, provider_kind, billing_unit, unit_price,
free, open_weights, license`.
**Why:** `core/modality.generators_needed()` lists every media-OUT modality with no generator; registering
generators drives it to **0** and makes media products buildable.
**How:** the model-strategy gate picks the generator per modality; the router resolves it; an adapter runs
it; media QA validates; costing books per-unit cost. Only bundle-safe or API-hosted generators are offered.

---

## 4. Downloadable open-weights — are they LLMs? cost? size?

**Mostly not LLMs** — they are task models (diffusion, TTS, ASR, OCR, 3D). A **few are transformer/LLM**:
VLMs (Qwen2.5-VL, InternVL, Moondream, SmolVLM) and Whisper (ASR). **Yes** — open weights download once
and run **locally with no per-call/per-token fee**; your cost is your own compute. Licenses can still
restrict commercial use/redistribution, so we gate by license.

| Model | Role | Disk (approx.) | VRAM | License |
|---|---|---|---|---|
| FLUX.1-schnell (12B) | image | 12–24 GB | 8–16 GB | Apache-2.0 ✅ |
| Sana (0.6–1.6B) | image | 1–3 GB | 4–8 GB | Apache-2.0 ✅ |
| Wan 2.2 (1.3–14B) | video | 3–28 GB | 8–24 GB+ | Apache-2.0 ✅ |
| Mochi 1 / CogVideoX | video | 4–20 GB | 8–20 GB | Apache-2.0 ✅ |
| Kokoro / Piper | TTS | 0.3 GB / 20–60 MB | CPU–2 GB | Apache / MIT ✅ |
| Parler-TTS / Bark | TTS | 1.8–7 GB | 2–8 GB | Apache / MIT ✅ |
| Whisper / faster-whisper | STT | 0.1–1.5 GB | 1–6 GB | MIT ✅ |
| Vosk / Parakeet | STT | 0.04–1.8 GB | CPU–4 GB | Apache / CC-BY-4.0 ✅ |
| ACE-Step (3.5B) | music | ~7 GB | 8–12 GB | Apache-2.0 ✅ |
| TripoSR / TRELLIS / InstantMesh | 3D | 1.5–8 GB | 6–16 GB | MIT/Apache ✅ |
| Qwen2.5-VL / InternVL / SmolVLM / Moondream | VLM | 0.5–16 GB | 2–16 GB | Apache/MIT ✅ |
| BGE / E5 / GTE | embed/rerank | 0.1–2.3 GB | CPU–4 GB | MIT/Apache ✅ |
| Tesseract / PaddleOCR / RapidOCR / docTR | OCR | 10–200 MB | CPU–4 GB | Apache-2.0 ✅ |

> A full free self-host media stack ≈ **40–90 GB**; packs download only what a project needs.
> **Never bundle:** FLUX.1-dev, SD1.5/SDXL base, SVD, MusicGen (CC-BY-NC), XTTS (CPML),
> MMS-TTS (CC-BY-NC), HunyuanVideo/3D (Tencent), Surya/Marker weights.

## 5. API models — free-tier & paid (call, don't download)

| Modality | Free-tier | Paid (direct) | Aggregator (one key) |
|---|---|---|---|
| LLM/vision | Gemini AI Studio, Groq, OpenRouter free | OpenAI, Anthropic, Google | OpenRouter, Together, Fireworks |
| Image | Imagen (AI Studio), Cloudflare SDXL | GPT-Image-1, Imagen, Stability | fal.ai, Replicate, kie.ai |
| Video | limited | Runway, Luma, Pika, Kling, Sora | fal.ai, Replicate, kie.ai |
| TTS | Edge-TTS, Google TTS free | ElevenLabs, Cartesia, PlayHT, OpenAI | aggregators |
| STT | Groq Whisper, Deepgram credit | OpenAI, Deepgram, AssemblyAI, Azure | aggregators |
| Music | — | Suno, Udio, Stability | fal.ai, Replicate |
| 3D | — | Meshy, Tripo, CSM | fal.ai, Replicate |
| OCR | — | Google Doc AI, AWS Textract, Azure DI | — |
| Embed/rerank | HF Inference | OpenAI, Cohere, Pinecone | Together, OpenRouter |

## 6. Tools / SDKs — free, permissive, distributable ✅

**Python:** diffusers · transformers · safetensors · accelerate · huggingface_hub · hf_transfer ·
modelscope · torch · onnxruntime · openvino · Pillow · OpenCV · scikit-image · imageio · imageio-ffmpeg ·
PyAV · decord · MoviePy · librosa · soundfile · pydub · faster-whisper · piper-tts · kokoro · vosk ·
pyserial · bleak · pymodbus · minimalmodbus · paho-mqtt · influxdb-client · pdfplumber · pypdf ·
pypdfium2 · pytesseract · paddleocr · rapidocr · python-doctr · trimesh · open3d · pygltflib · numpy-stl ·
pyassimp · cadquery · ezdxf · pydraco · qdrant-client · faiss-cpu · fastapi.
**Binaries:** FFmpeg (**LGPL** build) · Tesseract (+tessdata) · whisper.cpp.
**Conditional (weak copyleft):** FFmpeg, FluidSynth (LGPL — unmodified/dynamic only).
**Do NOT bundle:** espeak-ng, aubio (GPL) · Essentia, Grafana, PyMuPDF (AGPL) · poppler (GPL) ·
Blender embedded (GPL — subprocess only) · Surya/Marker weights.

## 7. Licence & bundling policy

`license/open_weights/free/bundle_allowed` are **catalog fields** enforced by selection and packaging.
Bundle-safe = MIT/Apache/BSD/ISC/CC-BY or LGPL used unmodified. API-only = restricted weights.
Never ship GPL/AGPL inside the product. Verify the exact version license before every packaging run.

## 8. IoT / sensor / time-series

Sensors are **data streams**, not media files. **Ingest:** MQTT (`paho-mqtt`), serial (`pyserial`),
BLE (`bleak`), Modbus (`pymodbus`/`minimalmodbus`), CAN (`python-can`, LGPL), HTTP/REST, CSV/Parquet.
**Store:** Parquet/InfluxDB (client MIT); Grafana **external only** (AGPL). **Models:** anomaly
(IsolationForest, autoencoder/TSB-AE), forecast (DLinear, N-BEATS, PatchTST, TimesNet, Chronos, Moirai),
TinyML export (TFLite Micro). **Kinds:** `timeseries`, `sensor`, plus sensor+vision **fusion**.

---

## 9. The EXISTING Product Forge pipeline (text/regular — today)

Product Forge today runs a **text/LLM pipeline** with 8 phases (P1–P8), 40 stages, 62 agents. This is the
system the media layer must plug into (unchanged for non-media products).

| Phase | Stages | Agents |
|---|---|---|
| **P1 Ideation & Discovery** | `0` Ideation · `0a` Discovery | ideation · discovery |
| **P2 Business, Market & Monetization** | `0b` Business & Product Definition · `0c` Market/Competition · `0d` Monetization & Unit Economics · `0e` GTM & Customer Journey | product-owner · researcher · pricing-strategist · marketing |
| **P3 Design** | `1` Design · `1a` Product Design Spec · `1b` Design Review · `1c` UX/IA Review · `1d` Research | design · product-design-spec · design_critic · ux-ia · researcher |
| **P4 Architecture** | `2` Architect · `3` Refine Requirements · `3a` QA Spec Review | architect · orchestrator · validate |
| **P5 Implementation** | `4-0` Skeleton · `4a..4f` Iterations (+`-vqa` Visual QA) | implement · devops · code-review · validate · visual_qa |
| **P6 Verification** | `5` Security Scan · `6` NFR Tests · `7` Full Test Suite | security · validate |
| **P7 Delivery** | `8` Document · `9` Package · `10` Pre-Production · `10a` Go/No-Go · `11` Deploy · `12` Exit | document · package · devops · orchestrator · validate · production-deploy |
| **P8 Operate, Grow & Engage** | `13` Operate & Observability · `13a` Customer Success · `13b` Growth | observer · customer-success · growth |

Text e2e: **idea → discovery → business/market/monetization → design → architect → build (iterations +
visual QA) → verify (security/NFR/tests) → deliver (docs/package/deploy) → operate.** Models are chosen
from `config/model-catalog.json` (163 **text-output** models) via `model-tier.json`; modality detection
already exists (`core/modality.py`) but **output is text only** — that is the gap the media layer fills.

---

## 10. Media / IoT agents (new — plug into the pipeline above)

These agents are **added to the roster + stages only when their capability pack is enabled**. They reuse
the existing orchestrator/stage/job/QA machinery — they do not fork the pipeline.

| Agent (new) | Role / scope | Model(s) to use | Tools | Stage placement |
|---|---|---|---|---|
| **capability-strategist** | post-ideation gate: detect modalities → enable packs → pick kinds + free/paid mix → write `capabilities.json` | existing text tier (LLM) | `core/modality.py`, catalog, capability-packs | **new `0f`** (P1/P2) |
| **media-analyst** | understand assets: alt-text, scene/shot summaries, transcripts, tags | Qwen2.5-VL / InternVL / SmolVLM (VLM) · Whisper (ASR) · CLAP (audio) | media ingest/tiling | `0a`,`1d`,`1` (analysis) · `4m` |
| **media-generator** | generate image / video / music / 3D / voice | FLUX.1-schnell·Sana (img) · Wan 2.2·Mochi·CogVideoX (video) · ACE-Step (music) · TripoSR·TRELLIS (3D) · Kokoro·Piper (TTS) · Whisper (STT) | generator adapters (BI-0188) | **new `4m`** (P5) |
| **media-editor** | cut/merge/render, transcode, subtitles/burn-in, format packs | — (tools) | FFmpeg · MoviePy · Blender (external) | `4m` · `9` |
| **asset-librarian** | index, metadata, dedupe (phash), provenance & licence of assets | BGE / CLIP embeddings | asset store (BI-0187) | cross-stage |
| **doc-analyst** | OCR/document → structured text/tables/layout | Tesseract·PaddleOCR·RapidOCR·docTR + Qwen-VL for hard pages | ocr adapters (BI-0209) | `0a`,`1` · `4m` |
| **sensor-analyst** | time-series ingest, anomaly, forecast, TinyML packaging | IsolationForest/autoencoder · DLinear/PatchTST/Chronos | ingest adapters (BI-0208) | `1b`,`2` · `4m` |
| **media-qa** | validate media: probe, loudness, phash, A/V sync, captions, schema | — (validators) | ffprobe · loudness · phash | `5`,`6` (Verify) |

**Existing agents that gain media duties:** `architect` (media services in the tech stack) · `document`
(media docs/captions) · `a11y-audit` (alt-text/captions) · `security` (media/asset threats) · `package`
(bundle-licence check via BI-0211) · `pricing-strategist`/`finops` (per-unit media cost).

---

## 11. Integration — one e2e (text pipeline + media layer)

**Pack-gated composition.** A capability pack declares `{agents, stages, tools, validators, models}`.
When enabled, the orchestrator (a) adds the agents above to the roster, (b) injects the optional stages
(`0f`, `4m`, media-QA additions) into the run's stage order, (c) registers the pack's tools/models. For a
**non-media project nothing changes** — same 40 stages, same 62 agents, same cost.

**Where each pack touches the existing flow:**

| Existing stage | Non-media (today) | Media/sensor (pack on) |
|---|---|---|
| `0` Ideation | ideation | + media signals detected |
| `0a` Discovery | discovery | + `media-analyst`/`doc-analyst`/`sensor-analyst` analyse provided assets |
| **`0f` CAPABILITY & MODEL STRATEGY (new)** | — | `capability-strategist` writes `capabilities.json`, enables packs, picks kinds + free/paid |
| `0b..0e` Business/Market/Monetization | unchanged | + per-unit media cost in unit economics (BI-0194) |
| `1`,`1a`,`1c`,`1d` Design | design/ux/research | + media/asset design (storyboards, voice, assets) |
| `2` Architect | architect | + media services, asset store, provider/adapter strategy in the stack |
| `3`,`3a` Req/QA | unchanged | + media acceptance criteria |
| `4-0`,`4a..4f` Implementation | implement/devops/qa | unchanged code path **plus** media production: |
| **`4m` MEDIA PRODUCTION (new)** | — | `media-generator` → `media-editor` → `asset-librarian` (image/video/voice/music/3D/OCR/sensor) |
| `4*-vqa` Visual QA | visual_qa | + media rendering checks |
| `5`,`6`,`7` Verify | security/NFR/tests | + **`media-qa`** (probe/loudness/phash/A-V sync) |
| `8` Document | document | + captions/transcripts/media docs |
| `9` Package | package | + bundle-licence check (BI-0211) + media assets |
| `10..13` Deliver/Operate | unchanged | + media observability/cost |

**Run sequence (one e2e):**
```
idea
 → 0 ideation → 0a discovery (+media-analyst/doc-analyst/sensor-analyst if assets)
 → 0f capability-strategist  [enable packs, pick kinds + free/paid]  ◄── NEW
 → 0b..0e business/market/monetization (+per-unit media cost)
 → 1..1d design (+media/asset design)
 → 2 architect (+media services, adapters, asset store)      ◄── refine model strategy (BI-0192)
 → 3,3a requirements/QA
 → 4-0,4a..4f implementation  ─┬─ code path (existing agents)
                               └─ 4m media production: media-generator → media-editor → asset-librarian ◄── NEW
 → 5,6,7 verify (+media-qa)
 → 8 document (+captions) → 9 package (+licence check) → 10..13 deliver/operate
```

---

## 12. Architecture at a glance (terminal view)

```
                              PRODUCT FORGE — E2E (text + multi-modal in ONE pipeline)
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │  ORCHESTRATOR  ·  stage_runner (0..13b)  ·  agent_runner  ·  job_manager  ·  model_router            │
 │  config: pipeline-definition.json · model-tier.json · model-catalog.json · capability-packs.json     │
 └─────────────────────────────────────────────────────────────────────────────────────────────────────┘
        │                      │                                   │
        ▼                      ▼                                   ▼
 ┌──────────────┐   ┌───────────────────────────┐   ┌──────────────────────────────────────────────┐
 │ EXISTING      │   │ CAPABILITY LAYER (NEW)     │   │ MODEL / ADAPTER LAYER (NEW)                  │
 │ TEXT PIPELINE │   │                            │   │                                              │
 │               │   │ modality detect            │   │ kind-aware router (BI-0193)                  │
 │ P1 ideation   │   │  core/modality.py          │   │   reads model-catalog.json                   │
 │  discovery    │──►│ capability-strategist 0f   │──►│   (kind,provider_kind,billing_unit,          │
 │ P2 business   │   │  capability-packs (BI-0189)│   │    unit_price,free,open_weights,license)     │
 │ P3 design     │   │  post-ideation gate (0210) │   │        │                                     │
 │ P4 architect  │   │  strategy refine (BI-0192) │   │        ▼                                     │
 │ P5 build      │   └───────────────────────────┘   │  ADAPTER REGISTRY                            │
 │  (+ 4m media) │                                   │   ├─ LocalModelAdapter (self-host)           │
 │ P6 verify     │                                   │   ├─ DirectVendorAdapter (OpenAI/Google/…)   │
 │ P7 deliver    │                                   │   └─ AggregatorAdapter (fal/Replicate/kie)   │
 │ P8 operate    │                                   │        │                                     │
 └──────┬───────┘                                   │        ▼                                     │
        │                                           │  GENERATORS/MODELS: image·video·tts·stt·     │
        │                                           │   music·3d·ocr·embed/rerank·timeseries·VLM   │
        │                                           │        │                                     │
        │                                           │  ┌─────┴───────────────┐                     │
        │                                           │  ▼                     ▼                     │
        │                                           │ MODEL DOWNLOADER   PROVIDER KEY REGISTRY      │
        │                                           │ (BI-0206: HF/       (BI-0207: keys,           │
        │                                           │  ModelScope,         allowlist, cost caps)     │
        │                                           │  license gate,                                 │
        │                                           │  models.lock)                                  │
        │                                           └─────────┬─────────────┘                       │
        │                                                     │                                     │
        │              ┌──────────────────────────────────────┴───────────────────┐                 │
        │              ▼                                  ▼                          ▼               │
        │      MEDIA AGENTS (BI-0190)              ASSET STORE (BI-0187)      MEDIA QA (BI-0191)      │
        │      media-analyst / media-generator     artifacts+media+index      probe·loudness·        │
        │      media-editor / asset-librarian      (store-registry.json)      phash·A-V sync         │
        │      doc-analyst / sensor-analyst                                                          │
        └───────────────────────────────────────────────────────────────────────────────────────────┘
                     (a plain text/LLM project enables NO pack -> identical to today)
```

---

## 13. Backlog map

**Existing:** BI-0185 epic multimodal · BI-0186 LLM media plumbing · BI-0187 media ingest+asset store ·
BI-0188 generator adapters · BI-0189 capability packs · BI-0190 media agents · BI-0191 media QA ·
BI-0192 two-phase selection · BI-0193 provider-kind+router · BI-0194 per-unit costing · BI-0195 epic
pluggable/standards.

**New (from this doc):** BI-0206 model downloader+license gate · BI-0207 provider key registry ·
BI-0208 sensor/IoT pack · BI-0209 OCR/doc pack · BI-0210 post-ideation gate · BI-0211 tool licence
catalog · BI-0212 multi-modal e2e test · **BI-0213 capability-gated pipeline composition** (inject `0f`/`4m`
+ roster per pack into the existing 0..13b order).
