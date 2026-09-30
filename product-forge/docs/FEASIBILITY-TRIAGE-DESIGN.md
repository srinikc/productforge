# Two-Phase Feasibility & Capability Triage — Design (BI-0214)

## Goal
Know early whether a product idea is buildable — and how it ships — before design/architecture commit to
it. **Phase 1 (BUILD-HOST, mandatory at ideation):** probe the machine building the product; per modality
decide `local | api | aggregator`; verdict `go | conditional | no-go`. **Phase 2 (DESTINATION, deferred at
packaging):** profile where the product runs; decide shipping `bundle | api | hosted | hybrid` + SKU.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Host/GPU/VRAM probe | **none** | `probe_host()` (nvidia-smi/lib-guarded, degrade) | new `core/feasibility.py` |
| Capability need | `modality.generators_needed`, `capabilities_for_project` | reuse | `modality` |
| Generator license/free/key/cost | `generator_adapters.catalog/eligible/select/cost` + `config/generators.json` | reuse; derive `bundle_allowed` | `generator_adapters` |
| Packs/profile | `capability_packs.resolve/load_profile/active_packs` | reuse | `capability_packs` |
| Keys/budget | `credentials.has/check_budget` | reuse | `credentials` |
| Product footprint | `sizing.py`, `bom.py` | reference (don't recompute) | reuse |
| Destination target | `target_advisor`, `target_selector` (`docs/targets.json`) | reuse for Phase 2 | reuse |
| Shipping-mode truth | **prose only** (docs) | machine-readable in `feasibility.json` | new |
| Verdict pattern | `qa_report.go_no_go` (GO/GO-WITH-RISK/NO-GO) | mirror `{verdict,reasons,risks}` | mirror |
| Hardware tiers | docs §18/§19 (image 6–16 GB, video 8–24 GB+, audio CPU–4, 3D 6–16, VLM 4–16) | encode once | new `config/hardware-tiers.json` |
| Hook (Phase 1) | preflight `pipeline_executor.py:2778-2796` (after BI-0189/0187) | call `evaluate(phase="build")` | wire |
| Hook (Phase 2) | stage 9 BOM `stage_runner.py:729-737` | call `evaluate(phase="destination")` | wire |

**Blast radius:** preflight, stage-9 hook, store-registry, env-flags, CLI. No new top-level dirs; single writer.

## Design decisions (modular)
- **New `core/feasibility.py`** — pure assessment + persistence; **single writer** of
  `products/<p>/feasibility.json`. Public API: `probe_host()`, `assess_build(project_dir, host=None)`,
  `assess_destination(project_dir, target="", shipping="")`, `evaluate(project_dir, phase=...)`,
  `save_report/load_report/verdict`.
- **Two independent phases** (`phase1_build_host`, `phase2_destination`) so a later Phase-2 run rewrites
  only its key — **idempotent**, phase 1 never redone.
- **One shared `assess()`** against shared dimensions — capability (modality), license/free/key
  (generators), packs, cost — so the two phases never diverge in logic (modular, DRY).
- **Reuse, never duplicate truth:** generator/license/pack/key/cost from their owners; target from
  `target_advisor`; footprint referenced from `bom`/`sizing`. `feasibility.json` stores **verdicts +
  the host/target snapshot only**.
- **`bundle_allowed` derived** locally (`open_weights && license in permissive class`) until `BI-0211`'s
  tool catalog lands; read through `generator_adapters`, not hardcoded.
- **Hardware tiers in `config/hardware-tiers.json`** (global) — the per-modality VRAM/RAM/disk thresholds,
  single source, not prose.
- **Fail-closed & degrade:** any probe failure ⇒ explicit `"unknown"` + `degraded=true`; unknown host
  ⇒ verdict **`conditional`** (API fallback), never silent `go`. Never raises.
- **Verdict shape** mirrors `qa_report`: `{verdict: go|conditional|no-go, reasons[], risks[]}`.

## Plan (branch `feature/bi-0214-feasibility-triage`)
1. `docs/FEASIBILITY-TRIAGE-DESIGN.md` (this file).
2. `config/hardware-tiers.json` — per-modality VRAM/RAM/disk tiers (global).
3. `core/feasibility.py` — probe + assess_build + assess_destination + evaluate + persist.
4. Wire Phase 1 at preflight (unconditional) + Phase 2 at stage 9 (`stage_runner.py:729-737`).
5. `config/store-registry.json` — register `feasibility.json` (derived/project) + `hardware-tiers.json`
   (config/global). `config/env-flags.json` — `PIPELINE_FEASIBILITY_STRICT`, `PIPELINE_FEASIBILITY_GPU_OVERRIDE`.
6. CLI `pipeline.py feasibility <project> [--phase build|destination]`.
7. Tests `test_feasibility.py` — build matrix (idea×host): video-on-CPU ⇒ `conditional` (api); restricted
   weight ⇒ API-only; audio small ⇒ `go`; destination pass sets shipping mode; host probe degrades
   gracefully (no GPU) without raising; phase independence (phase 2 doesn't rewrite phase 1).
8. Gates: compileall, wired_audit (0 unwired, stores registered), workflow_matrix, pipeline tests, precheck.
9. Merge; close `BI-0214` through the loop.

## Acceptance
- At ideation the gate reports per-modality build feasibility **before design**; a video-on-CPU host is
  `conditional: API required`; a restricted weight is `API-only / not shippable`.
- Phase 2 later profiles the destination and sets shipping mode without redoing Phase 1 (idempotent).
- `feasibility.json` registered; `wired_audit` 0; `precheck` PASS; no duplication of generator/pack/cost truth.

## Out of scope (tracked separately)
Model downloader (`BI-0206`), tool/vendor license catalog `bundle_allowed` (`BI-0211`), per-unit cost
(`BI-0194`), strategy gate (`BI-0192`/`BI-0210`), stage injection (`BI-0213`).
