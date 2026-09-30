# Per-Unit Cost Model — Design (BI-0194)

## Goal
Cost today is per-token only (`budget_planner`: `input/1000*price_in + output/1000*price_out`). Media bills
**per image / second / char / track / mesh**. Add a **per-unit cost schema + projection** and stitch it into
the places decisions are made: project creation (provisional estimate), the strategy gate (per-stage/agent
projection incl. media), and the budget allocator — scalable, API-first, verified. Text projects unchanged.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Generator pricing | `config/generators.json` already has `billing_unit`+`unit_price` (image/second/char/track/mesh) | the SSOT for media unit price | reuse |
| Token pricing | `config/model-catalog.json` + `budget_planner` ($/1k in/out) | unchanged (text path) | reuse |
| Strategy gate | `model_strategy.assess` emits `assignments[]` with `billing_unit` (no cost) | add per-stage/agent **cost projection** | extend |
| Budget | `budget.py record_usage`, `budget_allocator.TokenBudgetAllocator` (tokens only) | accept media units + cost | extend |
| KPI | `cost_kpi.TaskCost` (tokens) | optional `billing_unit`/`units` | extend |
| Project create | provisional tier only | provisional **cost estimate** incl. media | extend |

**Blast radius:** new `core/cost_model.py` (the projection engine); wire into `model_strategy.assess`,
`budget_planner`, `budget_allocator`, API. One new derived artifact `artifacts/…/Cost-Projection.json`
(single writer = `cost_model.py`). No new store (price sources are existing configs).

## Design decisions (modular, 1 truth per concern)
- **New `core/cost_model.py`** — the single owner of per-unit costing:
  - `unit_price(model_or_generator_id) -> {billing_unit, unit_price}` from `generators.json` (media) or
    `model-catalog.json`/`budget_planner` (tokens).
  - `cost_of(unit, units) = unit_price x units` — the schema: **`billing_unit + unit_price x units`**.
  - `project(project_dir, quantities) -> {per_stage[], per_agent[], total, free_paid_mix}`:
    text = per-token (unchanged formula); media = per-unit (N images × $, M s × $, K chars, T tracks, meshes).
    Quantities come from the pipeline plan / capability packs (bounded defaults), overridable.
  - `write_projection(project_dir, ...)` -> `artifacts/…/Cost-Projection.json` (this module is the **only**
    writer; deterministic; auditable).
- **Reuse, never fork:** token math stays in `budget_planner`; `generators.json` stays the price SSOT;
  `cost_model` composes them. No second cost source.
- **Stitched where decisions happen:**
  - `model_strategy.assess` → each assignment gains `unit_price` + `projected_cost`; the report gains
    `cost_projection` (per stage/agent + total + free/paid mix) — the strategy gate now sees media cost.
  - `budget_allocator` → accepts `units`+`billing_unit` so media consumption is allocatable; `budget.py
    record_usage` can receive `units`.
  - **Project creation** → provisional tier + rough **estimate** via `cost_model.project` (empty ⇒ text-only,
    identical to today).
- **Text path is byte-identical:** with no media quantities, `project()` returns the current per-token
  number → no regression (asserted by test).
- **API-first:** `GET /api/v1/costs/schema` (unit schema), `GET /api/v1/costs/projection?project=` (read the
  projection), `POST /api/v1/costs/estimate` (ad-hoc per-unit estimate).
- **Scalable:** pure functions; per-unit multiplication; no network; projection cached as one artifact.

## Plan (branch `feature/bi-0194-per-unit-cost`)
1. `docs/PER-UNIT-COST-DESIGN.md` (this file).
2. `core/cost_model.py` — unit price lookup, `cost_of`, `project`, `estimate`, `write_projection`.
3. Wire: `model_strategy.assess` (+cost_projection), `budget_allocator` (+units), `budget.record_usage`
   (+units passthrough), optional `cost_kpi`.
4. `dashboard/api/app.py` — `/api/v1/costs/{schema,projection,estimate}`.
5. Tests `test_cost_model.py` — media projection reflects per-unit pricing; **text projection unchanged**;
   strategy report exposes cost per agent/stage; free/paid mix; schema endpoint.
6. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
7. Merge; close `BI-0194` through the loop.

## Acceptance
- A media project's projected cost reflects per-unit media pricing (image/second/char/track/mesh × price).
- A text project's projected cost is unchanged (per-token only).
- Strategy-gate output exposes cost per agent/stage + free/paid mix; API surfaces it.
- `precheck` PASS; single writer for the projection; no fork of token math.

## Out of scope (tracked separately)
Real provider invoices/live price sync (0206 model downloader/license; 0218 ops/evals), per-unit *billing*
reconciliation.
