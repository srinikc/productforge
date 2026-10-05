# PFSSOT-P7 — Worker Adapter Interface (runtime-neutral)

**Item:** BI-PF-0368 (epic BI-PF-0360) · `core/worker_adapters.py` (no new store)

The scheduler assigns work through an **abstraction**, never OpenCode directly (doc §17/§18). OpenCode is
the **first adapter**, never a dependency.

## Contract (doc §18 verbs)

```
register · heartbeat · get_status · accept_assignment · start · pause · cancel · report_result · disconnect
```

## Adapters

| runtime | role |
|---|---|
| `opencode` | first adapter; wraps `core.worker:OpenCodeProvider`; degrades to BLOCKED if absent |
| `command` | local/test runtime; runs a command in the worktree (exercises the contract offline) |
| `native` | **declares** PF's own native path — **does NOT route agents through workers** (doc §43d) |

Adapters are **thin translators**: registration/liveness delegate to `core.worker_registry` (P6);
results persist via `core.worker` (single writer); claim/lease stays in `core.job_manager` (P5). No
orchestration logic, no new state.

## API

| Method | Path |
|---|---|
| GET | `/api/v1/engineering/adapters` |
| POST | `/api/v1/engineering/workers/{id}/assign` |
| POST | `/api/v1/engineering/workers/{id}/report` |

## 360° check

- Reuses providers (P0 `worker.py`), registry (P6), lease (P5); **no new engine/store**.
- Scheduler depends on the adapter abstraction, not OpenCode.
- PF agents stay native; the native adapter only declares that boundary.

## Verification

```
python scripts/dev/adapters_check.py     # OK (contract verbs, opencode-first, command cycle, native declared)
python -m pytest .../test_worker_adapters.py   # 4 passed
python scripts/dev/precheck.py           # PASS
```
