# Multi-Modal Orchestration — Product Forge

**Status:** reference / design. Backlog: epic **BI-0185** + sub-items (BI-0186…BI-0191).
**Scope:** backend (how the pipeline handles projects that involve non-text media — image, audio, video,
3D, and the tools alongside LLMs).

---

## 1. What "multi-modal" means here
Two independent axes:
- **Input modalities** — what an agent can *read* (image / audio / video / file).
- **Output modalities** — what can be *produced* (text vs. generated **media**: image / video / audio / 3D).

Our catalog is strong on **input** (understanding) and **absent on media output** (generation).

## 2. What we have today (catalog facts — `config/model-catalog.json`, 163 models)
Distinct modality values present: **`text, image, video, audio, file`** (nothing else).

| Input modality | # models | examples |
|---|---|---|
| text | 92 | all chat models |
| image | 65 | `claude-opus-5`, `gpt-5.6-sol`, `gemini-3.7-flash`, `deepseek-v4-flash-vision-exp` |
| file | 39 | `gpt-5.6-*`, `claude-*` |
| video | 20 | `gemini-3.7-flash`, `glm-5.3-flash`, `kimi-k3`, `mimo-v2.6-pro` |
| audio | 15 | `gemini-3.7-flash`, `muse-spark-1.2`, `mimo-v2.6-pro` |

**Output modality: `text` only (92) — 0 media generators.**

**Multi-modality distribution (inputs):** `0 → 71 · 1 → 26 · 2 → 18 · 3 → 33 · 4 → 5 · 5 → 10`
- **All 5 inputs** (10): the **Gemini** fleet (`gemini-2.5-pro/flash/flash-lite`, `3.5-flash`, `3.5-flash-lite`, `3.6-flash`, `3.7-flash`) + **`muse-spark-1.2`, `muse-spark-1.2-contributor`, `muse-spark-1.3-contributor`** (ctx ~1.05M).
- **4 inputs** (5): `mimo-v2.6-pro/flash`, `mimo-v2.5`, `xiaomi/mimo-v2.6-flash`, `xiaomi/mimo-v2.5`.
- **3 inputs** (33): `gpt-5.x` (file+image+text), `claude-opus/sonnet-*`, `grok-4.x`, `qwen3.x`, `kimi-k3`, `glm-5.3-flash`, `minimax-m3`, `o3/o4-mini`.

**Other modality types we do not yet model** (to add when generators/assets exist): 3D/mesh,
depth/point-cloud, sensor/timeseries, tabular, music, embeddings.

## 3. Generators — the missing half
A **generator model** *emits* media (diffusion / transformer generative models), unlike chat LLMs.
Our catalog is an **LLM gateway**, so it has none.

Market examples:
- **Image:** Google Imagen / *"Nano Banana"* (Gemini image), GPT-Image, **FLUX** (BFL), Stable Diffusion, Midjourney, Seedream, Recraft.
- **Video:** Sora, Veo, **Runway** Gen-4/4.5, Kling, Pika, Luma Ray, MiniMax Hailuo/H3, HunyuanVideo, **Wan**, Seedance, LTX, NVIDIA Cosmos.
- **Audio/Voice:** ElevenLabs, OpenAI TTS, MiniMax Audio, Kokoro/XTTS/Bark.
- **Music:** Suno, Udio, ACE-Step.

## 4. How the leaders do it (Runway / Nano Banana / Gemini / GPT)
Not one model — an **agentic 3-layer stack**:
1. **Reasoning LLM** — plans, writes prompts, critiques output.
2. **Generator models** — text→image, image→video, video→video, TTS.
3. **Editing/compositing tools** — ffmpeg, inpainting, upscalers, keyframe/continuation (e.g. Runway motion-brush; Wan Animate motion transfer; FLUX 3 native-audio multi-shot chaining).

Media creation is **tools + generators, steered by LLMs** — not LLMs alone.

## 5. Tooling we can use (with distribution licenses)
| Layer | Tools | License |
|---|---|---|
| Graph runner | **ComfyUI** (SD/FLUX/Wan/Hunyuan/Cosmos) | GPL-3.0 (core) |
| Image gen | **FLUX.1-schnell** ✅; SD/SDXL (OpenRAIL-M ⚠); SD1.5 (CreativeML ⚠) | mixed |
| Video gen | **Wan 2.2** (Apache-2.0 ✅); HunyuanVideo (Tencent ⚠); MiniMax H3 (open weights, **non-commercial** ⚠); LTX | mixed |
| Audio/Voice | **Kokoro** (Apache-2.0 ✅), **Whisper** (MIT ✅), XTTS/Coqui (⚠), CosyVoice | mostly ✅ |
| Music | **ACE-Step**, MusicGen (MIT ✅) | ✅ |
| Edit/mux | **ffmpeg** (LGPL/GPL), **OpenCV**/**Pillow**/**ImageMagick** ✅, **MoviePy** (MIT), **Blender** (GPL), **Demucs** (MIT) | mostly ✅ |

**Rule:** Apache/MIT/BSD = safe to ship; GPL/LGPL = copyleft (use ok, watch bundling); OpenRAIL-M /
Tencent / MiniMax = **use-restricted or non-commercial → license needed for commercial products.**

## 6. Target architecture — pluggable capability packs
Make the pipeline **modality-agnostic** by enabling **capability packs** per project, chosen when the
idea is analysed. Nothing extra turns on unless the project needs it.

### 6.1 Layers / stages / agents
| Where | What is added |
|---|---|
| **0a discovery** | detect project modality + domain (`core/modality.py` exists) → write `required_capabilities` |
| **1 / 1b design + architect** | select the **capability pack** → becomes part of the tech stack |
| **media service** (cross-cutting) | ingest → normalize → **tile / segment / frame-sample** → per-asset summaries → **asset store** |
| **new agents** (only when the pack is active) | `media-analyst` (VLM understanding), `media-generator` (image/video/audio), `media-editor` (cut/merge/render), `asset-librarian` (store/index) |
| **4 implement** | invoke tools/generators (ffmpeg/ComfyUI/provider APIs) via the media service |
| **11 / 12 validate** | media QA — ffprobe (codec/res/fps), loudness, perceptual-hash continuity, A/V sync |
| **llm_client** | **multimodal message builder** (attach image/audio/video parts) |

### 6.2 Pluggable mechanism
- A **capability registry** (mirrors `core/knowledge_registry.py`) + **`config/capability-packs.json`**:
  `modality → { tools, generator providers, agents, validators }`.
- **Discovery emits `required_capabilities`** (modalities + domains).
- The orchestrator **enables the matching pack** (agents + tools + models) — auto or explicitly chosen.
- Effect: a **todo app enables nothing extra**; a **reels/movie/voice** idea enables the media pack.

### 6.3 Large-media strategy (split/merge)
Media is **not split by bytes**. Tokenization differs by kind, so:
- **Image:** downscale/re-encode to limits, or **tile** (overlapping patches) + re-assemble findings.
- **Audio:** time-segment + transcribe per segment.
- **Video:** **sample frames** (e.g. 1 fps) + **extract audio track**, feed a structured bundle.
- **Large sets:** per-asset summary → **map-reduce** (reuse the text pattern in `_call_llm_chunked`).

## 7. Gaps blocking this today
1. **No multimodal input plumbing** — `core/orchestrator/llm_client.py` builds **text prompts only**; the 65 image-input models receive nothing.
2. **No media ingest / segment-tile / asset store** — large image/video/audio sets unhandled.
3. **No generator adapters** (image/video/audio) + no media-agent pack + no capability-pack layer.

## 8. Backlog (epic BI-0185)
| id | item |
|---|---|
| **BI-0185** | Epic: multi-modal / media orchestration (pluggable) |
| BI-0186 | Multimodal LLM plumbing (attach image/audio/video parts) |
| BI-0187 | Media ingest + segmentation/tiling + asset store |
| BI-0188 | Generator-model adapters (open-weights image/video/audio) |
| BI-0189 | Capability-pack registry + config + discovery→enablement |
| BI-0190 | Media agents (media-analyst / media-generator / media-editor / asset-librarian) |
| BI-0191 | Media QA validators (probe/loudness/hash/A-V sync) |

Dashboard counterpart (separate): **BI-0134** — multi-modal I/O UI.

---

## 10. Provider kinds — the framework must not be text-only
Treat **all provider kinds** uniformly through adapters/aggregators/routers. A model's `kind`:
`chat · vision · image-gen · video-gen · tts · stt · music · 3d · embedding · timeseries · rerank`.

Provider shapes:
- **Direct providers** — OpenAI Images, Google Imagen/Veo, ElevenLabs, Stability, Runway, Meshy/Tripo.
- **Aggregators** — **fal.ai, Replicate, kie.ai**: **one API key + one base URL for many media models**
  (closest to "swap a base URL", but call shapes still differ per modality).
- **Self-host** — open-weights via ComfyUI/diffusers (free compute).

Uniform **Provider interface** (what our router talks to): `kind · modalities · auth · submit ·
status · fetch · cancel · cost_unit · free/open-weights/license`.

## 11. API shapes — why adapters are mandatory
| Kind | Shape |
|---|---|
| chat / vision | sync request → response |
| image-gen | sync or short job → URL/base64 |
| tts / stt | sync → audio bytes |
| **video-gen / music / 3d** | **async job**: submit → poll (or webhook) → fetch artifact |
So a chat-shaped call path cannot run media. Adapter contract: `submit(kind, payload) → job`,
`status(job)`, `fetch(job) → artifact`, `cost(job)`. Aggregators unify auth/base-URL, **not** the shape.

## 12. Pricing & free options (2026, grounded)
**Image:** fal `$0.02–0.04`/img (Seedream V4 $0.03, Flux Kontext Pro $0.04, Nanobanana $0.0398,
Qwen $0.02/MP); kie.ai resells cheaper (GPT-Image-2 1K **$0.03**, Nano Banana 2 1K **$0.04**).
**Video (per second):** Wan 2.5 **$0.05** (480p; $0.10 720p) · Kling 2.5 Turbo Pro $0.07 ·
Kling 3.0 Pro **$0.112** (audio off) → $0.168 (audio) → $0.336 (elements+audio) · Veo 3.1
**$0.20** (off)/$0.40 (on) · LTX-2.5-Pro $0.17 · Ovi $0.20/video.
**Per clip (Veo 3.1):** 1080p **$3.20** (official) / **$1.28** (kie) · 4K $4.80 / $1.85.
**Free:** fal.ai has **no free tier** (per-output + GPU $1.89–8.50/h); **free-to-run = open-weights**
(Wan 2.2, FLUX.1-schnell, Kokoro Apache-2.0 ✅; Whisper/MusicGen MIT ✅; SD/SDXL OpenRAIL ⚠;
HunyuanVideo/MiniMax H3 open weights non-commercial ⚠); **free API tiers** = HF Inference,
Cloudflare Workers AI, Google AI Studio (limited). Music: ElevenLabs Music / Suno / Udio / ACE-Step.
3D: Meshy/Tripo (hosted) / Hunyuan3D/Trellis (open). Timeseries: TimesFM/Chronos (open, not a generator).

## 13. Catalog extension — `kind` + per-unit cost (needed for routing/costing)
Add to each model entry: `kind`, `provider_kind` (direct|aggregator|self-host),
`billing_unit` (token|image|second|char|track|mesh|megapixel), `unit_price`, `free` (bool),
`open_weights` (bool), `license`. Cost = `unit_price × units` (budget-integrated). Extends BI-0173.

## 14. Runtime orchestration (after the idea) — mirrors the text path
`idea → 0a detect modality → capability packs (BI-0189) → model-strategy gate picks kind+provider per
agent incl. free/paid (BI-0192) → runtime router resolves per agent → adapters execute (async for
media) → artifacts → media QA (BI-0191)`. Same flow as text (tier → agent model → client), but
**kind-aware routing + job-based adapters**.

## 15. Costing during project creation / tier assignment
- **At creation:** provisional tier + rough cost estimate (text only).
- **After the strategy gate:** per-stage/agent cost projection **including per-unit media costs**
  (e.g. N images × $0.03, M seconds × $0.20) → budget allocator + free/paid mix surfaced.
- Agents get their tier/model **with a cost perspective**, not just capability.

## 16. E2E parity checklist (make media work *like* text)
1. registry knows the kind + unit price (13) → 2. router resolves by kind/modality/cost (14) →
3. adapters/aggregators execute incl. async jobs (10/11) → 4. artifacts land in the asset store (BI-0187) →
5. QA validates (BI-0191) → 6. cost recorded per unit (15) → 7. capability packs gate it per project (BI-0189).
