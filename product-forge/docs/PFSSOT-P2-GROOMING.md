# PFSSOT-P2 — AI + User Grooming

**Item:** BI-PF-0363 (epic BI-PF-0360) · `core/grooming.py` + `config/grooming-guidelines.json` (no new store)

Grooming turns a raw backlog item into an execution-ready one: priority, structured dependencies,
architecture-fit/strategy, duplication/drift/conflict findings, risks, readiness, and missing-info.

## Modes

- **AI grooming is the DEFAULT** (`mode="ai"`): reuses the existing agent runtime
  (`PipelineExecutor.execute_agent("analyst", "groom", …)`) — **no new LLM client**.
- **Deterministic** (`mode="deterministic"`, or `ai=false`): no model; uses `backlog.find_similar`,
  `deps`, `links`, `score`. Always available.
- **Auto-fallback:** the AI path falls back to deterministic when no model is live, and is auto-skipped
  when disabled (`PF_GROOMING_AI=0`, `PF_OFFLINE`, `CI`) so gates/CI never make slow live calls.
- **User grooming** (`decide`): APPROVE → analysis `COMPLETE` + item ready; MODIFY → `IN_PROGRESS`;
  DEFER → `NOT_ANALYZED`; REJECT → `STALE`. Recorded in the item's `decisions[]` (reused).

## Guidelines + cadence (data, not code)

`config/grooming-guidelines.json` (owner `core/grooming.py`) holds the checklist, decision options,
and cadence:

```
on_entry (default) · on_pickup_when_defer · on_material_change (P1 marks STALE) · periodic_sweep_days (0=off)
```

No per-read / per-assignment AI. Periodic sweep (if enabled) is a scheduler job, not polling.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/backlog/grooming/guidelines` | checklist + cadence |
| POST | `/api/v1/backlog/items/{id}/groom` | AI by default; `mode=deterministic` or `ai=false` for no-AI |
| POST | `/api/v1/backlog/items/{id}/groom/decide` | APPROVE/MODIFY/REJECT/DEFER |

Maps to the future `/pf groom ai <id>` and `/pf groom <id>` (P10).

## 360° check

- Extends `core/backlog.py` (writes go through `set_analysis`/`set_priority`/`set_dependencies` — single writer); **no new store**; one **config** file registered.
- Reuses the agent runtime (no new LLM client) and HIL `decisions[]` (no new decision store).
- AI-default but automation-safe (offline auto-skip) so the product default is AI while gates stay fast.

## Verification

```
python scripts/dev/grooming_check.py     # OK (AI-default + deterministic fallback, guidelines, decide)
python -m pytest .../test_grooming.py    # 4 passed
python scripts/dev/precheck.py           # PASS
```
