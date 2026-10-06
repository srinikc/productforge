# PIDL-4 — Pre-dispatch + Cross-worker Synthesis + Consequential-action Gate

**Item:** BI-PF-0379 (epic BI-PF-0375) · `core/pidl.py` + `core/work_pull.py` + `core/close_loop.py` + API

The remaining PIDL triggers (doc appendix #1/#3/#4). Additive; reuses PIDL-1/2/3; no second engine/store.

## 1. Pre-dispatch evaluation (trigger #1, optional)

`pidl.pre_dispatch(...)` returns the exact `pidl_context` + `execution_policy` a worker's execution contract
carries — the doc's *"what the worker actually receives"* (relevant subset, never the whole personality).
**Wired** in `core/work_pull._package`: the assignment package now includes `pidl_context` + `execution_policy`.
Read-only/advisory; the scheduler still decides whether/when the work runs.

## 2. Cross-worker synthesis (trigger #3)

`pidl.synthesize(results=[...])` evaluates combined parallel results for **consistency**: it detects status
disagreement and path overlap (reusing `scheduler.path_overlap`) and returns the decision contract plus a
`synthesis` summary (`consistent`, `conflicts`). `CORRECT` on conflict, `REVIEW` when incomplete, else
`AUTO_PROCEED`. **Wired** in `core/close_loop.verify_and_close` when a run closes **multiple** items: records
`pidl_synthesis`; in `PIDL_GATE_MODE=enforce` a conflicting synthesis holds the close.

## 3. Consequential-action gate (trigger #4)

`pidl.consequential_gate(...)` returns `APPROVAL_REQUIRED` for consequential actions (architecture/security/
destructive/production/release/…), else `AUTO_PROCEED`. Surfaced in the assignment `execution_policy.
approval_required` and enforced by the PIDL-3 close gate; no new blocking path.

## API (API-first)

`POST /api/v1/engineering/pidl/pre-dispatch` · `/pidl/synthesize` · `/pidl/consequential` (read-only).

## Non-goals

No personality worker/queue; no scheduler redesign; PIDL stays decoupled from the worker layer (the worker
layer reads PIDL, never the reverse).

## Verification

```
python scripts/dev/pidl_synthesis_check.py   # pre-dispatch contract, synthesis conflicts/consistency, wiring
python scripts/dev/pidl_gate_check.py        # result gate
```
