# Multi-Modal Model Selection — Dynamic / Staged Decision

**Status:** analysis + plan. Backlog: epic **BI-0185**; relates to **BI-0189** (capability packs),
**BI-0192** (two-phase strategy gate), **BI-0193/BI-0194** (this doc's concrete pieces).
**Scope:** backend — WHERE and WHEN the pipeline should decide model types + capabilities per project.

---

## 1. Problem — we decide too early, in one phase
- The tier/model set is chosen at **creation** (`config/model-tier.json:active_tier`, or a per-project
  `model-tier.json`) and `_run_model_fit_preflight()` runs **at run start** (`pipeline_executor.py:2864`),
  **before any stage**.
- At that point the idea's modality / complexity is unknown, so the model strategy cannot match the project.
- Real capability needs are only known **after** discovery (0a) + design (1) + architect (1b).
- Result: a media project could start on text-only models; the model choice is effectively fixed for the
  whole run regardless of what the idea turns out to need.

## 2. What each stage actually KNOWS
| Stage | Known by now | Enough to decide… |
|---|---|---|
| **0 ideation** | raw idea/seed (text) | coarse **modality/capability** (idea text → media?) |
| **0a discovery** | scope, MVP, domain, constraints, data/deployment | modality **confirmed** + rough complexity |
| **0b/0c** | product definition, market | priority / complexity signals |
| **1 design** | features, functional specs, UI behaviour | **which agents run** + per-agent model *type* |
| **1b architect** | tech stack, architecture, chosen tools | **provider / generator specifics** |

## 3. "The decision" is really THREE decisions (different information needs)
1. **Capability / modality packs** — is this a media project, and which modalities?
2. **Model type per agent** — text vs vision vs audio vs video vs generator.
3. **Tier / quality / cost + specific providers** — how strong/expensive, which stack.

## 4. Where each belongs (the answer)
- **(1) capability/modality → ideation (0) is viable** (idea text alone detects modality; `modality.detect`
  already does this). Discovery (0a) **confirms** it.
- **(2) model type per agent → design (1)** — needs to know which agents will run.
- **(3) tier/provider specifics → architect (1b)** — needs the tech stack; safe because generators are only
  needed at implement (4).

**If you must pick ONE place:** **discovery (0a)** — earliest point that is both early and informed.
**Not architect alone** (too late for the design stage), **not ideation alone for everything** (tier/agents
unknown).

**Edge case that forces ideation:** if the pipeline can **start with media input** (uploaded reference
image/audio/video, mood board), then **stage 0 itself must read media** → the capability decision **must** be
at/near **ideation (0)**, because you cannot discover/design without a modality-aware model from call one.

## 5. Recommended plan — detect → enable → decide → apply (pluggable, gated)
| Step | Where | What | Reuses | Backlog |
|---|---|---|---|---|
| **Detect** | 0a (or 0 if media-in) | write `required_capabilities` (modalities + domain) | `modality.detect` | BI-0189 |
| **Enable** | after detect | turn on matching capability packs | capability packs | BI-0189 |
| **Decide** | after 1/1b | choose per-agent model types + tier; persist a strategy artifact | `tier_builder`, `model_fit` | BI-0192 |
| **Apply** | before 2… | apply via `model_router` / per-agent override | BI-0178 override | BI-0192 |

**Two touchpoints (best shape):**
- **detect modality/capability at 0/0a** (coarse — enables packs),
- **decide model types + tier at 1/1b** (informed — before implement).

**Gating:** the decide step only activates when `required_capabilities` is non-trivial → **plain (text)
projects keep today's behaviour untouched.**

## 6. Is it required, or is what we have good enough?
- **Text projects:** current one-phase early selection is **good enough** — no change needed.
- **Multi-modal/media projects:** **not good enough** — needs the staged decision.
- **Size:** the decision logic is **small** (read artifacts → decide → persist → apply — orchestration glue).
  The **big** work is the media enablers (plumbing, ingest, generators). So **sequence the decision AFTER**
  detection + packs; it has nothing to decide from until they exist.

## 7. Gap list (vs what exists)
| Piece | Status |
|---|---|
| modality detection persisted as a project profile | missing (store) |
| capability packs (the switch) | missing (BI-0189) |
| model-strategy decision step | missing (BI-0192) |
| model-strategy artifact persisted | missing (store) |
| decision policy (auto vs blocking) + media-bootstrap re-run path | missing (mechanics) |
| media plumbing / ingest / generators | missing (the big work) |

## 8. Open policy questions
- Blocking gate (human approves the strategy) or auto with override?
- If Phase A lacked a needed modality, auto re-run 0a/1/1b after the pack turns on?
- Strategy scope: per-project strategy file vs applied as per-agent overrides?

## 9. Sequencing (why this order)
detect → enable → decide → apply. Building the decide step before packs leaves it nothing to switch on;
before detection, nothing to decide from. So: **packs + detection first, strategy gate second.**
