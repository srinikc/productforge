# PFSSOT-P5 — Claim + Lease + Recovery (single claimer)

**Item:** BI-PF-0366 (epic BI-PF-0360) · extends `core/job_manager.py` (+ fixes IS-PF-0034)

Turns read-only eligibility (P4) into an **atomic claim with a lease** so no two workers get the same task
and a crashed worker doesn't strand work (doc §12–§14/§37).

## Primitives (job_manager)

| fn | does |
|---|---|
| `claim_next(scope, project, worker)` | pick highest **eligible** item (P4) → create the canonical job (`enqueue`) → **atomic** `BEGIN IMMEDIATE` bind (`worker/assignment_id/lease_id/lease_expires_at/attempt`) → write item `execution{}` via `backlog.set_execution`. No double-claim. |
| `renew_lease(...)` | extend `lease_expires_at` (heartbeat) |
| `release(...)` | clear lease; item back to READY (or terminal) |
| `recover_expired(...)` | leases past expiry → recovery policy |

**Recovery policies:** `RESUME|RETRY|REASSIGN|MARK_FAILED|REQUIRE_REVIEW` (default **REQUIRE_REVIEW** —
never blind re-run of non-idempotent work). Config: `PF_LEASE_SECONDS`, `PF_LEASE_RECOVERY`.

## Single claimer (IS-PF-0034 fixed)

`core/portfolio.py` `enqueue`/`claim`/`finish` now **delegate to `core.job_manager`** — the legacy duplicate
claimer is gone; one queue, one claimer.

## API

| Method | Path |
|---|---|
| POST | `/api/v1/engineering/schedule/claim` |
| POST | `/api/v1/engineering/schedule/lease/{item_id}/renew` |
| POST | `/api/v1/engineering/schedule/lease/{item_id}/release` |
| POST | `/api/v1/engineering/schedule/recover` |

## 360° check

- Atomicity via the existing SQLite `BEGIN IMMEDIATE` (no new lock/queue); item state via `backlog` (single writer). **No new store.**
- Eligibility is authoritative (P4); recovery is fail-closed (review default).
- **P5 does not** add worker registry/heartbeat/adapters (P6/P7) or auto-dispatch (P9).

## Verification

```
python scripts/dev/lease_check.py     # OK (claim/lease/no-double-claim/renew/release/recover + single claimer)
python -m pytest .../test_claim_lease.py   # 4 passed
python scripts/dev/precheck.py        # PASS
```
