# Pipeline Operations, State & API

> Single reference for how the pipeline is started/controlled/resumed and what
> state it persists. Updated with wiring status.

## 1. Run entrypoint
`scripts/run_pipeline.py` (framework-agnostic):

| Flag | Meaning |
|---|---|
| `--project <name>` | project under `products/` (required) |
| `--idea "<text>"` | seed Stage 0 (new project) |
| `--pipeline <file>` | pipeline definition (default `pipeline-definition.json`) |
| `--products-dir <dir>` | default `products` |
| `--tier <name>` | model tier profile (`actual`, `free-trial`, …) `PIPELINE_MODEL_TIER` |
| `--tier-list` | list tier profiles and exit |
| `--tier-info <name>` | show one tier's details (per-agent models + fallbacks) |

Tier resolution order: `--tier` (env) → `project.json: model_tier` → config `active_tier`.

## 2. Run modes
| Mode | How |
|---|---|
| **New project** | `run_pipeline.py --project X --idea "..." [--tier …]` |
| **Continue / resume** | same command without `--idea`; the executor auto-resumes from `pipeline-state.json` (completed stages skipped) |
| **Restart (fresh)** | delete `products/X/pipeline-state.json` (or API `restart`) then run |
| **Modify existing** | continue; new/changed stages run, completed ones skip |

## 3. Control (cross-process)
The executor polls `products/<project>/control.json` each loop iteration.

| Action | Mechanism |
|---|---|
| **stop** | write `{"action":"stop"}` (CLI `stop()` / API `pipeline-stop`) |
| **pause** | write `{"action":"pause"}` (API `pipeline-pause`) — loop sleeps until resume |
| **resume** | write `{"action":"resume"}` (API `pipeline-resume`) |
| **restart** | delete `pipeline-state.json` + `control.json`, relaunch (API `restart`) |

Locking: `LockManager` (`products/.locks/<project>.lock`) prevents concurrent runs; stale locks are auto-cleaned on start.

## 4. State files (per project `products/<project>/`)
| File | Purpose |
|---|---|
| `pipeline-state.json` | checkpoint/resume (completed stages, iteration, totals) — atomic writes |
| `control.json` | cross-process stop/pause/resume signal |
| `project.json` | project config (idea, `model_tier`, `enable_*` flags, budget) |
| `project-config.json` | canonical config for compliance |
| `pipeline-execution-report.json` | final report (stage/agent tokens, compliance, `cost_kpi`, `feature_health`, `nfr_coverage`) |
| `agent-audit-log.json` / `agent-audit.md` | per-agent audit |
| `PROJECT-STATUS.md`, `project-status.json` | live journal/status |
| `docs/agent-context.md`, `docs/compact/<stage>-summary.md`, `docs/feature-status.md` | checkpoints |
| `product-plan.json`, `architecture/product-plan.md` | feature-level tracking |
| `compliance/*.json` | compliance + LLM verification reports |
| `notifications.json`, `llm-errors.json` | reliability |
| `issue*` / `issues/*.json` | security/NFR/test issues |
| `docs/tech-stack.json`, `docs/ports.json` | agreed stack + derived ports |

Global: `products/.pipeline/model_registry.json` (catalog), `products/.pipeline/cost_metrics.jsonl`, `products/.pipeline/tool_cache.json`, `products/.pipeline/pipeline_cost_history.json`.

## 5. API (dashboard)
`pipeline_dashboard/api/*` + `router.py` (custom router → `serve.py`). Pipeline control: `api/pipeline.py`.

| Endpoint | Action | Status |
|---|---|---|
| `GET /api/tiers` | list tier profiles + details | ✅ wired |
| `GET /api/tier/<name>` | one tier's per-agent models | ✅ wired |
| `POST /api/pipeline/run` or `start` | **start** (detached) returns pid | ✅ wired (was a no-op instructions dump) |
| `POST /api/pipeline/restart` | clear state + start fresh | ✅ wired |
| `POST /api/pipeline/stop` | write control.json | ✅ (cross-process via control file) |
| `POST /api/pipeline/pause` / `resume` | write control.json | ✅ |
| `GET /api/pipeline` | stage list | ✅ |
| `GET /api/projects`, `/api/project/<n>` | projects/status | ✅ |
| `GET /api/models` | registry models/tiers | ✅ |
| `GET /api/telemetry`, `/api/budget`, `/api/journal`, `/api/alerts`, `/api/delegation`, `/api/iterations`, `/api/compliance`, `/api/logs` | governance data | ✅ |

Actions routed through `api/pipeline.py:run(action, project)`; unknown actions return `{"error": ...}`.

## 6. Legacy CLI
`scripts/pipeline.py` provides display/management commands (`list`, `status`, `health`, `checkpoints`, `dlq`, `budget`, `models`, `report`, `phases`, `context`, `ledger`, `cost-kpi`, `version`, `reviews`, `knowledge`, `queue`, `circuit-reset`, …). Some back onto legacy modules; the authoritative run path is `run_pipeline.py` + `PipelineExecutor`.

## 7. Known wiring notes
- `stop/pause/resume` were previously ineffective (instance flags in a throwaway executor); now cross-process via `control.json`.
- API `start` previously only printed "continue" instructions; now launches the run.
- Tier selection is available at CLI (`--tier`, `--tier-list`, `--tier-info`), via `project.json: model_tier`, and via `GET /api/tiers`.

## 8. Standardized status & dependency model
One vocabulary at every level (phase -> stage -> agent), defined in
`core/orchestrator/status.py`:

| Status | Meaning |
|---|---|
| `pending` | not started |
| `blocked` | dependencies not satisfied (won't run yet) |
| `running` | in progress |
| `completed` | done |
| `failed` | errored |
| `skipped` | intentionally not run |
| `stale` | was completed, but an upstream dependency changed -> needs rerun |
| `needs_retry` | ran but must rerun (compliance/validation) |
| `escalated` | needs human |

A dependency is **satisfied** when it is `completed` or `skipped`. Otherwise the
dependent stage/agent reports **`blocked`** with `unmet_dependencies`.
A `pending`/`stale` stage with unmet deps is shown as `blocked`; once deps are met a
stale stage is runnable again.

### Status snapshot
- `PipelineExecutor.get_status()` returns `{phase, current_stage, stages:{id:{status,
  depends_on, unmet_dependencies, agents:[{agent_id,status,model,tokens,...}]}}, summary}`.
- API: `GET /api/pipeline/status?project=<name>` (also `executor-status` action).

## 9. Resume & selective rerun
- **Resume**: `pipeline-state.json` now restores DAG stage states on load
  (`_restore_from_checkpoint`), so completed stages are **skipped** and artifacts are
  rehydrated. (Previously only the iteration counter was restored -> re-ran everything.)
- **Selective rerun** (`scripts/run_pipeline.py`):
  - `--agent <id[,id]>` -> rerun the stages containing those agents
  - `--only-stage <id[,id]>` -> rerun those stages
  - `--from-stage <id>` -> rerun that stage and everything downstream
  On rerun, the target stages reset to `pending` and all **transitive dependents** are
  marked `stale` (and removed from completed state) until re-executed — so the dashboard
  shows them as `blocked`/`stale` rather than "done".

## 10. Agent-level operations & control API
Agent-level ops are supported in addition to stage-level, persisted via `run-scope.json`
so a (re)launched process honors the scope.

### CLI (`scripts/run_pipeline.py`)
| Flag | Effect |
|---|---|
| `--agent a[,b]` | rerun the stage(s) containing those agents; within a stage, downstream agents (via `agent_dependencies`) also rerun; **all downstream stages invalidated** (default) |
| `--only-stage s[,s]` | rerun only those stages (downstream invalidated) |
| `--from-stage s` | rerun that stage and everything downstream |
| `--only` | run **only** the selected stages/agents; dependents stay `pending`/`blocked` |

Default (no `--only`): selected agent/stage **plus all transitive downstream** re-run —
conservative and correctness-first. `invalidate_for_rerun` marks downstream stages
`stale` (shown `blocked` until their deps complete).

### Control API
| Method + path | Body / query | Purpose |
|---|---|---|
| `GET /api/pipeline/status?project=` | — | standardized phase/stage/agent status |
| `GET /api/agents/status?project=` | — | flattened agents with `stage`, `status`, `unmet_dependencies` |
| `POST /api/pipeline/rerun` | `{project, agents[]\|agent, stages[]\|stage, from_stage, only, tier}` | selective rerun + launch |
| `POST /api/pipeline/retry` | `{project, agent}` | retry one agent (`only=true`) |
| `POST /api/pipeline/control` | `{action, project}` | run/start/stop/pause/resume/restart |
| `POST /api/forge/stop\|pause\|resume` | `{project}` | control via `control.json` |

### Status guarantees
- Statuses standardized (`pending/blocked/running/completed/failed/skipped/stale/needs_retry/escalated`).
- Stage status = raw status; `pending`/`stale` with unmet deps reported `blocked` + `unmet_dependencies`.
- Agent status from executions; agents with unmet within-stage prerequisites reported `blocked`.
- All state persisted (`pipeline-state.json` atomic, `run-scope.json`, `control.json`, audit/report),
  so CLI and dashboard/API observe the same state and can control the same run.

### Status semantics (clarified)
- **`pending`** = not yet run (never executed in this plan). This is the default for
  agents/stages that are *yet to run* — **not** `stale`.
- **`blocked`** = a `pending`/`stale` item whose dependencies (stage deps or within-stage
  agent prerequisites) are not yet satisfied. Shown with `unmet_dependencies`.
- **`stale`** = **only** for an item that was previously `completed` and has been
  invalidated by an upstream re-run → needs re-execution.
- **`running` / `completed` / `failed` / `skipped` / `needs_retry` / `escalated`** = as before.

All stage agents are listed (from the stage `ideal_flow`), so agents that have not run
yet appear as `pending`/`blocked` instead of being omitted.

## 11. Interactive runs without a TTY (prompt bridge) — BI-0026
`scripts/run_pipeline.py --interactive` makes the pipeline's own prompts answerable from a
harness (e.g. `/pipeline`) instead of a terminal. `core/interactive.py` routes every prompt
through a file channel; the runner stays the single brain.

```powershell
# launch (writes a pending prompt, then polls)
python scripts/run_pipeline.py new <project> --interactive --tier <tier>

# from another shell / the agent harness:
python -m core.interactive --project <project> --list           # show pending prompts
python -m core.interactive --project <project> --answer P1 "…"  # answer one
```

- **Prompts covered:** project name, brief (Stage 0), tier, enhance goal, integration HIL,
  deployment target, and the `--step` pause after each agent (`--interactive` implies `--step`).
  Approval gates were already file-based (`approve.py`).
- **Precedence:** bridge on ⇒ always file-relayed (wins over `isatty()`); bridge off ⇒ TTY
  `input()`, else the default. **Terminal behaviour is unchanged** when the flag is absent.
- **Store:** `prompts.json` (kind=control; `products/<p>/interactive/`, or `products/.interactive/`
  for the pre-project prompt); single writer `core/interactive.py`; env `PIPELINE_PROMPT_TIMEOUT`
  (default 1800s) bounds the wait — an unanswered prompt falls back to its default, never hangs.
