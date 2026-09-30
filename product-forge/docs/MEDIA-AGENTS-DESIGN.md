# Media Agents — Design (BI-0190)

## Goal
Add pluggable **media agents** — `media-analyst` (VLM understanding), `media-generator` (drive generator
models), `media-editor` (cut/merge/render), `asset-librarian` (index/manage the asset store) — enabled
**only when the media capability pack is active**, wired into the pack stages so they appear in the
effective roster and run in the media stage (`4m`), and pass every existing agent audit.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Media agents | **none** (4 not in cards/specs) | 4 new agents | `.opencode/agent/*.md` + `agents/*.agent.json` |
| Pack → agents | `config/capability-packs.json` `agents:[]`; video `stages[0].ideal_flow` already names `media-generator`,`media-editor` | populate pack `agents` + placement | `capability_packs` (data) |
| Composition | `pipeline_composition.effective_agents` appends pack agents to target stages | reuse (already supports) | reuse |
| Agent card format | `## 0..8` sections; frontmatter `description/mode/model/agent_id/version/spec_version/permission`; model unquoted | same | new cards |
| Agent spec | `agents/<id>.agent.json` (`core.agent_spec.load_specs`) | same | new specs |
| Knowledge audit | `agent_knowledge_audit` needs a live `docs/guidelines/<layer>/*.md` | declare `knowledge` bindings | `config/agent-capabilities.json` |
| Tier drift | `check_tier_models` flags a `model-tier.json` agent key with no spec | only add tier keys we also spec | avoid/Optional |
| Audits | `role_prompt_audit`, `agent_card_audit` (advisory); `wired_audit` fatal for store/naming | keep all clean | — |

**Blast radius:** 8 new files + `config/agent-capabilities.json` + `config/capability-packs.json`; no store-registry change; no test count assertions break.

## Design decisions (modular)
- **Four new agents**, each a `.opencode/agent/<id>.md` (sections 0–8, unquoted `model`) + `agents/<id>.agent.json`,
  following the exact sibling conventions (from the 360° checklist).
  - `media-analyst` — VLM/ASR: understands ingested media (ingest from BI-0187); text-out model.
  - `media-generator` — drives `generator_adapters` for the pack's modality kinds.
  - `media-editor` — cut/merge/render (ffmpeg/ToolSpec-guarded; degrade if absent).
  - `asset-librarian` — index/manage the asset store (BI-0187); phash/provenance/license.
- **Pack-driven enablement (no forking):** populate `config/capability-packs.json` pack `agents` +
  `agent_stages`/`validator_stages`; `pipeline_composition.effective_agents` appends them to the media
  stage only when the pack is enabled. Non-media runs unchanged (identity guard already proven).
- **Delegations (guarded, no new writer):** `media-generator` calls `generator_adapters.generate`;
  `media-editor`/`asset-librarian` use `asset_store` (`add/to_media/modalities`). Agents are **prompts +
  specs**, not new stores — actual execution stays in the existing modules (single writer preserved).
- **Audit compliance:** `config/agent-capabilities.json` entries with **live** knowledge layers
  (ui-ux, rendering, operations, testing, domain, architecture); `## 0. METADATA` `Tools` line lists no
  write tool when `edit: deny`.
- **Placement:** media agents on the media stage (`4m`, per pack) + analyst on `0a`/`1d`; validators
  (`media-qa` is BI-0191 — not created here). We add only the four in-scope agents; `capability-strategist`
  etc. are other items.

## Plan (branch `feature/bi-0190-media-agents`)
1. `docs/MEDIA-AGENTS-DESIGN.md` (this file).
2. 4 × `.opencode/agent/<id>.md` + 4 × `agents/<id>.agent.json` (compliance format).
3. `config/agent-capabilities.json` — bindings for the 4 (live knowledge layers).
4. `config/capability-packs.json` — pack `agents` + placements (image/video/audio/3d).
5. Tests `test_media_agents.py` — specs load; knowledge bindings resolve to live guideline dirs; pack
   composition appends only-on-enabled; non-media unchanged. Run `role_prompt_audit`/`agent_card_audit`/
   `wired_audit` clean.
6. Gates: compileall, wired_audit (0), workflow_matrix, pipeline tests, precheck.
7. Merge; close `BI-0190` through the loop.

## Acceptance
- Agents added to roster + stages, gated by the capability pack; a disabled pack adds none.
- Each agent declares knowledge/skills (agent-knowledge audit green); all card audits clean.
- `precheck` PASS; no new store; single-writer preserved.

## Out of scope (tracked separately)
Media QA validators (`BI-0191`), OCR/sensor agents (`BI-0209`/`BI-0208`), real generator transport
(`BI-0188` follow-up), media-agent prompt content depth (iterative).
