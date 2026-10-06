# PIDL-3 — Worker-result Decision Gate (primary trigger)

**Item:** BI-PF-0378 (epic BI-PF-0375) · `core/pidl.py` + `core/close_loop.py` + `POST /engineering/pidl/gate`

The **primary PIDL trigger** (doc appendix #2): when a run produces a result/proposed action, the
**orchestration path** evaluates it through PIDL and acts on the structured decision. PIDL is never invoked
by the worker itself.

## Wiring (shared result boundary)

`core/close_loop.verify_and_close` — the run-result → close boundary used by **both** the native PF agent
path and the optional worker path — invokes `pidl.gate(...)`. This keeps PIDL a **shared decision capability**
(not a scheduler, not an agent persona) and adds no second orchestration engine.

## Mode

`PIDL_GATE_MODE` (`config/env-flags.json`, owner `core/pidl.py`):

| mode | behaviour |
|---|---|
| `advisory` (**default**) | compute the decision and record it on the item under `links.pidl`; **do not** change close behaviour |
| `enforce` | hold a non-`AUTO_PROCEED` close: mark the item `blocked` for review/approval instead of auto-closing |

Advisory-by-default keeps existing close behaviour stable and keeps the gate removable; **PIDL-5** completes
approval-policy enforcement.

## Contract

`pidl.gate(scope, project, *, item_id, result, action, components, area, conflicts, failures, escalated,
run_id)` = `decide()` + provenance (`item_id`, `run_id`, `worker_id`, `runtime`, `gate_mode`). Pure/read-only;
the caller acts. Recorded on the item via `backlog.update(..., links={"pidl": {...}})` — backlog stays the
single writer; no new store.

## API (API-first)

`POST /api/v1/engineering/pidl/gate?scope=&project=` with body `{item_id, run_id, result, action, area,
components, conflicts, failures, escalated}` (read-only).

## Verification

```
python scripts/dev/pidl_gate_check.py   # precedence, modes, provenance, wired-at-close assertion
python scripts/dev/pidl_check.py        # resolver + decision contract
```
