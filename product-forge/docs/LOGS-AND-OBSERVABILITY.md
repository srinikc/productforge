# Logs & Observability — current map and SSOT gap

> **As-is map (2026-09-27).** What is logged today, where, by whom — and why it is **not** yet a single
> source of truth. Companion: `pipeline_current_issues.md`, `config/log-conventions.json` (owner `core/log_router.py`).
>
> **Verdict:** logging/observability is **scattered across ~20 files in 4 trees**, uses **two different event
> streams**, and is **incomplete** (no prompt/response, thin per-agent logs, inconsistent ids). There is **no SSOT**
> for "what is the pipeline / a project run / an agent doing?" — this must be re-architected (see §5).

---

## 1. The current map (as-is)

### A. Pipeline backend (the engine itself)
| Artifact | Path (actual) | Writer | Contains |
|---|---|---|---|
| Backend log | `data/logs/pipeline-backend.log` | `core/run_entry.py` (`log_router.backend_log_path`) | backend start/stop, dispatch |
| ~~Backend log (convention)~~ | `product-forge/logs/pipeline-backend.log` | — | **ABSENT** (config says here; reality is `data/logs/`) |
| Pipeline runs registry | `products/<p>/pipeline-runs.json` | `core/run_state.py` | run attempts + linkage |
| Backend index | `product-forge/logs/index.html` | `core/views.py` | **ABSENT** |

### B. Per-project run
| Artifact | Path | Writer | Contains |
|---|---|---|---|
| Console run log | `products/<p>/pipeline-run.log` | runner stdout (`run_entry`) | **richest narrative**: per-stage summary (tokens/cost/model, features, sections, next stage) + `human_proxy` decisions |
| Stdout/stderr | `products/<p>/run.out.log`, `run.err.log` | detached `Start-Process` | raw process output |
| Manifests | `products/<p>/pipeline-state.json`, `project-status.json`, `PROJECT-STATUS.md`, `run-status.json`, `agents-live.json` | `pipeline_executor`, `run_status`, `product_page` | **4–5 overlapping state/status files** |
| Log index | `products/<p>/logs/index.html` | `core/views.py` | static snapshot of runs → agents → files |

### C. Per-agent / per-run log files
| Artifact | Path | Writer | Contains |
|---|---|---|---|
| Pipeline log (run) | `products/<p>/logs/<run_id>/<run_id>-pipeline.log` | `core/log_router.py` | `run_start`, `stage_complete` only |
| Agent log | `products/<p>/logs/<run_id>/<stage>-<agent>.log` | `core/log_router.py` | `agent_start` / `agent_complete` (tokens, cost, model, artifacts) — **lifecycle only, no prompt/response** |
| Run manifest | `products/<p>/logs/<run_id>/INDEX.json` | `core/log_router.py` | file/size/updated for the run |

### D. Events (two different streams!)
| Artifact | Path | Writer | Consumed by |
|---|---|---|---|
| Global orchestration bus | `products/.orchestration/events.jsonl` | `core/event_bus.py` | **dashboard SSE** (`/api/v1/events`, `dashboard/api/app.py:217`) |
| Per-project events | `products/<p>/events.jsonl` | `core/events.py` | analytics / heartbeats / `agent_completed` / `run_failed` |
> The live-feed reads the **global** stream, but run/heartbeat/failure events are written to the **per-project** stream → the dashboard can miss them. (The `.orchestration` dir was empty while `smoke-all/events.jsonl` held the heartbeats.)

### E. Accounting
| Artifact | Path | Writer | Contains |
|---|---|---|---|
| Call ledger | `products/<p>/call-ledger.jsonl` | `core/call_ledger.py` | per **LLM/tool call**: agent, model, prompt/output/reasoning tokens, chars, duration, strategy |
| Work estimate | `products/<p>/work-estimate.json` | `core/work_estimate.py` | predicted call shape/time |
| Telemetry | `products/<p>/quality-metrics.json`, `budget.json` | `quality_metrics`, `budget` | metrics/cost rollups |

### F. State / status
`pipeline-state.json` (stage execution) · `run-status.json` (derived) · `project-status.json` / `PROJECT-STATUS.md` (projection) · `agents-live.json` (live snapshot) · `pipeline-runs.json` (run registry). **Five files describe "where are we" — and they can disagree.**

### G. Audit / evidence
`products/<p>/agent-audit-log.json` + `agent-audit.md` (`core/orchestrator/storage.py`) · `audit-trail.json` (`core/audit_trail.py`) · `products/ledger/agent_ledger.json` · `review-ledger.json`.

### H. Dashboard
`dashboard/logs/dashboard.log` — **ABSENT** (not built yet per convention).

---

## 2. Why this is hard to debug (trace one step)

Tracing a single agent step ("design, stage 1") requires opening **five** places:
1. Live: `products/.orchestration/events.jsonl` (SSE) — **may be empty**.
2. Run events: `products/smoke-all/events.jsonl` — heartbeats + `agent_completed` + `run_failed`.
3. Per-agent: `products/smoke-all/logs/run-1790446354/1-design.log` — start/complete + tokens.
4. Narrative: `products/smoke-all/pipeline-run.log` — the stage summary.
5. Accounting: `products/smoke-all/call-ledger.jsonl` — the 9 individual calls.

There is **no single record** that answers "what did this agent do, on which model, with which prompt, at what cost, and did it pass?".

---

## 3. Problems (evidence)

1. **No SSOT / no unified schema.** ~20 files, 4 roots (`products/<p>/`, `data/logs/`, `product-forge/logs/` absent, `dashboard/logs/` absent), each with its own shape. `config/log-conventions.json` exists but is **not** enforced end-to-end.
2. **Two event streams** (`products/.orchestration/events.jsonl` vs `products/<p>/events.jsonl`) → live feed and history diverge.
3. **Incomplete step logs.** Per-agent logs hold **no prompt and no response**; tool calls are not logged (`call-ledger` shows `tool_calls: 0`; the tool loop is invisible).
4. **Attribution loss.** `1-design.log` shows `agent_complete` with `run_id = "-"`, and `events.jsonl` shows `{"type":"run_failed","run_id":""}` → the failure couldn't be correlated. This is the direct cause of `run-status.json` = `failed` while stages = `running`.
5. **Config vs reality.** Convention paths `product-forge/logs/…` and `dashboard/logs/…` do **not** exist; the backend log is written to `data/logs/pipeline-backend.log`.
6. **5 overlapping state files** with no single precedence rule.
7. **Static views.** `logs/index.html` is a snapshot generated by `core/views.py`, not live; there's no query/filter API over logs.
8. **Rotation/retention** declared in config (`keep_runs: 20`) but not consistently enforced.

---

## 4. What a query looks like today

- Human: open `products/<p>/pipeline-run.log` (+ `logs/index.html`).
- Machine: read `call-ledger.jsonl` / `events.jsonl` / `run-status.json` — and hope they agree.
- API: only `GET /api/v1/events` (SSE on the global stream) — **no logs query API**.

---

## 5. Target design (SSOT) — what needs to change

**One writer, one schema, one tree, one query surface.**

1. **Single writer = `core/log_router.py`.** Only this module creates/appends any log/event file. Everything else calls `log_router.log_event(...)` / `event_bus.emit(...)` routed through it.
2. **One record schema (all files JSONL):**
   ```
   {ts, level, run_id, project, stage, agent, event, message, data{...}, }
   ```
   `run_id` **always** present (also on terminal + complete events). Human `.log` lines are a rendering of this.
3. **One event stream.** Merge `products/.orchestration/events.jsonl` and `products/<project>/events.jsonl` into **`products/<project>/logs/<run_id>/events.jsonl`**, with a global tail/`logs/index.json` registry. The SSE endpoint reads the same store it writes.
4. **One tree (per convention, enforced):**
   ```
   products/<project>/logs/<run_id>/      per-run + per-agent + events + INDEX.json
   product-forge/logs/                    backend
   dashboard/logs/                        dashboard
   ```
   Fix the two absent dirs + move the backend log to the convention path.
5. **Capture what's missing:** prompt/response + tool calls, **flag-gated** (`PIPELINE_VERBOSE`/`logLevel`) so it's off by default but available for debugging (this is BI-0229's scope, extended to prompts).
6. **One status derivation:** `run-status.json` is *derived only* from the unified event stream; delete/auto-generate the overlapping projections so they cannot disagree.
7. **Query API + live:** `GET /api/v1/logs?project&run&stage&agent&level&q` (reads the SSOT) and fix `GET /api/v1/events` to stream the SSOT. `logs/index.html` becomes a live view, not a snapshot.
8. **Enforce rotation/retention** in `log_router` (`keep_runs`, `max_bytes`).

---

## 6. Backlog mapping

| Item | Status | Covers |
|---|---|---|
| **BI-0229** Verbose-gated logging + loops/tool-calls in the summary | open | flag-gated verbosity; surface loops/tool-calls |
| **BI-PF-0233** Unify logs/events into one SSOT (`log_router` only writer; one schema; one tree; fix config paths) | open | §5.1–5.4, 5.8 |
| **BI-PF-0234** Fix terminal-event attribution (`run_id` on `run_failed`/`agent_complete`) + derive `run-status` from the stream | open | §3.4, §5.6 |
| **BI-PF-0235** Logs query API + live log index | open | §5.7 |
| (prompt/response + tool-call capture) | via **BI-0229** | §3.3, §5.5 |

---

## 7. Suggested next step

1. Land the **SSOT skeleton** first (**BI-PF-0233** + **BI-PF-0234**): single writer + schema + one tree + fix paths + run_id everywhere. This alone removes the "scattered/inconsistent" pain.
2. Then **BI-0229** (verbose flag + prompt/tool capture).
3. Then **BI-PF-0235** (query API + live index).

> This document is the **as-is map**. It should be updated to the target once the SSOT lands.
