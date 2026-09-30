# Capability-Pack Registry + Discovery→Enablement — Design (BI-0189)

## Goal
The pluggable-core foundation for multimodal/media: a **capability-pack registry** (catalog of packs
keyed by modality) + a per-project **capability profile** derived from discovery, wired through the
**existing** discovery→recommend→enable path (no 4th enable mechanism).

## 360° — what exists (verified)
`capability` is overloaded across 5 orthogonal concerns; `BI-0189` must not duplicate any of them:
| Existing | Owner | Role | BI-0189 stance |
|---|---|---|---|
| `capability_bridge` (stage hooks, `capabilities-*.json`) | `core/capability_bridge.py` | runtime orphan adapters | reuse; **avoid name collision** |
| `pipeline_capabilities` (`extended-capabilities.json`) | `core/pipeline_capabilities.py` | liveness probe | reuse |
| `agent_capabilities` (LLM request vector) + `agent-capability-vector.json` | `core/agent_capabilities.py` | per-agent LLM features | reuse |
| `agent-capabilities.json` (agent→knowledge/skills/MCP bindings) | `core/skills_registry.py` | agent binding SSOT | reference agents by id; never re-declare |
| `integration_advisor` (`recommendations.json`/`integration_choices.json`) + `feature_flags` | `core/integration_advisor.py` | the existing discover→recommend→HIL→enable path | **feed pack enablement through here** |
| `plan_evaluator`/`run_plan` (`plan-groups.json`/`run-plan.json`) + `pipeline_tailoring` | — | 3 overlapping optional-stage enable paths | do **not** add a 4th |
| `modality.py` (`MODALITIES`, `detect`, `capabilities_for_project`) | `core/modality.py` | detects modalities, read-only, persists nothing | build on it; persist instead of re-detect |
| `knowledge_registry.py` | `core/knowledge_registry.py` | the registry pattern to mirror | mirror the API shape |

No `capability-packs.json` / `capabilities.json` / `core/capability_packs.py` exist (BI-0189 not built).

## Design decisions
- **New module `core/capability_packs.py`** — single writer of the two new stores, API mirroring
  `knowledge_registry` (`list_packs/view/get/add/modify/remove` + `resolve(required)`). No runtime
  behaviour of its own beyond resolving a profile → active packs.
- **New `config/capability-packs.json`** (global catalog): `pack_key → {title, modality, tools[],
  generator_providers[], agents[], validators[], models[], requires[], providers_kind[]}` + defaults
  `none|image|video|audio|3d`. Packs **reference** existing agents/tools/models by id — never restate
  bindings or model caps.
- **New `products/<project>/capabilities.json`** (project profile): `{required_capabilities:[...],
  enabled_packs:[...], source, at}`. `required_capabilities` is produced by **extending `modality.py`**
  to persist (today it only logs). Distinct name from the existing `capabilities-*.json` wildcard.
- **Enablement reuses the existing path:** pack selection is surfaced as recommendations via
  `integration_advisor`/`feature_flags` (or `plan_evaluator` groups) — the pack registry only declares
  the catalog + resolves a profile. No new HIL/enable mechanism.
- **Fail-closed:** unknown pack in `enabled_packs`, or a required capability with no pack, is reported
  as a warning (advisory) and never silently enabled; `resolve()` never invents a pack.
- **Register both stores** in `config/store-registry.json` (config/global + config/project). New module
  must be on the runtime path (imported by a caller) or `wired_audit` flags it UNWIRED.

## Plan (branch `feature/bi-0189-capability-packs`)
1. `docs/CAPABILITY-PACKS-DESIGN.md` (this file).
2. `config/capability-packs.json` — catalog (image/video/audio/3d/none) referencing existing ids.
3. `core/capability_packs.py` — registry + `resolve(required)` + `profile(project_dir)` (read/persist
   `capabilities.json`); single writer.
4. `core/modality.py` — add `persist_required(project_dir, idea)` (write `required_capabilities`).
5. Wire: call `persist_required` at the existing modality site (`pipeline_executor` preflight) and
   surface pack recommendations via `integration_advisor` (additive, guarded).
6. `config/store-registry.json` — register `capability-packs.json` + `capabilities.json`.
7. Tests `test_capability_packs.py` — catalog loads; `resolve()` maps required→packs; unknown
   capability/pack fail-closed (warning, no enable); persistence round-trips; no collision with
   `capabilities-*.json`.
8. Gates: compileall, wired_audit (0 unwired, store registered), workflow_matrix, pipeline tests, precheck.
9. Merge; close `BI-0189` through the loop.

## Acceptance
- `capability_packs.list_packs()` returns the catalog; `resolve(["image"])` → image pack; unknown ⇒
  warning, empty enable (fail-closed).
- A project profile round-trips through `products/<p>/capabilities.json`; `required_capabilities`
  derived from `modality.detect` and persisted.
- Pack enablement rides the existing recommendation/HIL path (no new mechanism); agent bindings remain
  owned by `agent-capabilities.json`.
- `wired_audit` 0; stores registered; no name collision; `precheck` PASS.

## Out of scope (tracked separately)
Media agents (`BI-0190`), generator adapters (`BI-0188`), media ingest (`BI-0187`), multimodal LLM
plumbing (`BI-0186`), stage injection (`BI-0213`), E2E (`BI-0212`).
