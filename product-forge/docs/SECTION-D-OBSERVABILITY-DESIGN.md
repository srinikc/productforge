# Section D — Observability & Seamless Execution: design & plan (BI-PF-0244)

> Design-first (per EOS §4): **DESIGN → PLAN → 360° → implement**. This is the design/plan for the
> industry-standard observability layer (LOGS-AND-OBSERVABILITY.md Appendix D). Implementation is sliced.

## 1. DESIGN — outcome & invariants
- **Outcome:** one trustworthy, queryable, low-cost observability layer such that any run/stage/agent/tool call is
  traceable end-to-end, status is derived (never disagreeing), and SLIs/SLOs are measurable.
- **Invariants:** one schema; `trace_id`(=run_id) on **every** record; state derived from the event stream;
  bounded cost (compact, sampled where appropriate); secrets/PII redacted.

## 2. 360° — current vs target (affected modules)
| Concern | Now | Target | Owner |
|---|---|---|---|
| Event/log path + append | `core/log_router.py` (paths, append_jsonl, retention) | same, single owner | `log_router` |
| Event schema | `core/events.py` (typed) | + `trace_id`/`span_id`/`level` | `events` |
| Two streams | converged (mirror + canonical SSE) | one canonical stream | `event_bus`/`events` |
| State | derived in `core/run_status.py` | derived strictly from stream | `run_status` |
| Per-agent logs | `log_router.log_event` (`ts|level|run|stage|agent|event|msg`) | same + trace_id | `log_router` |
| Query | `GET /api/v1/logs` | + trace filter; run/agent/stage/level | `dashboard/api` |
| Trace | none | `core/tracing.py` (trace/span ids), OTel export | new |
| Metrics/SLI | `core/quality_metrics.py`, `/metrics` | SLIs (success, p95, tokens, retries) | new/`quality_metrics` |
| Redaction/retention | `rotate_runs` | + redaction + per-schema retention | `log_router` |

**Dependencies/consumers (blast radius):** `events`, `event_bus`, `log_router`, `run_entry`, `job_manager`,
`stage_runner`/`agent_runner`/`llm_client` (emit points), `run_status`, `call_ledger` (accounting), `dashboard/api`,
`core/views.py`. All read/write via `log_router`/`events` — keep those as the only writers.

## 3. PLAN — phases (each shippable + tested)
- **P1 Trace context:** `core/tracing.py` (`trace_id`=run_id, `new_span_id`, context); add `trace_id`+`span_id` to
  every event/log line; `GET /api/v1/logs` filter by `trace_id`. **(slice 1 — now)**
- **P2 Structured schema + levels:** single canonical record schema documented + validated; `level` everywhere;
  redaction of secret-looking fields.
- **P3 Event-sourcing/CQRS:** `run_status` + projections derive **only** from the stream (no parallel writers);
  rebuild-on-demand.
- **P4 Metrics + SLIs/SLOs:** success rate, p95 latency, tokens/cost, retries per stage/agent; expose in `/metrics`.
- **P5 OTel export:** map records to OTel spans (`gen_ai.*`); OTLP file/collector export (optional, flag-gated).
- **P6 Trace UI + retention/redaction:** per-run trace view; `log_router` retention per schema; KEEP compact.

## 4. Acceptance (for the whole item)
- Every event/log line carries `trace_id`+`span_id`; `/api/v1/logs?trace_id=` returns the full trace.
- `run_status`/projections are pure derivations of the stream.
- SLIs surfaced; export flag-gated; nothing bloats prompts.

## 5. Progress
- **P1 done:** `core/tracing.py` + `trace_id`/`span_id` on every event + `/api/v1/logs?trace_id=`.
- **P2 done:** canonical `level` on events; **secret redaction** applied to every log line + JSONL event write
  (`log_router.redact`).
