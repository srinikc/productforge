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

## 4. New media / IoT agents (pack-gated)

| Agent | Role | Model(s) | Stages |
|---|---|---|---|
| capability-strategist | detect modalities → enable packs → pick kinds + free/paid | existing text tier | `0f` (new) |
| media-analyst | understand assets (alt-text, scenes, transcripts, tags) | Qwen2.5-VL / InternVL / SmolVLM, Whisper, CLAP | `0a`,`1d`,`1`,`4m` |
| media-generator | generate image / video / music / 3D / voice | FLUX.1-schnell·Sana, Wan 2.2·Mochi·CogVideoX, ACE-Step, TripoSR·TRELLIS, Kokoro·Piper, Whisper | `4m` (new) |
| media-editor | cut/merge/render/transcode/subtitles | FFmpeg, MoviePy, Blender (external) | `4m`, `9` |
| asset-librarian | index, metadata, phash dedupe, provenance/licence | BGE / CLIP embeddings | cross-stage |
| doc-analyst | OCR/document → structured text/tables | Tesseract·PaddleOCR·RapidOCR·docTR (+Qwen-VL) | `0a`,`1`,`4m` |
| sensor-analyst | time-series ingest, anomaly, forecast, TinyML | IsolationForest/autoencoder, DLinear/PatchTST/Chronos | `1b`,`2`,`4m` |
| media-qa | probe, loudness, phash, A-V sync, captions | — (validators) | `5`,`6` |

Existing agents gaining media duties: architect, document, a11y-audit, security, package, finops/pricing-strategist.

---

## 5. Component locations

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
