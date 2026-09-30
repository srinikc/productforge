# Media Chunking + Asset-Ref Resolution — Design (BI-PF-0288)

## Goal
Extend the media context pipeline (BI-PF-0287) so that: (1) when selected media **exceeds the per-call
budget**, it is **map-reduced over the asset's children** (tiles/segments/frames) instead of dropping
parts; and (2) **markdown asset references** in upstream artifacts (`![..](assets/..)`, `AS-*`) are
resolved to real assets so a non-media agent that points at media actually receives it (summary/parts).

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Media parts | `asset_store.to_media` (children-first, ≤8 MB) | reuse; add a **bounded chunker** | `media_context` |
| Media selection | `media_context.for_agent` caps `MAX_PARTS=6` | keep; when over budget, **map-reduce children** | `media_context` |
| Asset refs | `_REF_RE` already matches `AS-…` in upstream text | resolve **markdown links** `![..](assets/..)` + `AS-*` | `media_context` |
| Token estimate | `estimate_tokens(parts)` | use it to decide chunking | `media_context` |
| LLM chunking | text map-reduce in `llm_client._call_llm_chunked` | media children reduce share the same *shape* (summaries), not text split | `media_context` |
| Store | none | none | — |

**Blast radius:** `media_context` only (+ tests). No new store; no engine change; text path untouched.

## Design decisions (modular)
- **New `chunk_media(project_dir, agent_id, model_name, media_budget_tokens) -> (parts, summary)`** in
  `core/media_context.py`: when `estimate_tokens(parts) > budget`, iterate an asset's **children**
  (tiles/segments/frames — the modality-native units from `asset_store._split`) and take the **first N
  that fit**; if still over, fall back to **summary-only** (fail-closed — never blow the window).
- **Asset-ref resolution** (extend `select_assets`/`_referenced_assets`): parse markdown image links
  `![alt](assets/<id>/…)` and inline `AS-<hash>-<n>` tokens; map to asset ids via `asset_store.get`.
  Non-media agents thus get media **only when referenced** (need-based, consistent with BI-PF-0287).
- **Budget source:** reuse the agent contract `max_input_tokens` × a media share (e.g. 25%) or the
  model's usable context; default conservative. `PIPELINE_MEDIA_BUDGET_TOKENS` overrides.
- **Reuse, never duplicate:** `asset_store` (children, to_media), `multimodal` (gating), existing token
  estimate. Media chunking is **selector-side** (which children to send), not a new LLM loop.
- **Fail-closed:** over-budget with no fitting children ⇒ summary only; unknown refs ignored.

## Plan (branch `feature/bi-pf-0288-media-chunking`)
1. `docs/MEDIA-CHUNKING-DESIGN.md` (this file).
2. `core/media_context.py` — `resolve_refs` (markdown + AS-*), `chunk_media`, wire into `for_agent`.
3. `config/env-flags.json` — `PIPELINE_MEDIA_BUDGET_TOKENS`.
4. Tests `test_media_chunking.py` — ref resolution (`![..](assets/AS-…)` → asset), over-budget ⇒ children
   subset (never > budget), no fitting children ⇒ summary only, plain text unaffected.
5. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
6. Merge; close `BI-PF-0288` through the loop.

## Acceptance
- An upstream artifact referencing `AS-*`/`![..](assets/..)` causes the referenced media to reach the
  agent (native if capable, else summary).
- Media parts never exceed the budget: over-budget ⇒ a child subset or summary, never an overflowing call.
- Text-only/no-asset runs unchanged; `precheck` PASS; no new store.

## Out of scope (tracked separately)
Media QA (`BI-0191`), learning pipeline (`BI-PF-0289+`), real generator transport.
