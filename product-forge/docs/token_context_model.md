# Token / Context-Window / Multi-Modal Model Reference

> Reference for how input size, context windows, and multi-modal I/O work in the Product Forge
> pipeline. Related: `core/context_policy.py`, `core/orchestrator/llm_client.py`,
> `core/id_index.py`, backlog BI-0169 (overflow) and BI-0170 (multi-modal).

## 1. Token ↔ size (English text)

- 1 token ≈ **4 chars** ≈ **0.75 words** (English).
- **1,000,000 tokens ≈ 4,000,000 chars ≈ ~3.8 MB of text ≈ ~750k words ≈ ~1,300–1,500 pages.**
- Code/markdown is denser (more chars per token); non-English can be fewer chars/token.
- So the current tier (1M-token window) holds **~3–4 MB of text per call**; beyond that the
  **map-reduce overflow path** kicks in (see §3).

| Window | ≈ chars | ≈ size | ≈ words | ≈ pages |
|---|---|---|---|---|
| 8K tokens | ~32K chars | ~30 KB | ~6K | ~12 |
| 32K tokens | ~128K chars | ~120 KB | ~24K | ~48 |
| 128K tokens | ~512K chars | ~0.5 MB | ~96K | ~190 |
| 1M tokens | ~4M chars | ~3.8 MB | ~750K | ~1,300–1,500 |

## 2. The agent input budget

An agent's prompt = **instructions + knowledge/skills/domain/techstack + upstream artifacts
(context)**. Fetch/injection is bounded by:

```
max_context_tokens = min(contract.max_input_tokens, 0.8 * model.context_window)
max_context_chars  = max_context_tokens * 4        # rough estimate
```

Instructions are added **full** (never truncated); the **context** is what the budget governs.

## 3. Overflow flow (> window) — nothing lost, one coherent file

```
Agent prompt assembled
        │
   llm_client._call_llm
        │
  tokens_est <= 0.8*window ? ──yes──► ONE call ──► artifact
        │ no
        ├─ larger-window model in tier? ──yes──► ONE call (model-upgrade)
        │ no
        └─ CHUNK  (split by artifact + SPLIT-BY-SIZE within a huge artifact)
              MAP   : each chunk → DENSE DIGEST (facts/ids/decisions, NOT the artifact)
              REDUCE: instructions + all digests → ONE coherent artifact
                      (if still too big → compress digests → reduce again)
                          ▼
                 single coherent artifact saved   (nothing lost)
```

Key points:
- **Split-by-size** makes even a single oversized incoming artifact fit.
- **Map-reduce** (not naive concat) yields ONE coherent artifact — correct file contents.
- **Model-upgrade** tries a larger-window model before chunking.

## 4. Multi-modal I/O (image / voice / video / sensor / 3D)

Today the pipeline is **text-only** for agent I/O. Multi-modal is a **media layer** (new
capability, BI-0170). Two conversions:

### Media → text (input)
- **Voice (STT):** audio → transcript → normal text path.
- **Image (vision):** (a) send the image to a **vision model** as a message part (true
  multi-modal), or (b) **caption/OCR → text**.
- **Video:** sample frames + captions + audio transcript → text (bounded), or a video model.
- **CAD / 3D / sensor:** geometry/metadata loader → structured text/JSON.
- Media become **referenced assets with ids** (like artifacts) so traceability holds.

### Text → media (output)
- The agent emits **text**; a **render step** produces media: text→**image** (diffusion),
  text→**video**, text→**speech** (TTS), text→**3D/print**.
- Same "canonical artifact + derived formats" idea already used for md→pdf/xlsx/csv, extended to media.

## 5. Context cost per modality (why multi-modal is expensive)

| Modality | Rough token cost |
|---|---|
| Text | ~4 chars/token |
| Image | ~750–1,500 tokens per 1024×1024 (model-dependent, resolution-tiled) |
| Audio (speech) | ~10–25 tokens/sec |
| Video | frames × per-image + audio → **thousands → millions** → blows the window fast |

So for media you **sample / downscale / summarize** (few frames, STT, captions) and apply the
**same overflow discipline** (bounded digests + reduce) **per modality**.

## 6. What multi-modal needs (new capability — BI-0170)

1. **`modality`** field on knowledge/skills (`text | image | audio | video | 3d | sensor`) +
   a `knowledge_router` branch.
2. **Media loaders** (STT, vision/OCR, frame-sampler, geometry) → text/assets.
3. **Media generators** (image/video/TTS/CAD) as the output render step.
4. **Multi-modal models** in the registry/tiers (vision/audio/video) + routing.
5. **Asset ids + traceability** for media (like artifacts).

**Net:** text (incl. its overflow) is handled today; true multi-modal I/O is a new layer —
bounded digests + generators, reusing the same overflow and artifact/id discipline.
