# OpenTelemetry GenAI Observability (incl. multimodal) — Design (BI-0199)

## Goal
Emit **GenAI-style OTel spans** for every LLM/generator call — including **multimodal** attributes
(media parts in/out, modalities, token/cost) — on the canonical event stream, so the media chain is as
traceable as the text chain. Flag-gated export; API-first; no new store.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| OTel mapping | `core/otel.py`: `to_span(ev)` (generic), `export(project)` flag-gated to `otel-spans.jsonl` | add `gen_ai` attributes incl. multimodal | `core/otel.py` |
| Trace context | `core/tracing.py` (`trace_id`, `new_span_id`); `events.emit` sets trace/span | reuse | reuse |
| Event stream | `core/events.py` `emit/read`, `TYPES`, single writer via `log_router` | emit a `gen_ai` event per call | reuse |
| LLM calls | `llm_client._call_llm_single` (token_info incl `media_requested/attached/degraded_media`) | emit span with gen_ai + media attrs | `llm_client` |
| Generators | `generator_adapters` (kind/provider_kind/billing_unit) + `call_ledger kind=generator` | emit a gen_ai span | `generator_adapters` |
| API | `POST /api/v1/otel/export` | + `GET /api/v1/otel/spans` (read) | `dashboard/api` |
| Export flag | `PIPELINE_OTEL` | reuse | `core/otel.py` |

**Blast radius:** `otel.py` (gen_ai mapping), `events.TYPES` (+`gen_ai_call`), `llm_client`/`generator_adapters`
(emit), API, tests. No new store; one writer (events/log_router).

## Design decisions (modular)
- **Extend `core/otel.py`**: `gen_ai_attributes(ev)` → OTel **GenAI semantic conventions**:
  `gen_ai.system` (provider), `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.operation.name`
  (chat|image_generation|tts|…), `gen_ai.usage.input_tokens/output_tokens`, plus **multimodal**:
  `gen_ai.input.modalities` (list), `media_requested`, `media_attached`, `degraded_media.count`,
  and `gen_ai.output.modalities` for generators. `to_span` includes these when present.
- **Emit a canonical `gen_ai_call` event** at the LLM/generator call (via `events.emit`, single writer):
  fields `provider, model, operation, input_tokens, output_tokens, media_requested, media_attached,
  degraded_media, duration_ms, kind`. Bounded (counts, not payloads — **never** log media bytes/content).
- **Reuse trace context**: `events.emit` already stamps `trace_id`/`span_id`; span parent = run trace.
- **Two emit sites:** `llm_client._call_llm_single` (after token_info is built; operation=chat) and
  `generator_adapters.submit` (operation=media kind). Both guarded, fail-open (never break the call).
- **API-first:** `GET /api/v1/otel/spans?project=` returns mapped GenAI spans (read over events);
  keep `POST /api/v1/otel/export` (flag-gated write).
- **Privacy/scale:** attributes are **counts + ids only** — no prompts/media content; bounded cardinality.
- **No duplication:** single event stream (`events`/`log_router`); `otel` only *maps*, never writes its own.

## Plan (branch `feature/bi-0199-otel-genai`)
1. `docs/OTEL-GENAI-DESIGN.md` (this file).
2. `core/events.py` — add `gen_ai_call` to `TYPES`.
3. `core/otel.py` — `gen_ai_attributes(ev)`, extend `to_span`; `spans(project)` reader (maps the stream).
4. `core/orchestrator/llm_client.py` — emit `gen_ai_call` from `_call_llm_single` (chat; incl media counts).
5. `core/generator_adapters.py` — emit `gen_ai_call` from `submit` (media kind/billing_unit).
6. `dashboard/api/app.py` — `GET /api/v1/otel/spans`.
7. Tests `test_otel_genai.py` — mapping includes gen_ai + multimodal attrs; an LLM emit produces a span
   with tokens; a generator emit produces a media span; no content/bytes leak; disabled export no-op.
8. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
9. Merge; close `BI-0199` through the loop.

## Acceptance
- Each LLM call yields a `gen_ai_call` event → a span with `gen_ai.system/model` + token usage.
- Multimodal calls carry `gen_ai.input.modalities` + media counts (no payloads); generators carry
  `gen_ai.output.modalities` + billing unit.
- `GET /api/v1/otel/spans` returns the mapped spans; export still flag-gated; `precheck` PASS; no new store.

## Out of scope (tracked separately)
OTLP collector transport, MCP/A2A/AG-UI (0196–0198), cost attribution (0194).
