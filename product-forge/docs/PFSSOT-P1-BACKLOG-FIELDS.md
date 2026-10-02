# PFSSOT-P1 — Backlog First-Class Execution Fields

**Item:** BI-PF-0362 (epic BI-PF-0360) · extends `core/backlog.py` (no new store)

The canonical backlog item now carries the execution-SSOT fields so the scheduler/worker can pick up work
with full context (analysis/design/strategy already done) rather than re-deriving it at pickup.

## Added fields (all additive; legacy items unaffected)

| field | meaning | doc |
|---|---|---|
| `revision` | monotonic version; bumps on material change | §38 |
| `priority_rank` / `priority_class` | deterministic ordering | §6.3 |
| `analyze_mode` | `on_entry` (default) \| `defer` | §7 |
| `analysis{}` | versioned, stale-aware architecture analysis (status/architecture_fit/strategy/drift/evidence/confidence…) | §6.5/§8 |
| `dependencies[]` | structured `{task_id, type: BLOCKS\|REQUIRES\|RELATED, required_state}` (+ flat `deps` kept in sync) | §6.4 |
| `blocked_by[]` / `unlocks[]` | dependency graph edges | §6.4 |
| `readiness{ready,reasons,computed_at}` | computed eligibility | §6.1 |
| `execution{worker_id,assignment_id,lease_id,…}` | assignment/lease state | §13 |

`analysis.status` ∈ `NOT_ANALYZED|IN_PROGRESS|COMPLETE|STALE` — never a boolean.

## Rules (enforced in `update()`)

- **revision** bumps only when a schedule/definition field changes (`title/body/deps/dependencies/priority/priority_rank/moscow/value/effort/risk/links`).
- a **COMPLETE** analysis becomes **STALE** only when a **requirement/architecture** field changes (`title/body/dependencies/links`) — **priority/dep bookkeeping does not stale it**.
- structured `dependencies` keeps the legacy flat `deps` in sync so `core.scheduler` keeps working.

## Helpers / API

`set_analysis` · `set_priority` · `set_dependencies` · `set_execution` · `set_readiness` · `mark_stale` · `order_by_priority`

- `POST /api/v1/backlog/items/{id}/analysis`
- `POST /api/v1/backlog/items/{id}/priority`
- `POST /api/v1/backlog/items/{id}/dependencies`

Index (`open.json`/`closed.json`) exposes `priority_rank`, `revision`, `analysis_status`, `ready`, `worker_id`
so the scheduler can query without loading full items.

## 360° check

- Extends the single owner (`core/backlog.py`); **no new store**. Old items read with defaults.
- Status vocabulary **unchanged** (analysis/execution are sub-states, per doc §6.2 "don't duplicate states").
- `order_by_priority` is opt-in; existing `list_open` behavior preserved.

## Verification

```
python -m compileall -q core api            # 0
python -m pytest .../test_backlog_pfssot_fields.py   # 6 passed
python scripts/dev/precheck.py              # PASS
```
