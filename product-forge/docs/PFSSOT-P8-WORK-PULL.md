# PFSSOT-P8 — Manual Work Pull (`/pf work`)

**Item:** BI-PF-0369 (epic BI-PF-0360) · `core/work_pull.py` (no new store) · first end-to-end milestone

A worker asks for work; the scheduler picks the highest eligible item, claims it with a lease, and returns a
canonical **assignment package**. Composes the built owners — no new engine/store:

```
worker_registry (P6) -> scheduler.next_eligible (P4) -> job_manager.claim_next (P5)
  -> worker_adapters.accept_assignment (P7) -> assignment package (+ execution_contract)
```

## Assignment package (doc §34)

Minimal and canonical: `item_id`/`revision`, requirement, priority/`priority_rank`, structured deps, the
**stored analysis/design** (P1/P3 — pickup is execution, not re-architecture), relevant
components/APIs, constraints, acceptance/test requirements, plus an `execution_contract` envelope
(permissions/limits/verification/recovery), `assignment_id`, `lease_id`, `lease_expires_at`, `attempt`.

## Flow

```
/pf work (worker or operator)
  -> if unregistered, auto-register by runtime (P6)
  -> claim next eligible (P4+P5, atomic, no double-claim)
  -> adapter.accept_assignment (P7)
  -> return {assigned, package}
/pf work <id> start  -> adapter.start (e.g. command) to close the loop
```

Workers only — PF agents are never routed here (doc §23). P8 returns an **assignment**, it does not itself
run the work beyond the optional adapter `start`.

## API

| Method | Path |
|---|---|
| POST | `/api/v1/engineering/work` |
| POST | `/api/v1/engineering/work/{item_id}/start` |

## 360° check

- Reuses registry/eligibility/claim/adapter/backlog/execution_contract; **no new store**.
- Fail-closed: unregistered worker → not assigned; no eligible → not assigned; contract validated.
- Manual first (doc §21); automatic dispatch is P9.

## Verification

```
python scripts/dev/work_pull_check.py     # OK (pull/package/no-double-pull/start)
python -m pytest .../test_work_pull.py    # 4 passed
python scripts/dev/precheck.py            # PASS
```
