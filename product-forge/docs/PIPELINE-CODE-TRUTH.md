# Pipeline — Code is the Source of Truth (corrections)

> The implementation is authoritative; several older docs were stale. This file
> records the **code-verified** facts (BI-0047) so design/UI work is grounded.
> Verify anytime: `python -m compileall -q core scripts dashboard` +
> `python scripts/dev/wired_audit.py` (exit 0), and `python scripts/dev/invocation_audit.py`.

## Corrections (docs ≠ code)
| Topic | Stale doc claim | Code truth |
|---|---|---|
| Stages | `7a/7b/7c` as stages | **Not stages.** Stage 6 = NFR, stage 7 = packaging. `pipeline-definition.json` has 32 stage ids (`0,0a,1,1a,1b,1c,1d,2,3,3a,4-0,4a..4f(+ -vqa),5,6,7,8,9,10,10a,11,12`). |
| State | `pipeline-state.md` audit | **No writer.** `pipeline-state.json` = truth (`pipeline_executor._save_checkpoint`); `pipeline.json` = derived (`pipeline_store.sync`). |
| Tests location | `test-framework/tests/<project>/` | Runtime reads/writes **`products/<project>/tests/`** (`test_matrix.plan`). |
| `on_complete` | drives flow | **Never executed** (decorative). |
| Observability | Prometheus `/metrics` | **No `/metrics`**; JSON telemetry (`pipeline_telemetry`). |
| Tier precedence | `config/model-tier.json` authoritative | Runtime `ModelRouter.tier_config_candidates` prefers **`products/pipeline_dashboard/model-tier.json`**, then repo `config/`. |
| Ops | stage 13 | **Opt-in post-deploy hook**; `core/ops_phase.py` gated by `ops.enabled`. |
| Roster | `.opencode/agent/*.md` | Runtime roster = **`agents/*.agent.json`** + `config/model-tier.json` + `config/agent-requirements.json`. |
| Reasoning | — | LLM client must **never** use `message.reasoning` as content (BI-0075). |
| Backlog ids | plain `BI-####` | ids are **per-scope** and collide; use **scope-qualified** refs `product_forge:BI-0042`, `project:<p>:BI-0015` (`backlog.qualify/get_by_ref`). |
| Intake | `core/intake_api.py` mounted | deprecated/unmounted; live intake = dashboard API → `core.intake.ingest` → `IntentRouter` → `backlog_link`. |

## New/authoritative modules (this build)
- **API layer** `dashboard/api/app.py` — FastAPI: intake (`/api/v1/intake`), backlog (`/api/v1/backlog`), model-fit (`/api/v1/model-fit`), memory, project archive, capacity, tenancy, licensing, status, SSE (`/api/v1/events`). CORS + bearer auth; operator endpoints 404 on tenant instances.
- **`core/model_fit.py`** — per-tier model/agent capability preflight (+ `model-fit.json`).
- **`core/licensing.py`** — tiers/entitlements/keys/trials/instance-role (+ `licenses.json`, `tenants.json`, `config/licensing-tiers.json`).
- **`core/tenancy.py`** — tenant members/teams/roles/seats (+ `members.json`).
- **`core/project_archive.py`** — soft-delete → 7-day archive → restore/purge (+ `archive-registry.json`).
- **Control channel** — `control.json` now also carries `{"agents": {"<id>": "pause|resume|stop|cancel"}}` (per-agent control).
- **Capacity** — `core/capacity.py` gained `effective_limits/can_add_context/can_start_context` (tier/tenant aware).

## Stop/gate semantics
- **`max_duration_per_stage`** measures the **current stage** elapsed time and **excludes human-wait** (interactive/approval) (BI-0072).
- Approval/gate waits honor **`PIPELINE_PROMPT_TIMEOUT`** (0 = wait indefinitely) (BI-0074).
- A prompt that times out is recorded as **`timed_out`**, never silently "answered" (BI-0048).
