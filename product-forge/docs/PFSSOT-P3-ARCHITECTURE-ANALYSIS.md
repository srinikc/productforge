# PFSSOT-P3 — Deep Architecture Analysis (merged into grooming)

**Item:** BI-PF-0364 (epic BI-PF-0360) · extends `core/grooming.py` + `core/backlog.py`

**Decision (no second engine):** grooming and architecture analysis are **one pass at two depths**, per doc
§7 (*"Analysis belongs primarily to backlog grooming"*). P3 adds the **deep** depth to the existing groomer —
it does **not** add a separate `analyze()` engine or store.

## Depth

- **`depth="deep"` (default):** the deterministic groomer searches the **real codebase** for existing
  components (`core/*`), APIs (OpenAPI paths) and config/modules matching the item's keywords, then derives
  `architecture_fit` (REUSE/EXTEND/…), `implementation_strategy`, `duplication/dependency/conflict` findings,
  `drift`, rewrite/new-component, `evidence`, `confidence`.
- **`depth="standard"`:** backlog-signal analysis only (the former P2 behavior) — escape hatch for cheap/edge cases.
- **AI (default mode)** enriches the deep analysis via the existing agent runtime (same as P2); offline it
  falls back to the deterministic deep scan.

## Analysis at grooming time (default)

- **On entry:** `backlog.add_epic` runs `grooming.groom(..., depth=deep)` when `analyze_mode="on_entry"`
  (default), **after** the item is saved (best-effort; never blocks create). The item arrives
  **scheduler-ready** with its architecture/design plan in `analysis{}`.
- **`analyze_mode="defer"`:** skips; analysis runs before pickup.
- **Stale-triggered:** a requirement/architecture change marks the analysis `STALE` (P1) → re-groomed before assignment.
- **Cost model:** the deep analysis is paid **once, at entry** — **not** re-run at pickup (unless `STALE`).
  The **worker never** performs analysis (doc §7 Level 2 = scheduler light revalidation only).

## Config (`config/grooming-guidelines.json`)

`default_depth: "deep"` · `ai_on_entry: "all|high_value|deferred"` (default `all`).

## API

`POST /api/v1/backlog/items/{id}/groom` accepts `depth` (default `deep`) and `mode`/`ai`.
No `/analyze` endpoint (no second engine).

## 360° check

- One owner (`core/grooming.py`), one `analysis{}` block (P1), one API; **no new store/engine**.
- Reuses codebase-search heuristics; reuses the agent runtime for AI (no new LLM client).
- Deep-by-default cost is incurred early and once; pickup is execution.

## Verification

```
python scripts/dev/grooming_check.py            # OK (deep default + codebase-grounded on entry)
python -m pytest .../test_deep_analysis.py .../test_grooming.py   # 8 passed
python scripts/dev/precheck.py                  # PASS
```
