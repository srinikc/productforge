# PFSSOT-P4 — Scheduler Eligibility over the Canonical Backlog

**Item:** BI-PF-0365 (epic BI-PF-0360) · extends `core/scheduler.py` (read-only; no new engine/store)

The scheduler answers *"what can run now?"* from the **canonical backlog** (not just task contracts),
per doc §10–§13/§31–§33.

## Eligibility (pure, fail-closed)

`eligible(item, *, by_id, worker, active) -> {ok, reasons[]}` checks, in order:

1. **status** — terminal/blocked excluded
2. **analysis gate** — `analysis.status == COMPLETE` (READY); `NOT_ANALYZED`/`IN_PROGRESS`/`STALE` → blocked (needs grooming)
3. **dependencies** — structured `dependencies`/`deps`/`blocked_by` all terminal (unknown refs block, fail-closed)
4. **readiness** — `readiness.ready`
5. **already assigned** — an open `execution.worker_id` blocks
6. **contention** — path overlap with other active items (reuses `path_overlap`)
7. **capability** — worker match when a slot is supplied (reuses `capability_match`)

Staleness is authoritative via `analysis.status` (P1 marks COMPLETE→STALE on requirement/architecture change);
eligibility does **not** re-derive it from revision numbers (priority/dep edits bump revision without invalidating).

## Selection (read-only)

- `eligible_backlog(scope, project)` — every open item with `{ok, reasons}` + counts.
- `next_eligible(scope, project)` — highest-priority eligible item via `backlog.order_by_priority` (deterministic).

**No claim/lease here** — that is P5. Eligibility writes nothing.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/engineering/schedule/eligible` | per-item eligibility + reasons |
| GET | `/api/v1/engineering/schedule/next` | highest eligible (read-only) |

## 360° check

- Extends `core/scheduler.py`; reuses `path_overlap`/`capability_match`/`dependency` logic + `backlog.order_by_priority`/`dependencies`/`readiness`/`analysis`/`execution`; **no new engine/store**.
- Fail-closed: missing analysis/deps/unknown refs block.
- Read-only: P5 adds the atomic claim/lease.

## Verification

```
python scripts/dev/scheduler_check.py     # OK (... + backlog eligibility)
python -m pytest .../test_scheduler_eligibility.py   # 4 passed
python scripts/dev/precheck.py            # PASS
```
