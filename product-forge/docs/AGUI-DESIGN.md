# AG-UI Typed Event Stream — Design (BI-0198)

## Goal
Emit an **AG-UI-compatible** typed event stream (`RUN_*`, `STEP_*`, `TEXT_*`, `TOOL_CALL_*`, `STATE_*`)
derived from our canonical event bus, so the dashboard/external clients consume a **standard, typed**
stream with **no coupling to internals**. API-first; bounded/scalable; single source (events).

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| SSE stream | `/api/v1/events` (BI-0056) raw `data: <event json>` tail | keep; add typed AG-UI **mapping** | `dashboard/api` + new `core/agui.py` |
| Event bus | `core/events.py` `emit/read` + `TYPES` (run/stage/agent/gen_ai/tokens/plan) | map → AG-UI event types | reuse |
| Trace ctx | `events` stamps `trace_id`/`span_id` | map to AG-UI `runId`/`threadId` | reuse |
| Trace endpoints | `/api/v1/trace`, `/api/v1/otel/spans` | consistent typed view | reuse |
| Redaction | `log_router.redact` | unchanged (no content) | reuse |

**Blast radius:** new `core/agui.py` (pure mapper), an SSE variant / endpoint, tests. No new store; no
change to the canonical stream (AG-UI is a *projection*).

## Design decisions
- **New `core/agui.py`** — pure projection `map_event(ev) -> AGUI dict | None` and `stream(project_dir)`:
  - Mapping (canonical → AG-UI):
    - `run_started` → `RUN_STARTED`; `run_completed` → `RUN_FINISHED`; `run_failed` → `RUN_ERROR`
    - `stage_started|agent_started` → `STEP_STARTED`; `stage_completed|agent_completed` → `STEP_FINISHED`
    - `agent_stage_changed`/`plan_confirmed` → `STATE_DELTA`
    - `tokens_used`/`gen_ai_call` → `TEXT_MESSAGE_CONTENT`-adjacent usage meta (typed `USAGE`)
    - `human_input_required`/`agent_blocked` → `CUSTOM`/`STEP_*` blocked
  - Each AG-UI event: `{type, threadId(=project), runId(=trace_id/run_id), timestamp, delta/name/usage}`
    — **bounded, no content/secrets** (reuse redaction).
- **API-first:** `GET /api/v1/agui/events?project=` (SSE, typed AG-UI) alongside the existing raw
  `/api/v1/events`; `GET /api/v1/agui/run/{run_id}?project=` returns the ordered typed event list
  (nice for tests/replay). Both read-only over the canonical stream.
- **Scalable:** pure stateless projection (tail the file → map → emit); no extra store, no per-client state
  beyond file offset (like the existing SSE). Works for any number of subscribers.
- **Backward-compatible:** raw `/api/v1/events` unchanged; AG-UI is additive.
- **Fail-closed/robust:** unknown event types → `CUSTOM` (never dropped, never raises).

## Plan (branch `feature/bi-0198-agui`)
1. `docs/AGUI-DESIGN.md` (this file).
2. `core/agui.py` — `map_event`, `map_all(project_dir, run_id="")`, `types()`.
3. `dashboard/api/app.py` — `GET /api/v1/agui/events` (SSE) + `GET /api/v1/agui/run/{run_id}`.
4. Tests `test_agui.py` — mapping for each lifecycle/step/usage; unknown→CUSTOM; run filter; no content leak.
5. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
6. Merge; close `BI-0198` through the loop.

## Acceptance
- A client subscribes to `/api/v1/agui/events` and receives typed `RUN_*`/`STEP_*`/usage events in order.
- `GET /api/v1/agui/run/{run_id}` returns the ordered typed list; unknown types → `CUSTOM`.
- No internals coupling (mapping is a projection); raw `/api/v1/events` unchanged; `precheck` PASS; no new store.

## Out of scope (tracked separately)
MCP (0196), A2A (0197), frontend UI implementation (dashboard backlog).
