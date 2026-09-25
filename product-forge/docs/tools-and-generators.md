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

---

## 14. Models vs Tools — the mental model

- **Model (weights)** = the *brain*: a task-specific artifact that does image / video / voice / music /
  3D / OCR / understanding. It **cannot run alone**; a tool loads it. Downloaded from Hugging Face /
  ModelScope. (FLUX, Wan, Kokoro, Whisper, ACE-Step, TripoSR, Qwen-VL.)
- **Tool (runtime / library / binary)** = the *engine + hands*: code that either **runs a model**
  (PyTorch, diffusers, transformers, onnxruntime) or does **deterministic media work with no AI model**
  (FFmpeg, Pillow, OpenCV, MoviePy, trimesh).
- Analogy: a **tool is the app/player** (VLC); a **model is the codec/content** it plays. Install the
  tool once; fetch the model per need.

**Three kinds of tools**
1. **Model runners / frameworks** (load weights): PyTorch, diffusers, transformers, onnxruntime,
   accelerate, safetensors, llama.cpp.
2. **Deterministic tools** (no AI model): FFmpeg, Pillow, OpenCV, scikit-image, PyAV, imageio, MoviePy,
   pydub, soundfile, librosa, trimesh, open3d, pygltflib.
3. **Tools that ship their own model**: Tesseract (+tessdata), whisper.cpp (+ggml model), Piper (+.onnx
   voice), Vosk (+model).

**We need BOTH**: tools installed (once, always present) **and** model weights downloaded (per capability).
Tools are installed with the product / dev env (licence-gated, BI-0211); models are fetched on demand by
the **ModelDownloader** (BI-0206) into `product-forge/models/`.

---

## 15. Model families — is it an LLM?

**LLM** = Large *Language* Model (text). Most media models are **not** LLMs.

| Modality | Model family | LLM? |
|---|---|---|
| Text / reasoning | LLM (transformers) | yes |
| Understand image/video | **VLM** = LLM + vision | yes (LLM-based) |
| Image gen | Diffusion (FLUX, Sana) | no |
| Video gen | Diffusion/DiT (Wan, Mochi) | no |
| Voice TTS | Neural TTS (Kokoro, Piper) | no |
| Voice STT | ASR (Whisper) | no (transformer, not LLM) |
| Music | Diffusion/DiT (ACE-Step) | no |
| 3D | Triplane/NeRF/DiT (TripoSR) | no |
| OCR | CNN/transformer (PaddleOCR) | no |
| Embedding/rerank | Encoder transformer (BERT-family) | no |

The catalog's `kind` field is what tells the router *which type* of model it is (LLM or not) and which
adapter/tool runs it.

---

## 16. Download (self-host) vs API — same as LLMs

Media is **not different from LLMs**: you can **download** open-weights and run locally, **or call an
online model with an API key** (no download). Some models exist only one way.

| | Local / download (self-host) | Online / API key |
|---|---|---|
| Text LLM | Llama/Qwen + `llama.cpp`/Ollama | OpenAI / Anthropic / Gemini |
| Image | FLUX/Sana + `diffusers` | GPT-Image/Imagen, fal, Replicate |
| Video | Wan/Mochi + `diffusers`/`ffmpeg` | Runway, Luma, Kling, Sora, Veo |
| Voice | Kokoro/Piper/Whisper + tools | ElevenLabs, OpenAI TTS/Whisper, Cartesia, Deepgram |
| Music | ACE-Step + tools | Suno, Udio |
| 3D | TripoSR/TRELLIS + tools | Meshy, Tripo |
| OCR | Tesseract/PaddleOCR (local) | Google Doc AI, AWS Textract, Azure DI |
| Understand (VLM) | Qwen2.5-VL + tools | GPT-4o / Gemini / Claude vision |

Both are wired the same way in the router — only `provider_kind` differs (`self-host` | `direct` |
`aggregator`). Downloading is **only** the self-host/free path; the API path downloads nothing.

---

## 17. Open-weight sizes by type (approx.)

| Type | Example (permissive) | Disk (fp16) | Disk (quantized) | VRAM |
|---|---|---|---|---|
| Image | Sana (0.6–1.6B) | 1–3 GB | 0.8–2 GB | 4–8 GB |
| Image | FLUX.1-schnell (12B) | ~24 GB | 6–12 GB | 8–16 GB |
| Video | CogVideoX (2–5B) | 4–20 GB | 3–10 GB | 8–20 GB |
| Video | Wan 2.2 (1.3–14B) | 3–28 GB | 2–14 GB | 8–24 GB+ |
| Video | Mochi 1 (10B) | ~20 GB | ~10 GB | 20 GB+ |
| Voice TTS | Piper | 20–60 MB/voice | — | CPU |
| Voice TTS | Kokoro (82M) | ~0.3 GB | ~0.15 GB | 1–2 GB |
| Voice TTS | Parler-TTS (0.9B) | ~1.8 GB | ~0.9 GB | 2–4 GB |
| Voice STT | Whisper tiny → large-v3 | 75 MB → 1.5 GB | 40 MB → 1.5 GB | 1–6 GB |
| Voice STT | Vosk | 40 MB → 1.8 GB | — | CPU |
| Music | ACE-Step (3.5B) | ~7 GB | 3–4 GB | 8–12 GB |
| 3D | TripoSR | ~1.5 GB | — | 6–8 GB |
| 3D | TRELLIS / InstantMesh | 2–8 GB | — | 8–16 GB |
| Understand | SmolVLM (0.25–2B) | 0.5–4 GB | 0.3–2 GB | 2–6 GB |
| Understand | Qwen2.5-VL (3B/7B) | 6–16 GB | 3–6 GB | 6–16 GB |
| Embed/rerank | BGE / E5 / GTE | 0.13–2.3 GB | 0.1–1 GB | CPU–4 GB |
| OCR | Tesseract tessdata | 15–50 MB/lang | — | CPU |
| OCR | PaddleOCR / RapidOCR / docTR | 15–200 MB | — | CPU–4 GB |

Rules of thumb: **disk ≈ params × 2 bytes** (fp16), **q4 ≈ params × 0.5 bytes**;
**VRAM ≈ weights + 20–100 %** overhead (higher for video/3D).

---

## 18. Hardware feasibility (dev laptop → workstation)

On a **Dell 5560 (32 GB RAM, 4 GB GPU)** the 4 GB VRAM is the bottleneck:

| Modality | 4 GB laptop | Notes |
|---|---|---|
| TTS / STT-small / OCR / embeddings | ✅ | CPU, real-time-ish |
| Small VLM (SmolVLM, Moondream q4) | ✅/⚠️ | CPU or 4 GB tight |
| Image (Sana 0.6B, SDXL-Turbo, quantized) | ⚠️ | CPU slow; 4 GB small only |
| FLUX / music / 3D / video / big VLM | ❌ local | use API |

Fine for **development/demo** of light modalities; heavy media needs a GPU box or API.

---

## 19. Recommended hardware to run ALL open-weights locally

| Tier | VRAM | System RAM | Storage | What it runs |
|---|---|---|---|---|
| Minimum viable (quantized, slow) | **16 GB** (e.g. RTX 4080/5070Ti) | 64 GB | 2 TB NVMe | image (FLUX q4), audio, OCR, small VLM, 3D (slow); video marginal |
| **Recommended** (all local, quantized, comfortable) | **24–32 GB** (RTX 4090 / 5090 32 GB) | 64–128 GB | 4 TB NVMe | image fp16, **video usable**, music, 3D, VLM 7B |
| Comfortable / Pro (video fp16 + concurrency) | **48–96 GB** (RTX 6000 Blackwell / 2×24–48 GB) | 128 GB+ | 4 TB+ NVMe | everything fp16, multiple jobs, larger video |
| Alternative | Apple Silicon unified 64–128 GB | — | 2 TB+ | LLM/VLM great; some diffusion slower |

- **GPU:** NVIDIA/CUDA strongly preferred (diffusers/torch ecosystem); AMD via ROCm possible but rocky.
- **CPU:** 12–24 cores for ffmpeg encode, OCR, and CPU inference fallback.
- **Storage:** fast NVMe (model load + 40–90 GB weights + media assets).
- **Burst:** rent a cloud GPU (L40S/A100/H100) for video when needed instead of buying top-end.

Per-modality VRAM targets: image 6–16 GB · video 8–24 GB+ · audio CPU–4 GB · 3D 6–16 GB · VLM 4–16 GB.

---

## 20. Shipping a product that needs runtime multi-modal AI

Three shapes; the right answer is usually **hybrid**.

- **A) Bundle / self-host** — weights in the installer, or download on first run; runs on the end-user's
  machine. + no per-call cost, offline, private, no vendor keys. − big download, hardware needs, model
  updates = new release, **licence must be bundle-safe**.
- **B) API / BYOK** — product calls a provider with the **user's key**. + tiny app, best models, no
  hardware, easy updates. − per-call cost, internet + keys, data leaves, vendor lock.
- **C) Hosted service** — you run the models behind **your own API**; the product just calls it. + no user
  GPU, you control quality/cost. − you pay for GPUs, build/run a service.

**Recommended (same as Product Forge):** local-first for light modalities (audio/OCR/embeddings/small
image/VLM), **API (BYOK or hosted)** for heavy/premium (video/music/3D/voice). Add a **setup wizard**
(detect hardware → recommend local vs API → ask for keys). Ship either an **offline SKU** (weights) or a
**thin SKU** (API only).

**How it works in the shipped product** — it embeds the same abstraction:
```
runtime request ("generate image")
 -> capability + policy (baked at build time)
 -> router picks: self-host (load weights from bundle/cache) OR API (key from user/env)
 -> adapter runs it -> artifact returned to the product UI
```
So the build-time choice (capability pack + strategy gate) is the **default**, but the product can
**fall back at runtime** (no GPU -> API; no key -> local). Bundling requires `bundle_allowed` weights;
restricted weights are reachable **only via API**.

---

## 21. Default model-selection policy (decision rule)

> **Self-host open-weights by default (free, shippable, private); fall back to API only for real gaps
> (top video/voice/3D, or no GPU / zero-download); reach paid models through a single aggregator key —
> always pluggable.**

Tiers: **0)** permissive open-weights · **1)** free-tier API · **2)** paid API/aggregator.
`provider_kind = self-host | direct | aggregator`; chosen per project by the model-strategy gate
(BI-0192 / BI-0210), configurable in the capability pack.

---

## 22. Industry standards & prior art (we are not inventing this)

Our concepts map onto established architecture patterns, frameworks and standards. Adopt these rather
than invent — there is **no single "multi-modal standard"**, but there are well-known practices per layer.

| Our concept | Industry practice / standard it aligns with |
|---|---|
| Adapter / provider abstraction | **Ports & Adapters (Hexagonal) architecture**; in AI: **LiteLLM**, **Vercel AI SDK**, LangChain/LlamaIndex provider abstractions, Hugging Face `transformers`/`diffusers` pipelines, **ONNX Runtime**; “**OpenAI-compatible API**” convention |
| Aggregator / one-key gateway | **API Gateway pattern**; AI gateways: **OpenRouter**, **LiteLLM proxy**, **Portkey**, **Cloudflare AI Gateway** |
| Model serving / loading | **MLOps serving**: NVIDIA **Triton**, **TorchServe**, **vLLM**, **TGI** (HF), **Ollama**, **KServe**, **BentoML**, **Ray Serve** |
| Model registry / metadata | **MLflow Model Registry**, HF **Model Cards**, **safetensors** / **GGUF** / **ONNX** artifacts |
| Async job (submit→poll→fetch) | Standard **task-queue / job** pattern (**Celery**, **RQ**, **Temporal**, **Argo Workflows**); media providers expose exactly this (Replicate/Runway/fal) |
| Agent interop & tool use | **MCP** (Model Context Protocol), **A2A** (Agent2Agent), **AG-UI**, OpenAI Agents SDK, LangGraph, AutoGen, CrewAI (all in BI-0195..0200) |
| Observability | **OpenTelemetry GenAI** semantic conventions (BI-0199) |
| Media formats | **glTF/GLB** (3D), **HLS/DASH** (video), **MIME types**, **EXIF/IPTC/XMP** (image metadata), **IIIF** (image delivery) |
| Audio QC | **EBU R128 / ITU-R BS.1770** loudness (BI-0191) |
| Content provenance | **C2PA / Content Credentials** (label AI-generated media) |
| Licensing / model governance | **SPDX** license IDs, **OpenRAIL** licenses, **Model Cards**; **NIST AI RMF**, **EU AI Act** (compliance) |
| IoT / sensor | **MQTT**, **Sparkplug B**, **OPC-UA**, **OMA LwM2M**, **W3C WoT**; time-series stores (**InfluxDB**) |
| Digital asset management | **DAM** concepts (asset store, metadata, provenance) |

**Conclusion:** the adapters/generators/aggregators/media-agents design is **industry-standard practice**
(Ports & Adapters + AI gateways + MLOps serving + agentic standards). Our job is to **wire the adopted
standards** (MCP/A2A/AG-UI/OTel in BI-0195..0200, C2PA/EBU R128 in BI-0191, MQTT/Sparkplug in BI-0208)
rather than build bespoke.

---

## 23. Hardware to run all open-weights — India cost, where to buy, build vs buy

> Prices are **approximate, 2026, India street, incl. ~18 % GST, volatile** — verify with retailers.
> GPU prices in India typically run **10–30 % above** global MSRP.

### GPU options (approx.)
| GPU | VRAM | Approx. India price | Notes |
|---|---|---|---|
| RTX 5070 Ti / 4070 Ti Super | 16 GB | ₹80 k – 1.1 L | entry (quantized only) |
| RTX 5080 / 4080 Super | 16 GB | ₹1.0 – 1.4 L | entry |
| **RTX 4090** | 24 GB | ₹1.7 – 2.2 L | recommended (scarcer now) |
| **RTX 5090** | 32 GB | ₹2.6 – 3.6 L | **best single-GPU pick** for all modalities |
| RTX A6000 / RTX 6000 Ada | 48 GB | ₹3.5 – 5.0 L | pro; video fp16 |
| RTX 6000 Blackwell | 96 GB | ₹7 – 9 L+ | comfortable/pro |
| Used RTX 3090 | 24 GB | ₹55 – 85 k | budget 24 GB (warranty risk) |
| Apple Mac Studio (M4 Max) | 64–128 GB unified | ₹2.5 – 4.5 L | alternative; slower for some diffusion |

### Full “all-local recommended” build (RTX 5090 class)
| Part | Approx. |
|---|---|
| GPU (RTX 5090 32 GB) | ₹2.6 – 3.6 L |
| CPU (Ryzen 9 9950X / i9 class) | ₹45 – 70 k |
| Motherboard (X870/Z790) | ₹25 – 45 k |
| RAM 128 GB DDR5 | ₹40 – 65 k |
| NVMe 4 TB | ₹25 – 40 k |
| PSU 1000–1200 W (80+ Gold) | ₹15 – 30 k |
| Case + cooling | ₹15 – 35 k |
| **Total (self-build)** | **≈ ₹4.2 – 6.0 L** |
| Prebuilt workstation (Dell Precision / Lenovo ThinkStation, 48 GB pro GPU) | ₹6 – 12 L |

### Where to buy (India)
- **Online:** Amazon.in, Flipkart, **MDComputers**, **Vedant Computers**, **PrimeABGB**, **TheITDepot**,
  **EliteHubs**, **PC Studio**, **Nehru Place** (Delhi) / **SP Road** (Bengaluru) / **Lamington Road** (Mumbai).
- **Pro GPUs (A6000/RTX 6000):** authorized distributors (NVIDIA partners), not consumer retail.
- **Used:** OLX, Facebook Marketplace, **TechEnclave**, r/IndianGaming (test before buying).
- **Cloud (burst, no capex):** AWS/GCP/Azure; **India:** E2E Networks, NeevCloud, Yotta, Jio Cloud, Krutrim
  (rent a L40S/A100/H100 by the hour).

### Build vs buy
- **Self-assemble (desktop)** — cheapest for 24–32 GB; standard ATX, but watch **PSU wattage, GPU
  clearance (3–4 slot), cooling, PCIe layout**.
- **Multi-GPU (48–96 GB)** — needs a workstation/server board + big PSU; harder, or buy prebuilt.
- **Cloud** — best for spikes/video; no capex, pay per hour.
- **Verdict:** a **self-built RTX 5090 (32 GB) + 128 GB RAM + 4 TB NVMe (~₹4.5–5.5 L)** covers all
  modalities comfortably; rent cloud GPUs for heavy video instead of a 96 GB card.

---

## 24. Used GPUs — cost & where to buy (India)

> Approx., 2026, volatile. Used = **no warranty**; many 3090s were mining cards. **Test before paying.**

| Used GPU | VRAM | Approx. price | Notes |
|---|---|---|---|
| RTX 3060 | 12 GB | ₹15 – 22 k | entry; small models only |
| RTX 3090 | 24 GB | ₹55 – 90 k | **best VRAM-per-rupee**; NVLink-capable |
| RTX 3090 Ti / 4070 Ti | 24/12 GB | ₹70 k – 1.0 L | — |
| RTX 4090 | 24 GB | ₹1.2 – 1.7 L | fast; check for blower/AIB |
| RTX A6000 | 48 GB | ₹2.0 – 3.2 L | pro; video fp16 |
| Whole used workstation (Dell Precision / HP Z + GPU) | 24–48 GB | ₹1.5 – 4 L | often good value |

**Where:** OLX, Facebook Marketplace, **TechEnclave** (forum marketplace), r/IndianGaming, local markets
(Nehru Place, Lamington Rd, SP Rd), eBay (import — duty applies).
**Test checklist:** GPU-Z (fake check), VRAM stress (OCCT/GpuMemTest), thermal + fan test, run a real
diffusion/VLM job, check artifacts/ECC, verify no mining BIOS.

---

## 25. Home hosting — cooling & power cost

**Power draw (system under load):** RTX 3090 ~450–550 W · 4090 ~550–650 W · **5090 ~750–900 W**.
**Electricity (India, ~₹8/unit):**

| Build | 8 h/day | 24/7 |
|---|---|---|
| RTX 3090 system (~0.5 kW) | ~₹1,000 / month | ~₹2,900 / month |
| RTX 5090 system (~0.85 kW) | ~₹1,600 / month | ~₹4,900 / month |

**Cooling / environment (India ~35–40 °C ambient matters):**
- Good case airflow + 3–6 fans: ₹3–8 k. High‑end GPUs need a **large airflow case** (₹8–20 k).
- **Room AC is often required** for sustained load: AC ₹30–50 k + running ~₹2–4 k/month.
- **UPS / inverter** (1–1.5 kVA) to protect the GPU: ₹8–15 k.
- Noise under load is significant — plan a separate room.

**Home‑hosting verdict:** fine for **one GPU / dev**; not ideal for 24/7 production (heat, noise, power,
uptime, static IP, cooling). Use cloud for sustained production, or a rented colo.

---

## 26. Cloud GPU providers — who, configs, how they charge

Cloud GPUs come in three billing shapes: **per‑hour** (AWS/GCP/Azure/Lambda), **per‑second** (Modal,
RunPod, Vast), and **serverless** (Replicate, Modal — pay only while running). Storage is per GB‑month;
egress extra. **Spot / reserved** can cut 40–70%.

| Provider | Type | Typical GPUs | How charged | Rough on‑demand (USD/hr) |
|---|---|---|---|---|
| **AWS** | hyperscaler | T4, L4, A10G, L40S, A100, H100 | per‑sec (min 1 min) | T4 ~0.4 · A10G ~1.0 · H100 ~3–4 |
| **GCP** | hyperscaler | T4, L4, A100, H100 | per‑sec | L4 ~0.7 · A100 ~2 · H100 ~3–4 |
| **Azure** | hyperscaler | T4, A100, H100 | per‑sec | similar to AWS/GCP |
| **Oracle OCI** | hyperscaler | A100, H100 | per‑sec | often **cheaper** than AWS/GCP |
| **Lambda Labs** | GPU cloud | A10, A100, H100 | per‑sec | A100 ~1.3 · H100 ~2.5 |
| **CoreWeave** | GPU cloud | A100, H100, L40S | per‑sec | competitive |
| **RunPod** | GPU cloud/marketplace | 3090, 4090, A100, H100 | per‑sec | 4090 ~0.35–0.7 · A100 ~1.2 |
| **Vast.ai** | marketplace | consumer + datacenter | per‑sec | 3090 ~0.2–0.4 (cheapest) |
| **Modal** | serverless | A10G, A100, H100 | per‑second, scale‑to‑zero | A100 ~2 · H100 ~3 |
| **Replicate / fal / Together / Fireworks / Baseten** | serverless inference | many media models | per‑second / per‑unit | pay per run |
| **India: E2E Networks, NeevCloud, Yotta, Jio Cloud, Krutrim** | regional | L40S, A100, H100 | per‑hour | ₹‑denominated; competitive, data‑residency |

**Guide:** dev/burst → RunPod/Vast/Modal (cheap, per‑second); production video → rented A100/H100 or a
cloud with reserved/spot; data‑residency → Indian providers; serverless media models → Replicate/fal.

### Hyperscalers rent the WHOLE box (CPU + RAM + GPU + network)
A GPU instance is **not just a GPU**: you rent vCPU + RAM + GPU(s) + network, and (usually separately)
disk. Some have **local NVMe included**; most use attached block storage. **Bare‑metal GPU** is also
available (full machine, no hypervisor).

| Provider | Example instance | GPU | vCPU / RAM | ~USD/hr | ~₹/hr |
|---|---|---|---|---|---|
| AWS | `g4dn.xlarge` | 1× T4 16 GB | 4 / 16 GB | ~0.5–0.7 | ~₹45–60 |
| AWS | `g5.xlarge` | 1× A10G 24 GB | 4 / 16 GB | ~1.0–1.3 | ~₹85–110 |
| AWS | `g6.xlarge` | 1× L4 24 GB | 4 / 16 GB | ~0.8–1.0 | ~₹70–85 |
| AWS | `p4d.24xlarge` | 8× A100 40 GB | 96 / 1152 GB | ~$26–32 | ~₹2,200–2,700 |
| AWS | `p5.48xlarge` | 8× H100 80 GB | 192 / 2 TB | ~$80–100 | ~₹6,800–8,500 |
| GCP | `a2-highgpu-1g` | 1× A100 40 GB | 12 / 85 GB | ~$3.3 | ~₹280 |
| GCP | `g2-standard-4` | 1× L4 24 GB | 4 / 16 GB | ~$0.8 | ~₹70 |
| Azure | `ND96asr_v4` | 8× A100 40 GB | 96 / 900 GB | ~$27 | ~₹2,300 |
| Azure | `ND-H100-v5` | 8× H100 | 96 / 640 GB | ~$80–98 | ~₹6,800–8,300 |
| Oracle OCI | `BM.GPU4.8` | 8× A100 40 GB | — / ~2 TB | ~$24–30 | ~₹2,000–2,600 |

**India regions:** AWS **Mumbai / Hyderabad** · GCP **Mumbai / Delhi NCR** · Azure **Pune / Chennai** ·
Oracle **Mumbai / Hyderabad**. Newest GPUs (H100) can be **quota‑limited / scarce** there.

**How billed:** per‑second (min 60 s) on AWS/GCP/Azure/Oracle · **spot −60–70 %** · reserved/committed
−30–60 % · storage ~$0.08–0.10/GB‑month (gp3/PD) · **egress ~$0.08–0.12/GB** · inter‑AZ traffic charged.
Approx **24/7 monthly**: 1×T4 ≈ ₹35–45 k · 1×L4/A10G ≈ ₹50–65 k · 1×A100 ≈ ₹1.8–2.0 L · 8×A100 ≈
₹16–20 L · 8×H100 ≈ ₹50–60 L (spot/reserved much less).

**Managed AI (bundles the box + MLOps):** AWS **SageMaker**, GCP **Vertex AI**, Azure **ML** — same
hardware, plus notebooks/pipelines/endpoints; **serverless inference**: AWS **Bedrock**, Vertex,
Azure AI — pay per request/token (no server management).

**Cheaper than hyperscalers** for the same GPUs: **RunPod, Vast.ai, Lambda, CoreWeave, Modal** (per‑second/
serverless). Use hyperscalers when you need **compliance, ecosystem, reserved capacity, or Indian
data‑residency**; use the others for **dev/burst/video**.

---

## 27. Where this is documented — standards & open‑source skills

**Docs / blogs / books**
- **Hugging Face** (huggingface.co): docs + blog for `transformers`, `diffusers`, **Model Cards**, Hub
  (models/datasets/spaces) — the de‑facto multi‑modal hub.
- **Anthropic** docs (**MCP**), **OpenAI** Cookbook, **Google** (A2A), **CopilotKit** (AG‑UI) — agent standards.
- **OpenTelemetry** docs (GenAI semantic conventions) · **C2PA** spec · **EBU R128** spec.
- **MLOps:** MLOps.community, Made‑With‑ML (Goku Mohandas), Chip Huyen (“Designing ML Systems”) + blog,
  Eugene Yan blog, **ThoughtWorks Tech Radar** (Ports & Adapters, architecture patterns).
- **NVIDIA Developer blog** (Triton, TensorRT‑LLM), AWS/GCP/Azure architecture centers.
- **Papers with Code**, **arXiv** for the models themselves.

**Open‑source repos (the “skills”/patterns, on GitHub)**
- Provider abstraction / gateways: **LiteLLM**, **LangChain**, **LlamaIndex**, **Vercel AI SDK**.
- Serving: **vLLM**, **TGI**, **Ollama**, **Triton**, **KServe**, **BentoML**, **Ray Serve**.
- Media: **diffusers**, **ComfyUI**, **AUTOMATIC1111**, **Real‑ESRGAN**, **whisper.cpp**, **so‑vits/piper**.
- Agents: **OpenAI Agents SDK**, **LangGraph**, **AutoGen**, **CrewAI**, **Semantic Kernel**,
  **modelcontextprotocol/servers**, **google/A2A**, **CopilotKit/AG‑UI**.
- MLOps: **MLflow**, **Kubeflow**, **Ray**, **Feast**, **DVC**.
- Curated lists (“awesome‑*”): `awesome-mlops`, `awesome-llm-apps`, `awesome-diffusion-models`,
  `awesome-ai-agents`, `awesome-mcp-servers`, `awesome-vector-databases`.
- Agent **skills** (emerging): Anthropic **Claude Skills**, MCP servers as reusable tools,
  `awesome-claude-skills`‑style collections.

**Takeaway:** everything in this document is documented industry practice — use these sources to
implement the adapters/generators/packs/agents rather than writing from scratch.

---

## 28. GPU models explained (what T4 / A10G / L4 / A100 / H100 are)

| GPU | Arch / year | VRAM | Power | Best for |
|---|---|---|---|---|
| **T4** | Turing 2018 | 16 GB GDDR6 | ~70 W | cheap inference; STT / OCR / small image |
| **V100** | Volta 2017 | 16/32 GB HBM2 | 250–300 W | legacy training |
| **A10G** | Ampere 2021 | 24 GB GDDR6 | ~150 W | inference + light media; image / small video |
| **A40** | Ampere 2021 | 48 GB GDDR6 | ~300 W | pro graphics + inference |
| **L4** | Ada 2023 | 24 GB GDDR6 | ~72 W | efficient inference + **video** (NVENC/NVDEC) |
| **L40S** | Ada 2023 | 48 GB GDDR6 | ~350 W | diffusion / video / 3D + graphics; FP8 |
| **A100** | Ampere 2020 | 40 / 80 GB HBM2e | 250–400 W | training + heavy inference; **video-gen** |
| **H100** | Hopper 2022 | 80 GB HBM3 | 350–700 W | top training / large models; FP8, NVLink |
| **H200** | Hopper 2024 | 141 GB HBM3e | ~700 W | LLM inference (big memory) |
| **B200 / GB200** | Blackwell 2024–25 | 192 GB HBM3e | ~1000 W+ | frontier |
| **RTX A6000 / 6000 Ada** | Ampere / Ada | 48 GB | ~300 W | workstation (same family) |
| AWS **Trainium/Inferentia**, Google **TPU** | vendor | — | — | vendor accelerators |

**Rule of thumb:** T4 / A10G / L4 = **cheap inference** (L4 also video); L40S / A100 / H100 =
**generation, video, training**; more VRAM = bigger models/video.

---

## 29. Cheaper GPU clouds & India providers

**Cheaper than hyperscalers** (all **usable online from India**, pay by card; data sits in their region):

| Provider | Type | Notes |
|---|---|---|
| **Vast.ai** | marketplace | cheapest; hosts worldwide (filter by region); 3090/4090/A100 |
| **RunPod** | GPU cloud | per-second; community + secure clouds; 4090/A100/H100 |
| **Lambda Labs** | GPU cloud | A100/H100; reservations |
| **CoreWeave** | GPU cloud | H100/A100/L40S; enterprise |
| **Modal** | serverless | per-second, scale-to-zero; A100/H100 |
| **Together / Fireworks / Replicate / fal / Baseten** | serverless inference | pay per run / token |
| TensorDock, Hyperstack, DataCrunch, Nebius, Paperspace, Salad | GPU clouds | alternatives |

- **Do they need to be in India?** No — they are **accessed fully online** and latency from India is
  fine. Pick an India region only for **data-residency / compliance**. (Vast's marketplace may have some
  India hosts; most others are US/EU/Asia.)

**India GPU providers (besides AWS/GCP/Azure/Oracle):**

| Provider | Notes |
|---|---|
| **E2E Networks** | NVIDIA partner; GPU cloud; INR |
| **NeevCloud** | India GPU cloud; A100/H100 |
| **Yotta (Shakti Cloud)** | Hiranandani; GPUs + datacenters |
| **Jio Cloud** | Reliance; GPU/AI cloud (freemium) |
| **Krutrim (Ola)** | cloud + GPUs |
| **Jarvislabs.ai** | India GPU cloud; INR billing; per-hour |
| Sify / CtrlS / ESDS / NTT Netmagic / Tata Comm | datacenter + GPU / colocation |
| **IndiaAI Mission compute portal** | govt-backed subsidised GPU access |

**Guide:** dev/burst → Vast / RunPod / Modal · video production → A100/H100 (spot / reserved) ·
India data-residency → E2E / NeevCloud / Yotta / Jio / Krutrim / Jarvislabs · subsidised → IndiaAI compute.
