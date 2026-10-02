# Worker Timing, Human-Wait & Token/Cost Accounting

**Concern:** observe how long each worker takes, how much of that is **human wait**, and the
**tokens (in/out) + cost** each worker consumes — reused across existing owners, no new store.

## Model (existing owners extended)

| field | owner | meaning |
|---|---|---|
| `timing.started_at` / `ended_at` | `core/worker.py` (`WorkerResult`) | active work window (ISO timestamps) |
| `timing.duration_ms` | `core/worker.py` | active work time |
| `timing.wait_ms` | `core/worker.py` | time blocked on a human (approval / response / input) — **separate** |
| `usage.input_tokens` / `output_tokens` | `core/worker.py` | tokens consumed |
| `usage.cost` | `core/worker.py` via `core.cost_model.token_cost` | compute cost (no duplicate cost logic) |
| `metrics` block on the task | `core/task_contract.py` (`set_metrics`) | persisted per task (single writer) |
| worker result rows | `core/worker.py` (`worker-results.json`) | append + carry timing/usage |
| run totals | `core/worker.py` (`run_totals`) | aggregate duration/wait/tokens/cost + per-worker breakdown |

`WorkerResult.metrics()` returns `{duration_ms, wait_ms, total_ms, input_tokens, output_tokens, cost}`.

## Where it is recorded

- `worker.run_task(...)`: stamps `started_at`, times the provider run → `duration_ms`; reads
  `wait_ms` from provider output (human escalation); extracts `usage` (tokens + model) and computes
  `cost` via `core.cost_model`.
- `worker.record_result(...)`: also writes `timing`/`usage` onto the task's `metrics` block via
  `task_contract.set_metrics` (single writer).
- `worker.run_totals(scope, project, run_id)`: sums across results; active time and human-wait stay
  **separate**; includes a `by_worker` breakdown.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/workers/metrics?scope=&project=&run_id=` | per-worker + totals (time/wait/tokens/cost) |
| GET | `/api/v1/workers/results?scope=&project=&task_id=` | raw timing/usage per result |
| GET | `/api/v1/runs/time-cost?project=&run_id=` | run-scoped totals |

## 360° dependency check

- Reuses `worker-results.json` (owner `core/worker.py`) and the task store (`core/task_contract.py`);
  **no new store** registered — the task `metrics` block is a field, not a store.
- Cost is **not** recomputed in a second place: delegated to `core.cost_model.token_cost`.
- Human wait is tracked distinctly from active duration (matches `stop_conditions` escalation semantics).

## Verification

```
python scripts/dev/worker_check.py     # OK (timing window, wait_ms, metrics, usage, run totals)
python scripts/dev/task_contract_check.py
python scripts/dev/precheck.py         # PASS
```
