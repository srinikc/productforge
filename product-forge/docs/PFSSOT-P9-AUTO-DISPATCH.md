# PFSSOT-P9 — Automatic Dispatch

**Item:** BI-PF-0371 (epic BI-PF-0360) · `core/dispatcher.py` (no new store)

The scheduler assigns work **automatically** — not just on manual pull — when enabled. It matches available
workers (P6) to eligible items (P4) and claims them (P5), then hands each assignment to the worker's adapter
(P7). It does **not** execute work (adapter `start` stays explicit).

```
tick (off by default):
  available workers (P6: ONLINE/IDLE, not revoked)
    -> work_pull.pull(worker)  = next_eligible (P4) + claim_next (P5) + accept_assignment (P7)
```

## Config (central flag registry)

| flag | default | meaning |
|---|---|---|
| `WORKER_AUTO_DISPATCH` | `0` | auto dispatch on/off (manual pull only when off) |
| `WORKER_DISPATCH_POLL_SECONDS` | `5` | poll interval for an optional loop |

Gated by `WORKER_INTEGRATION_ENABLED` (P8A): if the worker layer is off, dispatch is a no-op.

## Safety

- **Idempotent:** relies on P4 eligibility + P5 atomic claim → never double-assigns.
- **Default off:** PF behaves exactly as before unless explicitly enabled.
- **No daemon required:** `tick()` is the unit; a supervisor/loop may call it.

## API

| Method | Path |
|---|---|
| GET | `/api/v1/engineering/dispatch/status` |
| POST | `/api/v1/engineering/dispatch/tick` (`force`, `max_assign`) |

## 360° check

- Composes P4/P5/P6/P7 + `work_pull`; **no new engine/store**; `dispatcher.py` is part of the optional
  worker layer (exempted in the single-path guard).
- Real timing/threads are out of scope (P12); UI is P10; extra adapters are P11.

## Verification

```
python scripts/dev/dispatcher_check.py     # OK (configurable, default-off, composes the stack)
python -m pytest .../test_dispatcher.py    # 4 passed
python scripts/dev/precheck.py             # PASS
```
