# Model-tier timing & multi-modal flow (research / recommended design)

> Question: **when** should the right model be applied to each agent/role — at project
> creation, or only after ideation/discovery? And how do multi-modal (image/voice/video/3D/
> sensor) projects get the right models? This doc proposes the flow.

## 1. The problem with assigning models at creation time
At project creation we know only the **raw idea** — not the product type, required
reasoning depth, tool needs, context size, or modality (text/voice/video/image/3D/sensor).
So a tier picked at creation is a **guess**.

The pipeline discovers the truth progressively:
- **0 ideation** → shape of the product
- **0a discovery** → clarified goal
- **0b–0e** → business model, market, monetization, GTM
- **1 design / 2 architect** → **capabilities, tech stack, and modalities** are finally known

## 2. Recommended flow — bootstrap at creation, optimise after discovery/architect
```
create project
   └─ pick a BOOTSTRAP tier (general text models) — enough for 0 / 0a / 0b–0e / 1
        │
        ▼
run 0 ideation → 0a discovery → 0b–0e business → 1 design → 2 architect
        │   (here: product type, stack, and MODALITIES become known)
        ▼
AUTO-ASSIGN models per agent   ← core/model_catalog + core/model_fit
   - needs: tools · reasoning · structured_outputs · min_context · min_output · modality
   - pick best-fit model per agent (rank fit → cost → speed); flag not-good with reasons
        │
        ▼
run build/verify with the RIGHT models   (optional dynamic shift on failure)
```
**So:**
- **Tier selection at creation = bootstrap** (safe defaults).
- **Capability-driven (re)assignment = after architect (stage 2)** — earliest useful point is
  **design (1)**; the **stack is known at 2**.
- **Dynamic shift** = only on a fit/behaviour failure during the run (see fallback ladder).

## 3. Multi-modal projects — how they work
Two kinds of "model" are needed:

| Need | Model class | Source |
|---|---|---|
| Text reasoning/tools | LLM (this catalog) | 163 models |
| **Media IN** (image/audio/video) | multi-modal **LLM** | **65 models** already accept image/audio/video input (catalog `input_modalities`) |
| **Media OUT** (image/video/voice/3D) | **generators** (diffusion/TTS/video/3D) | **NOT in the LLM catalog** — must be registered as their own `kind` |

Catalog today: input `text 92 · image 65 · video 20 · audio 15 · file 39`; **output = text only**.
⇒ The pipeline can **consume** media (vision/STT/frames) today via multi-modal LLMs, but
**producing** media needs **generator models** added to the registry (`kind: generator`) +
a render step (text→image/video/audio/3D).

**Multimodal project creation flow:**
1. Discovery detects the modality need (e.g., "voice companion", "video generation").
2. Ensure **input**: assign a `vision`/`audio`/`video`-capable model to the relevant agents.
3. Register/enable the **generator** for the output modality (image/video/TTS/3D) in the
   knowledge/model registry (`kind: generator`).
4. Create the project with the modalities declared → the pipeline uses the right models.

So **yes** — any multi-modal project can be created, provided the **input modality model**
and the **output generator** are available; the catalog shows which models support which
modalities, so assignment can filter by modality.

## 4. Will tier creation SHOW modality support?
**Yes** — the catalog now carries `input_modalities` / `output_modalities` per model. The
tier-creation UI (BI-0135) should display, per model: `provider · context · max_output ·
tools · reasoning · structured_outputs · input modalities · output modalities · price`,
plus the per-agent fit verdict. → filter the model list by required modality when assigning.

## 5. Bottom line
- Assign a **bootstrap** tier at creation; **optimise after discovery/architect**.
- **Model, not tier, is the unit of assignment** — tier = a named bundle of agent→model picks.
- **Input multi-modal is ready** (65 models); **output multi-modal needs generator models**.
- Everything is data-driven from `config/model-catalog.json` + `config/agent-capabilities.json`.
