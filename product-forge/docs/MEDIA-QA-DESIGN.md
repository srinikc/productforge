# Media QA Validators — Design (BI-0191)

## Goal
Give media outputs a **quality gate**: validate generated/edited media assets (probe/codec/res/fps/duration,
loudness (EBU R128), perceptual-hash continuity, A/V sync, format/size limits) and surface failures as
**compliance findings** — feeding the same evidence stream the learning layer will consume.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Media metadata probe | `asset_store._probe`/`_ffprobe` (dimensions/duration/fps/sample_rate/codec) | reuse as the probe basis | `asset_store` |
| Media validators | **none** (asset_store doc:180 "QA is BI-0191") | new validators | new `core/media_qa.py` |
| Compliance surface | `ComplianceChecker.check_agent` + `AGENT_CHECKLISTS` + `derived_checklist` | add a media-QA check path | `compliance_check` (reuse) |
| Validate stage | `validate` agent at 11/12; `visual_qa` for UI | media validators run at validate when media exists | `stage_runner`/validate |
| Findings/evidence | defects (`defect_loop`), issues (`issues`), compliance | media-QA findings route to the same streams | reuse |
| Store | none needed | compute + report; findings via existing streams | — |

**Blast radius:** new `core/media_qa.py`; a compliance hook; tests. No new store (findings go to existing
defects/issues/compliance). Libs guarded (ffprobe optional).

## Design decisions (modular)
- **New `core/media_qa.py`** — pure validators over the asset store (no store of its own):
  - `probe(asset) -> checks[]`: codec/res/fps/duration/format/size present + sane (reuse `_ffprobe`).
  - `loudness(path) -> checks[]`: EBU R128 via `ffmpeg -af ebur128` when available, else degrade.
  - `perceptual_continuity(asset) -> checks[]`: phash/mean-hash across children (frames) via PIL/numpy
    when available; flag duplicate/blank frames; else degrade.
  - `av_sync(asset) -> checks[]`: audio vs video duration skew within tolerance (guard).
  - `validate_project(project_dir) -> Dict`: run all; return `{ok, checks[], findings[], degraded}`.
  - Every check is **lib-guarded** and **fail-closed**: missing tool ⇒ `degraded` (never a false PASS,
    never raise). Follows `asset_store._probe` and `multimodal` idioms.
- **Compliance hook (reuse, don't fork):** media-QA results surface through `ComplianceChecker` as a
  **check family** for media agents (or a top-level media section), so a failing/gated media artifact is
  visible like any other compliance finding. Findings also route to `defect_loop`/`issues` (evidence).
- **Wiring:** at the **validate** stage (11/12) when the project has media assets (or the media pack is
  enabled), run `media_qa.validate_project` and record results (compliance + findings). No-op when no media.
- **Opt-in & bounded:** `PIPELINE_MEDIA_QA` = `off|warn|block` (default `warn` — surfaces findings without
  blocking); `PIPELINE_MEDIA_QA_TOLERANCE` for sync/loudness thresholds.
- **Reuse, never duplicate:** `asset_store` (assets/children/probe), `compliance_check`, `defect_loop`,
  `issues`. No new store; one writer per concern.

## Plan (branch `feature/bi-0191-media-qa`)
1. `docs/MEDIA-QA-DESIGN.md` (this file).
2. `core/media_qa.py` — validators + `validate_project` (lib-guarded, fail-closed).
3. Wire at validate (guarded, no-op without media); surface via `compliance_check`.
4. `config/env-flags.json` — `PIPELINE_MEDIA_QA`, `PIPELINE_MEDIA_QA_TOLERANCE`.
5. Tests `test_media_qa.py` — corrupt vs good media file; missing ffmpeg ⇒ degraded (not PASS/raise);
   no-media ⇒ no-op; findings shape.
6. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
7. Merge; close `BI-0191` through the loop.

## Acceptance
- A corrupt/bad media asset ⇒ validator flags a finding; a good one passes; missing tooling ⇒ degraded.
- Findings surface as compliance findings and enter the evidence stream (defects/issues).
- No media ⇒ no-op; `precheck` PASS; no new store.

## Out of scope (tracked separately)
Learning pipeline (`BI-PF-0289+`), real generator transport, perceptual-hash dedupe in the store.
