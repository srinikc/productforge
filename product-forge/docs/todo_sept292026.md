# TODO — September 29, 2026

> Product Forge working to-do (logs/observability + seamless execution + non-backlog fixes).
> Sources: `docs/LOGS-AND-OBSERVABILITY.md` (App. D & E), `docs/pipeline_current_issues.md`.
> Backlog SSOT: `data/backlog/*` via `core/backlog.py`. Implementation truth = the code.

---

## A. Logs / observability — do now (in order)

- [ ] **BI-PF-0233 — Unify logs/events into one SSOT.** `core/log_router.py` is the ONLY writer; one JSONL
  schema `{ts, level, trace_id, run_id, project, stage, agent, event, message, data}`; one tree
  `products/<project>/logs/<run_id>/`; merge the two event streams (`products/.orchestration/events.jsonl`
  vs `products/<project>/events.jsonl`); fix the declared-but-absent paths; enforce rotation/retention.
- [ ] **BI-PF-0234 — Terminal-event attribution.** Put `run_id` on **every** record (incl. `run_failed` /
  `agent_complete`; today they are `""` / `"-"`); derive `run-status` **only** from the unified stream so it
  cannot disagree with `pipeline-state` (fixes `state=failed` while stages=`running`).
- [ ] **BI-0229 — Verbose-gated logging + prompt/response + tool-call capture.** Flag-gated
  (`PIPELINE_VERBOSE`/`logLevel`), PII-redacted; surface loops/tool-calls in the agent-end summary.
- [ ] **BI-PF-0235 — Logs query API + live index.** `GET /api/v1/logs?project&run&stage&agent&level&q` over the
  SSOT; fix `GET /api/v1/events` (SSE) to stream the same store; make `logs/index.html` live (not a snapshot).

## B. Industry-standard blueprint — seamless execution & observability (adopt)

- [ ] **OpenTelemetry** (traces/metrics/logs) + **GenAI semantic conventions** → one span per agent + per
  LLM call + per tool call (`gen_ai.system/model/usage.*`); OTLP export alongside files.
- [ ] **W3C Trace Context** (`trace_id`/`span_id`) → end-to-end correlation; `trace_id` = `run_id`, never blank.
- [ ] **Structured logging** (JSON Lines, one schema) + log levels → machine-queryable; human `.log` is a render.
- [ ] **Event sourcing + CQRS** → append-only event log is the SSOT; **state is derived** (retire the overlapping
  projections).
- [ ] **Three pillars + RED/USE + SLIs/SLOs** → per-stage/agent duration, tokens, cost, retries, failure rate;
  SLOs on run success + p95 latency.
- [ ] **12-Factor App** → logs as an event stream to stdout; all config via env/`config/*.json`; graceful shutdown.
- [ ] **Per-run trace UI pattern** (OpenLLMetry / Langfuse / Helicone / LangSmith) → a run→agent→call tree
  with opt-in prompt/response.
- [ ] **Idempotency + checkpoint/resume + DLQ + backpressure** → seamless recovery; wire the existing
  DLQ/circuit-breakers to the unified stream.
- [ ] **Retention / rotation / sampling / redaction** enforced in `log_router` (`keep_runs`, `max_bytes`).
- [ ] (Execution mechanics that make it verifiable: planner-once/ReWOO, capability steering, structured outputs,
  parallel sections, escalate-on-failure → **BI-0221–BI-0230**.)

## C. Other fixes (outside the backlog)

- [ ] **Stop versioning throwaway run artifacts.** Add to `.gitignore` and `git rm --cached`
  `product-forge/products/e2e-smoke/`, `product-forge/products/smoke-all/`, `product-forge/test-framework/reports/*`.
- [ ] **Fix config-vs-reality log paths.** `config/log-conventions.json` declares `product-forge/logs/` and
  `dashboard/logs/` (both absent); the backend log is actually written to `data/logs/pipeline-backend.log`.
- [ ] **Windows console encoding bug.** `python -m core.backlog --similar …` crashes with `UnicodeEncodeError`
  (cp1252) when a title contains `→`; force UTF-8 stdout or sanitize output.
- [ ] **Auto-refresh generated docs** in pre-commit/CI: `scripts/dev/gen_docs_index.py`,
  `scripts/dev/gen_backlog_summary.py`.
- [ ] **Backlog hygiene (advisory → clean):** record `dashboard_impact` on the 11 backend items; merge the 11
  near-duplicate open pairs; refresh the `model-tier` registry (3 drift) + live-model check (1 drift).
- [ ] **CI gate:** run `compileall` + `wired_audit` + `workflow_matrix_check` on every PR (BI-0205 scopes the PR
  workflow; the gate wiring itself is still manual).
- [ ] **State-file consolidation:** once events are SSOT, retire/auto-generate `project-status.json`,
  `PROJECT-STATUS.md`, `agents-live.json`, `pipeline-runs.json`.

## D. Git / branch (context)

- [x] Committed & pushed `develop` (`e7a0dd5`) — includes 739 files / run artifacts.
- [ ] (Manual, later) merge `develop` → `main` (develop is ahead 24 / behind 1 vs `origin/main`).

---

## References

- `docs/LOGS-AND-OBSERVABILITY.md` — as-is log map, problems, target SSOT, **Appendix D** (standards) / **E** (fixes).
- `docs/pipeline_current_issues.md` — live issues (cost/latency/observability/backlog hygiene).
- `docs/pipeline_review_recommendations.md` — review → BI-0220–BI-0230.
- Backlog: `data/backlog/` (BI-PF-0233/0234/0235, BI-0229) · Backlog page: `data/backlog/index.html`.
