# PFSSOT-P6 — Minimal Worker Registry + Heartbeat + Lifecycle

**Item:** BI-PF-0367 (epic BI-PF-0360) · new owner `core/worker_registry.py` (+ registered store)

External **execution resources** (OpenCode session, CLI, remote runtime) register so the scheduler can
discover capacity. **Not** for PF agents — agents stay native (doc §2/§23).

## Model (doc §15/§16/§19/§20)

```
REGISTERING -> ONLINE -> { IDLE | BUSY | PAUSED | DRAINING | OFFLINE | STALE }
```

- **register** — minimal, runtime-neutral: `runtime`, `capabilities`, `role`, `endpoint`, `workspace` → `worker_id`.
- **heartbeat** — lightweight (`worker_id`, status, current_assignment_id); the **scheduler/control plane owns authoritative state**.
- **STALE** — derived from heartbeat age (`PF_WORKER_STALE_SECONDS`, default 90s); a worker never sets its own STALE.
- **unregister / revoke** — remove or `OFFLINE`+revoked.
- **available_slots()** — bridge to the **existing** scheduler slot shape (`scheduler.worker_slots`); registry workers merge with the static pool. OpenCode is one `runtime` value, never a dependency.

## Store

`engineering/worker-registry.json` (single writer `core/worker_registry.py`), scope `project|product_forge`,
registered in `config/store-registry.json`. One concern; no per-worker identity system.

## API

| Method | Path |
|---|---|
| POST | `/api/v1/engineering/workers/register` |
| POST | `/api/v1/engineering/workers/{id}/heartbeat` |
| GET | `/api/v1/engineering/workers` (+ `/{id}`) |
| POST | `/api/v1/engineering/workers/{id}/unregister` |

## 360° check

- New dynamic layer **feeding** the existing scheduler (not replacing the static pool); **reconciles** the three worker notions (P0 risk) rather than adding a fourth.
- Requires/writes nothing PF-agent-related. No large heartbeat payloads.
- **Does not** invoke work — adapters (P7) and dispatch retain that.

## Verification

```
python scripts/dev/worker_registry_check.py   # OK (register/heartbeat/lifecycle/stale/slots/revoke)
python -m pytest .../test_worker_registry.py  # 4 passed
python scripts/dev/precheck.py                 # PASS
```
