# DOGFOOD / E2E product-generation — design (Phase 1–3)

**One-line restatement:** add an **API-first, auto-mode dogfood** that drives a real product generation
(idea → all stages/agents → stakeholder/HIL → delivery) with per-stage observability, plus a deterministic
**replay** variant for CI and a **scheduled** cadence — composing existing owners only (no new engine/store).

## RECONCILIATION (binding, before implementation)

```
PRIOR DECISIONS
- Single submission path: only sanctioned entries run the pipeline. scripts/dev/single_path_check.py:26-28
  (_ALLOW = {core/pipeline_executor.py, scripts/run_pipeline.py}); core/run_entry.py:12 ("execute_pipeline()
  refuses to run unless a lock is held, so no path can bypass this").
- One writer per concern; no duplicate engines/stores. AGENTS.md; config/store-registry.json.
- Worker path is product_forge-only (BI-PF-0427); product generation uses job_manager + executor (not workers).
- OpenCode is an adapter, not a dependency; API-first (dashboard consumes API only). AGENTS.md.
- Reconciliation-before-implementation + IMPACT REVIEW + RCCA-per-defect are binding. AGENTS.md:62-111.

EXISTING PATH
- Start a run: api/routers/runs.py (POST /runs/start -> run_entry.enqueue / run_now_on_priority);
  api/routers/intake.py (POST /intake -> run_entry). core/run_entry.py:116 enqueue.
- Execute: supervisor core/portfolio.py:311 (run_supervisor) launches scripts/run_pipeline.py
  (main :82; PipelineExecutor :317; begin_run :436; execute_pipeline :454). Flags: --idea/--tier/--auto (:198).
- Auto/HIL stakeholder: agents/human.agent.json (aliases hil/stakeholder/human-proxy); --auto sets
  auto_mode+auto_approve (scripts/run_pipeline.py:198-209). PIDL defaults allow autonomy
  (config/pidl-profile.json).
- Model tier: config/model-tier.json:1543 ("kctier"; active_tier kctier).
- Observability: products/<p>/pipeline-run.log (scripts/run_pipeline.py:67-79); canonical events.jsonl
  (core/events.py TYPES: run_/stage_/agent_*). Store registry: validation-runs.json owner validation_engine
  (config/store-registry.json:417).
- LLM seam: core/orchestrator/llm_client.py:48 (LLMClient; _call_llm_single :305); cache core/storage.py:128.
- Delivery: core/delivery.py, core/close_loop.py; product remote opt-in via git-config.json (core/vcs.py:33).

ASSUMPTIONS  (each needs explicit user yes/no)
A1. Dogfood targets a GENERATED product (scope=project), not product_forge itself.
A2. Auto-approve (PIDL/Human Proxy) is acceptable for dogfood runs (no human gate).
A3. Reusing validation-runs.json (owner validation_engine) for dogfood results is the right store.
A4. Product delivery may be local-only when no product remote is configured (asserted, not required).
A5. Caps: a per-run token/cost + wall-clock cap is desired.

DIVERGENCES
- New API surface (POST /dogfood/run, GET /dogfood/runs/{id}) — a NEW PATH; requires explicit approval.
- Phase 2 adds a record/replay mode to core/orchestrator/llm_client.py (extend the owner; not a new engine).

OPEN QUESTIONS
Q1. Endpoint shape: new POST /dogfood/run vs extend POST /intake with {idea,tier,auto,caps}?
Q2. Confirm A1–A5 above.
Q3. Caps values (tokens/minutes) and default tier = kctier?
Q4. Should nightly (Phase 3) also run a RELEASE-profile qualification, or DOGFOOD only?
```

## IMPACT REVIEW

| claim | verdict | evidence (file:line) | recommendation |
|---|---|---|---|
| Dogfood should go through the canonical run path, not the executor bypass | aligned | scripts/dev/single_path_check.py:26-28; core/run_entry.py:12 | use run_entry.enqueue + scripts/run_pipeline.py |
| New `POST /dogfood/run` (idea+auto+tier+caps → run_id) | new-path | api/routers/runs.py (start), intake.py | **needs explicit approval**; compose run_entry, no new engine |
| New `GET /dogfood/runs/{id}` status aggregation | new-path | api/routers/runs.py, events.py, artifacts.py | **needs explicit approval**; read-model over existing stores |
| Reuse `validation-runs.json` for dogfood results | aligned | config/store-registry.json:417; core/validation_engine.py | reuse owner; no new store |
| Auto mode + stakeholder via Human Proxy | aligned | agents/human.agent.json; scripts/run_pipeline.py:198-209 | reuse; no change |
| Tier `kctier` | aligned | config/model-tier.json:1543 | reuse |
| Per-stage logs/events | aligned | core/events.py; scripts/run_pipeline.py:67-79 | expose via read API only |
| Phase 2 replay seam | aligned | core/orchestrator/llm_client.py:48,305; core/storage.py:128 | extend LLM owner (record/replay); no new engine |
| Delivery assertions | aligned | core/delivery.py, core/close_loop.py, core/vcs.py:33 | assert repo/branch/tests/close_loop; fail-closed |
| Supervisor prerequisite | aligned | core/portfolio.py:311 | document/start; no "worker" |
| No new store/engine | aligned | AGENTS.md; store-registry | composition only |

## Functionality summary
- **Adds:** an on-demand, auto-mode, API-driven dogfood for generated products; a status/observability read API;
  delivery assertions; a deterministic replay variant for CI; a scheduled cadence with trend/alert.
- **Does not add:** a new engine, store, or worker; does not bypass the single submission path.
- **Reuses:** run_entry, job_manager, scripts/run_pipeline.py, portfolio supervisor, Human Proxy/PIDL, model tiers,
  events/logs, validation_engine + validation-runs.json, delivery/close_loop, LLM client.

## Phased backlog (recorded BEFORE coding)
- Phase 0 (done): hermetic lifecycle PR gate.
- Phase 1: `POST /dogfood/run` + `GET /dogfood/runs/{id}` + delivery assertions (parent epic: BI-0220).
- Phase 2: replay seam in core/orchestrator/llm_client.py + cassette store + CI gate.
- Phase 3: scheduled live dogfood + trends/gating.
