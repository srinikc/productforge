# Multi-Modal Architecture Support — Product Forge (terminal view)

Terminal/monospace view of how the **existing text/LLM pipeline** and the **multi-modal layer**
(image / video / voice / music / 3D / OCR / sensor) come together as **one e2e pipeline**.
Companion: `docs/tools-and-generators.md`. Backlog: BI-0185 epic (backend) + BI-0138 epic (dashboard).

---

## 1. System diagram (ASCII)

```
                          PRODUCT FORGE — ONE PIPELINE (text/regular + multi-modal)
╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║ ORCHESTRATOR · stage_runner (0..13b) · agent_runner · job_manager · model_router                  ║
║ config/: pipeline-definition.json · model-tier.json · model-catalog.json · capability-packs.json  ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝
        │                          │                                    │
        ▼                          ▼                                    ▼
┌───────────────────┐  ┌──────────────────────────┐   ┌────────────────────────────────────────────┐
│ EXISTING PIPELINE │  │ CAPABILITY LAYER (NEW)    │   │ MODEL / ADAPTER LAYER (NEW)                │
│ (text/LLM)        │  │                           │   │                                            │
│ P1 0 ideation     │  │ modality detect           │   │ kind-aware router (BI-0193)                │
│    0a discovery   │─►│  core/modality.py         │──►│   reads model-catalog.json                 │
│ P2 0b..0e business│  │ capability-strategist 0f  │   │   kind,provider_kind,billing_unit,         │
│ P3 1..1d design   │  │  capability-packs(0189)   │   │   unit_price,free,open_weights,license     │
│ P4 2,3 architect  │  │  post-ideation gate(0210) │   │         │                                  │
│ P5 4-0,4a..4f     │  │  strategy refine(0192)    │   │         ▼                                  │
│      └► 4m media  │  └──────────────────────────┘   │  ADAPTER REGISTRY                          │
│ P6 5,6,7 verify   │                                 │   ├─ LocalModelAdapter (self-host)         │
│ P7 8,9..12 deliver│                                 │   ├─ DirectVendorAdapter (OpenAI/Google/…) │
│ P8 13..13b operate│                                 │   └─ AggregatorAdapter (fal/Replicate/kie) │
└─────────┬─────────┘                                 │         │                                  │
          │                                           │         ▼                                  │
          │                                           │ GENERATORS/MODELS:                        │
          │                                           │  image·video·tts·stt·music·3d·ocr·        │
          │                                           │  embed/rerank·timeseries·VLM              │
          │                                           │      ┌────────┴─────────┐                 │
          │                                           │      ▼                  ▼                 │
          │                                           │ MODEL DOWNLOADER   PROVIDER KEY REGISTRY  │
          │                                           │ (0206: HF/ModelScope (0207: keys,         │
          │                                           │  license gate,       allowlist, cost caps)│
          │                                           │  models.lock)                             │
          │                                           └──────────┬────────────────┘               │
          │                    ┌─────────────────────────────────┴──────────────┐                 │
          │                    ▼                                ▼                ▼                 │
          │            MEDIA AGENTS (0190)              ASSET STORE (0187)   MEDIA QA (0191)       │
          │      capability-strategist · media-analyst   artifacts+media+     probe·loudness·      │
          │      media-generator · media-editor          index                phash·A-V sync        │
          │      asset-librarian · doc-analyst                                                │
          │      sensor-analyst · media-qa                                                    │
          └───────────────────────────────────────────────────────────────────────────────────────┘
                 non-media project enables NO pack → identical to today (40 stages, 62 agents)
```

---

## 2. End-to-end run sequence

```
idea
 → 0  ideation
 → 0a discovery            (+ media-analyst / doc-analyst / sensor-analyst if assets arrive)
 → 0f capability-strategist [detect modalities, ENABLE packs, pick kinds + free/paid]     ◄ NEW stage
 → 0b..0e business/market/monetization   (+ per-unit media cost)
 → 1..1d design            (+ media/asset design: storyboards, voice, assets)
 → 2  architect            (+ media services, adapters, asset store)   ← refine strategy (BI-0192)
 → 3,3a requirements / QA
 → 4-0,4a..4f implementation ─┬─ code path (existing agents: implement/devops/code-review/validate)
                              └─ 4m media production: media-generator → media-editor → asset-librarian ◄ NEW stage
 → 5,6,7  verify           (+ media-qa: probe / loudness / phash / A-V sync)
 → 8  document             (+ captions / transcripts)
 → 9  package              (+ bundle-licence check via BI-0211)
 → 10..13 deliver / operate
```

---

## 3. Existing pipeline it plugs into (unchanged when no pack is on)

| Phase | Stages | Agents |
|---|---|---|
| P1 Ideation & Discovery | 0, 0a | ideation, discovery |
| P2 Business/Market/Monetization | 0b, 0c, 0d, 0e | product-owner, researcher, pricing-strategist, marketing |
| P3 Design | 1, 1a, 1b, 1c, 1d | design, product-design-spec, design_critic, ux-ia, researcher |
| P4 Architecture | 2, 3, 3a | architect, orchestrator, validate |
| P5 Implementation | 4-0, 4a..4f (+ −vqa) | implement, devops, code-review, validate, visual_qa |
| P6 Verification | 5, 6, 7 | security, validate |
| P7 Delivery | 8, 9, 10, 10a, 11, 12 | document, package, devops, orchestrator, validate, production-deploy |
| P8 Operate, Grow & Engage | 13, 13a, 13b | observer, customer-success, growth |

A plain text/LLM project enables **no** capability pack: same 40 stages, same 62 agents, same cost.

---

## 4. Media / IoT agents — role & what they do

Eight new agents, **added to the roster only when their capability pack is enabled**. Each reuses the
existing orchestrator / stage / job / QA machinery — they do not fork the pipeline.

| Agent | Role | What it does | Key models / tools |
|---|---|---|---|
| **capability-strategist** | Decide *what* multi-modal capability is needed | After ideation it reads the idea, detects modalities, enables the matching capability packs, picks model **kinds** + a free/paid mix, and writes `capabilities.json` — so design/architecture know what media exists. | existing text tier; `core/modality.py`, catalog, packs |
| **media-analyst** | *Understand* media | Alt-text, scene/shot summaries, transcripts, tags for any provided or generated asset. | Qwen2.5-VL / InternVL / SmolVLM · Whisper (ASR) · CLAP |
| **media-generator** | *Produce* media | Generates image / video / music / 3D / voice from prompts + specs via adapters. | FLUX.1-schnell·Sana · Wan 2.2·Mochi·CogVideoX · ACE-Step · TripoSR·TRELLIS · Kokoro·Piper · Whisper |
| **media-editor** | *Process / assemble* media | Cut, merge, transcode, subtitles/burn-in, format packs — turns raw assets into deliverables. | FFmpeg · MoviePy · Blender (external) |
| **asset-librarian** | *Organize* media | Indexes the asset store, metadata, dedupe (perceptual hash), provenance + licence tracking. Cross-stage. | BGE / CLIP embeddings · phash · asset store |
| **doc-analyst** | *Read documents* | OCR/document → structured text/tables/layout. | Tesseract·PaddleOCR·RapidOCR·docTR (+Qwen-VL) |
| **sensor-analyst** | *Handle IoT / time-series* | Ingest (MQTT/serial/BLE/Modbus), anomaly detection, forecasting, TinyML packaging. | IsolationForest/autoencoder · DLinear/PatchTST/Chronos · TFLite Micro |
| **media-qa** | *Validate* media | ffprobe (codec/duration), loudness (EBU R128), perceptual hash, A/V sync, caption/schema checks. | validators (ffprobe, loudness, phash) |

**Grouping by job:** decide (`capability-strategist`) · understand (`media-analyst`, `doc-analyst`,
`sensor-analyst`) · create (`media-generator`, `media-editor`) · organize (`asset-librarian`) ·
verify (`media-qa`).

**Per-agent I/O**

| Agent | Input | Output |
|---|---|---|
| capability-strategist | idea / requirements text (+detected modalities) | `capabilities.json`, enabled packs, kind + free/paid plan |
| media-analyst | image / audio / video (+ text context) | descriptions, transcripts, tags, scene breakdowns |
| media-generator | prompts / specs + reference assets + chosen kind/model | generated image / video / audio / music / 3D / speech assets |
| media-editor | raw assets + edit spec (timeline, captions) | composed media (cut/merged/subtitled/transcoded) |
| asset-librarian | all assets + metadata | indexed asset store, dedupe, provenance/licence records |
| doc-analyst | documents / scans / PDFs / images | structured text, tables, layout, page confidence |
| sensor-analyst | time-series / sensor streams | cleaned series, anomalies, forecasts, TinyML models |
| media-qa | finished media artifacts | pass/fail + metrics (probe/loudness/phash/A-V sync) |

---

## 5. Inputs → agents → final product (the processing flow)

Inputs are **not only a text idea**. A project can start from (or accumulate) any of:

- **text idea** (always) — the pipeline's normal entry.
- **image / video / voice / audio** — reference or source assets (brand, footage, recordings).
- **documents** — PDFs, scans, spreadsheets (OCR).
- **sensor / time-series** — device data or streams.
- **existing files / datasets / URLs** — anything already produced upstream.

All inputs pass through **one flow** (the existing stages, plus the two new media stages):

```
 INPUTS                    STRATEGY              UNDERSTAND              CREATE / EDIT           ORGANIZE / VERIFY        OUTPUT
 ┌────────────┐         ┌──────────────┐       ┌──────────────┐       ┌───────────────┐       ┌────────────────┐     ┌──────────────┐
 │ text idea  │         │ capability-  │       │ media-analyst│       │ media-generator│      │ asset-librarian│     │ FINAL PRODUCT│
 │ image      │         │ strategist 0f│       │ doc-analyst  │       │ media-editor   │      │ media-qa       │     │  app + media │
 │ video  ────┼──ingest►│  (kinds +    │─packs►│ sensor-analyst│─specs►│  (adapters →   │─assets►│  (index, phash,│────►│  bundle +    │
 │ voice/audio│         │  free/paid)  │       │              │       │   models)      │      │   QA)          │     │  docs/assets │
 │ document   │         │  writes      │       │              │       │                │      │                │     │              │
 │ sensor     │         │  capabilities│       │              │       │                │      │                │     │              │
 │ files/URL  │         │  .json       │       │              │       │                │      │                │     │              │
 └────────────┘         └──────────────┘       └──────────────┘       └───────────────┘       └────────────────┘     └──────────────┘
```

**How it works:**
1. **Strategy (0f):** `capability-strategist` transforms the idea + any inputs into a capability profile
   (which modalities, which packs, which kinds, free/paid) → `capabilities.json`.
2. **Understand:** `media-analyst` / `doc-analyst` / `sensor-analyst` extract meaning from the provided
   inputs (descriptions, transcripts, tables, anomalies) → these become design/architecture context.
3. **Create/edit (4m):** `media-generator` produces new assets via adapters/models; `media-editor`
   assembles them into deliverables.
4. **Organize/verify:** `asset-librarian` indexes + tracks provenance/licence; `media-qa` validates.
5. **Output:** the existing `document`/`package`/`deploy` stages ship the **final product**, now
   including media assets, transcripts/captions, and licence records.

A **text-only** project simply skips strategy-media/understand-media/create steps (no pack enabled) and
produces the same output as today.

---

## 6. Are only these agents needed?

**Short answer: yes, the eight cover the lifecycle.** The pipeline needs *decide → understand → create →
edit → organize → verify*, and those eight do exactly that. To avoid roster bloat, **related duties are
folded into existing agents** rather than spawning new ones:

| Need | Handled by (extend, don't add) |
|---|---|
| Media services in the tech stack / asset-store design | `architect` |
| Storyboards, shot lists, visual/IA design | `design`, `product-design-spec`, `ux-ia` |
| Media docs, captions, transcripts docs | `document` |
| Alt-text / caption accessibility | `a11y-audit` |
| Media/asset threat surface (upload, generated content) | `security` |
| Rights: likeness/voice consent, input-asset licensing, PII | `legal-privacy` (+ `asset-librarian`) |
| Content safety / moderation of generated media | `guardian` (+ `media-qa` validators) |
| Per-unit media cost, ROI | `finops`, `pricing-strategist` |
| Bundle-licence compliance | `package` (via BI-0211 catalogue) |
| Growth / personalization of media products | `growth`, `product-analytics` |

**Optional, only if we want stricter separation** (not required e2e): a dedicated `media-safety`
(moderation), `media-localizer` (translation/dubbing), or `media-planner` (storyboard) agent. These can
be split out later if the folded duties grow; today they are covered by the agents above.

---

## 7. Component locations

| Concern | Location | Backlog |
|---|---|---|
| modality detect + capability packs | `core/modality.py`, `core/capability_packs.py`, `config/capability-packs.json` | BI-0189, BI-0210, BI-0213 |
| adapters / router | `core/adapters/*`, `core/orchestrator/model_router.py`, `config/model-catalog.json` | BI-0193, BI-0188 |
| generators registration | `config/model-catalog.json` (media `output_modalities`) | BI-0188 |
| model download + licence gate | `core/model_manager.py`, `models.lock` | BI-0206 |
| provider keys / caps | `config/provider-keys.json` | BI-0207 |
| media agents + stages | `agents/*.agent.json`, `pipeline-definition.json` (composed) | BI-0190, BI-0213 |
| asset store + media QA | `core/asset_store`, `core/media_qa` | BI-0187, BI-0191 |
| per-unit costing | `core/budget_planner.py` (+ allocator) | BI-0194 |
| OCR / sensor packs | capability packs + adapters | BI-0209, BI-0208 |
| licence/bundle gate | `config/tool-catalog.json` + packaging | BI-0211 |
| dashboard surfaces | dashboard epic | BI-0138..BI-0145 |
