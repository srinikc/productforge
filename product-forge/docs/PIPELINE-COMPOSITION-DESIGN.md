# Capability-Gated Pipeline Composition — Design (BI-0213)

## Goal
Given the **enabled capability packs**, produce the run's **effective** stage order + agent roster by
**inserting optional stages** (`0f` capability-strategy after `0a`; `4m` media-production after `4-0`) and
appending pack **agents/validators** to existing stages (media-QA into `5`/`6`) — leaving a non-pack run
**byte-identical** to today.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Effective stage order | fixed `pipeline-definition.json`; only **skip** exists (`run_plan.apply_to_dag`, `plan_evaluator.apply_to_dag`, `pipeline_tailoring.apply_plan` drop-at-load) | **insert** optional stages by anchor | new `core/pipeline_composition.py` |
| Pack → stages/agents | `config/capability-packs.json` has `agents:[]`, `validators:[]`, no `stages` | packs declare `stages[{id,after,depends_on,ideal_flow,...}]` + populate agents/validators | `capability_packs` (extend catalog) |
| DAG | `DAGExecutor(pipeline_def)` at `load_pipeline:1360`; `mark_skipped` (`dag_executor.py:205`), `get_ready_stages` treats SKIPPED satisfied (`:103-106`) | consume composed def, unchanged | reuse |
| Roster | `stage_runner.py:205` reads `stage.ideal_flow` | composed `ideal_flow` | reuse |
| Load site | `pipeline_executor.load_pipeline` raw read `:1330`, tailoring `:1336`, template `:1343`, `DAGExecutor` `:1360`; also `load_pipeline_from_dict:1384` | compose **between** tailoring/template and `DAGExecutor` | wire |
| Consumption | `self.pipeline_def` in-memory, no cache | same | — |
| Store | none needed | compute **in-memory** (pure fn of base + enabled packs) | — |

**Blast radius:** `pipeline_executor` load (2 paths), `capability_packs` catalog, store-registry (catalog only,
already registered), tests. Non-pack path must be a pure identity.

## Design decisions (modular)
- **New `core/pipeline_composition.py`** — pure, side-effect-free composition (no store, no I/O): 
  `effective_definition(base_def, project_dir=None, packs=None)`, `effective_stages(base_def, packs)`,
  `effective_agents(base_roster, packs)`, `enabled_tools/packs`. Reads enabled packs via
  `capability_packs.active_packs(project_dir)` — **never** a 4th enable path (reuses run_plan/tailoring for skips).
- **Anchor insertion (pure pre-DAG transform):** for each enabled pack's `stages[i]` `{id, after, ...}`:
  deep-copy base stages; insert the stage after its anchor preserving order; rewire dependents
  (any stage that `depends_on` the anchor now also depends on the inserted id); inserted stage
  `depends_on` the anchor. **Fail-closed:** unknown id/anchor or an attempt to remove a required stage ⇒
  raise-free -> return base unchanged + warning (mirrors the PF-065 lesson).
- **Media-QA as roster append, not a new stage:** pack `validators` are appended to stages `5`/`6`
  `ideal_flow`; pack `agents` appended to their target stage's `ideal_flow` (+ `agent_dependencies`).
- **Non-pack = byte-identical:** if enabled packs is empty or only `none`/text, return the **same base object**
  (no deep-copy reorder, no marker key). Composition is only invoked when a real pack is enabled.
- **Catalog extension (additive, empty-by-default):** add `stages:[]` to every pack; populate `agents`/
  `validators` for media packs. `none` pack stays a no-op. Packs still **reference** agent/tool/model ids.
- **Consumed in `pipeline_executor.load_pipeline` and `load_pipeline_from_dict`**, immediately before
  `DAGExecutor(...)`, so `DAGExecutor` + `stage_runner` need **no change**.

## Plan (branch `feature/bi-0213-capability-composition`)
1. `docs/PIPELINE-COMPOSITION-DESIGN.md` (this file).
2. `config/capability-packs.json` — add `stages` (0f after 0a; 4m after 4-0) + media `agents`/`validators`.
3. `core/pipeline_composition.py` — pure compose (anchor insert + roster append + identity guard).
4. Wire into `pipeline_executor.load_pipeline` / `load_pipeline_from_dict` (guarded, pre-`DAGExecutor`).
5. Tests `test_pipeline_composition.py` — (a) no-pack ⇒ `effective_definition(base) == base` (structural
   + order equality); (b) image/video pack ⇒ `0f` after `0a`, `4m` after `4-0`, dependents rewired, media
   agents on right stages; (c) disabling a pack ⇒ no residue; (d) unknown anchor ⇒ base unchanged + warning;
   (e) DAG `get_ready_stages` order correct with inserted stages.
6. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
7. Merge; close `BI-0213` through the loop.

## Acceptance
- No pack ⇒ effective stage order + roster identical to `pipeline-definition.json` (regression guard).
- Image/video pack ⇒ `0f`+`4m` present in order, media agents/validators on the right stages, existing stages intact.
- Disabling a pack removes its stages/agents with no residue.
- Unknown anchor/id ⇒ fail-closed (base unchanged, warning); never removes a required stage.
- `precheck` PASS; no new store; composition is in-memory.

## Out of scope (tracked separately)
Media agents themselves (`BI-0190`), media QA impl (`BI-0191`), model-strategy gate (`BI-0192`/`BI-0210`), packs
definitions beyond stage/agent anchors (`BI-0208`/`BI-0209`).
