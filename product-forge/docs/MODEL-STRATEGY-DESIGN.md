# Model & Capability Strategy Gate — Design (BI-0192 + BI-0210)

## Goal
Two-phase, mid-run strategy: **Gate A (post-`0a`)** detects modality, enables capability packs, picks
coarse model *kinds* + provisional free/paid mix; **Gate B (post-architect `2`)** refines to concrete
models/providers + per-stage tier using the tech stack. Persist an **auditable strategy artifact** and
apply via the existing per-agent override/store. Plain-text projects stay **byte-identical**.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Strategy gate | **none** (no module/store) | new two-phase gate | new `core/model_strategy.py` |
| Pack enablement | `capability_packs.persist_required` (preflight only) + `save_profile` | call at Gate A; recompose | reuse |
| Composition | `pipeline_composition.effective_definition` at *load* only | **re-invoke at Gate A** + reconcile DAG | reuse |
| Per-agent override | `agent_model_override.set` (BI-0178); router precedence override>stage>parent>agent>default | apply LLM kinds here | reuse |
| Tier/recommend | `tier_builder.needs_for/score_model/recommend` (advisory) | ranking engine for kind selection | reuse |
| Model metadata | `model_catalog.capabilities/fit`; `modality.models_for_input/output` | constrain candidates | reuse |
| Feasibility | `feasibility.assess_build` (per-modality build_mode/generator/license) | consume | reuse |
| Generators | `generator_adapters.select/view` (KIND map) | media-OUT = generator (never a chat model) | reuse |
| Hooks | `stage_runner` post-`0a` `:672-687`; post-`2` `:706-725` | add Gate A / Gate B blocks | wire |
| DAG reconcile | `DAGExecutor.export_state/restore_states` (`dag_executor.py:239/159`) | available primitives | reuse |

**Correction:** the architect is stage **`2`** (`pipeline-definition.json:154`); `1b` is *Design Review*.
Gate B keys on **`2`** (documents the BI label's "1b" wording).

**Blast radius:** stage_runner (2 blocks), new module, store-registry, env-flags, tests. No new tier/pack truth.

## Design decisions (modular)
- **New `core/model_strategy.py`** — single concern; **single writer** of `products/<p>/model-strategy.json`.
  API: `gate_a(executor)`, `gate_b(executor)`, `assess(project_dir, phase)`, `decide(...)`,
  `apply(executor, decision)`, `save_report/load_report`, `verdict`. No import-time side effects.
- **Reuse, never duplicate:** modality/packs/feasibility/generators/model_catalog/tier_builder/model_router/
  agent_model_override/pipeline_composition/provider_kinds. LLM model changes go through
  `agent_model_override.set` (router already honours `source=override`); media-OUT is a *generator id*, not a
  chat model.
- **Gate A (post-`0a`):** `modality.detect(idea)` → `capability_packs.persist_required` → **re-compose**
  `pipeline_composition.effective_definition` and update `self.pipeline_def`/`model_router.pipeline_def`,
  reconcile DAG via `export_state`/`restore_states` (so pack stages like `4m`/validators exist for stage 1+).
  Pick coarse kinds; provisional mix from `feasibility`.
- **Gate B (post-`2`):** read architecture (`docs/tech-stack.json`) + vector + pack kinds; refine concrete
  models per agent via `tier_builder.recommend` over a modality-filtered pool; `apply` via override store.
- **Fail-closed / no-op guard:** if required capabilities are empty/`text` and no generators needed ⇒ return
  immediately (no writes, no overrides, no events). Plain-text runs byte-identical.
- **Opt-in application:** `PIPELINE_MODEL_STRATEGY` = `off|warn|apply` (default `warn` = artifact only, no
  overrides), matching the codebase's recommend-first posture; generators remain `PIPELINE_GENERATORS=0` default.
- **Auditable artifact:** `model-strategy.json` with `gate_a`/`gate_b`/`applied`, `item_id`, atomic write.

## Plan (branch `feature/bi-0192-model-strategy`)
1. `docs/MODEL-STRATEGY-DESIGN.md` (this file).
2. `core/model_strategy.py` — assess/decide/apply + gate_a/gate_b + persist.
3. Wire Gate A after the `0a` block, Gate B after the `2` block in `stage_runner._execute_stage_sequential`
   (guarded `_strategy_a_done`/`_strategy_b_done`).
4. `config/store-registry.json` — `model-strategy.json` (derived/project). `config/env-flags.json` —
   `PIPELINE_MODEL_STRATEGY`, `PIPELINE_MODEL_STRATEGY_GATE_B`.
5. CLI `pipeline.py strategy <project> [gate_a|gate_b]`.
6. Tests `test_model_strategy.py` — plain-text no-op (nothing written, no overrides); media idea ⇒
   `enabled_packs` includes media + a generator assignment; Gate A recomposition adds `4m`; Gate B refines;
   idempotent re-run. **e2e:** drive `gate_a`→`gate_b` on a scratch project and assert the artifact + applied
   overrides + DAG contains the injected stage.
7. Gates: compileall, wired_audit (0 unwired, stores registered), workflow_matrix, pipeline tests, precheck.
8. Merge; close `BI-0192` (and `BI-0210`) through the loop.

## Acceptance
- Media idea ⇒ strategy gate enables the media pack + selects modality-appropriate models **before** implementation; artifact persisted.
- Plain app idea ⇒ selection stays as today; **nothing written** (byte-identical).
- Gate A runs before Design; media pack + `4m` present in the DAG by stage 1; non-media idea enables nothing.
- Changing the idea re-runs the gate and updates `capabilities.json`/strategy idempotently.
- `precheck` PASS; no new tier/pack truth; single writer per store.

## Out of scope (tracked separately)
Packs themselves (`BI-0189`✅), media agents (`BI-0190`), real generator transport (`BI-0188` follow-up),
per-unit cost (`BI-0194`), model policy schema (`BI-PF-0278`).
