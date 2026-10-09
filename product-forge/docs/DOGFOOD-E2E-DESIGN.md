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

---

# Phase 2 design (BI-PF-0459) — deterministic LLM replay

## RECONCILIATION (binding)
```
PRIOR DECISIONS
- GENERATION OUTPUT is never served from a cache; caching is INPUT-side only
  (core/orchestrator/storage.py:13-17). Replay is a TEST mode, default OFF; it must not weaken this.
- One writer per concern; extend the cache owner, do not add a store (AGENTS.md).
- Single LLM owner: core/orchestrator/llm_client.py (extract_llm_client.py 1A.11).
- New env switches register in config/env-flags.json (core/env_flags.py).

EXISTING PATH
- HTTP seam: core/orchestrator/llm_client.py:400 requests.post(api_endpoint, json=data, headers=headers, timeout=180).
- Cache owner: core/orchestrator/storage.py (LLMCache .llm-cache :128; InputCache .input-cache :165;
  flags no_cache/output_cache_allowed/input_cache_enabled :24-39).
- Env flag registry: config/env-flags.json ("flags" dict; owner field).
- CI: scripts/dev/precheck.py gates; --full runs the deep tier.

ASSUMPTIONS (need explicit yes/no)
A1. Replay is TEST-ONLY, default OFF; never used in production runs.
A2. Cassettes are project-scoped (products/<p>/.llm-cassettes), like .llm-cache (no store-registry entry).
A3. A replay MISS is FAIL-CLOSED (error), never a silent network call.
A4. Phase 2 includes an executor-level replay test for a MINIMAL scope (stage 0) with a committed cassette.

DIVERGENCES
- New env flag PIPELINE_LLM_REPLAY (off|record|replay) - add to the registry.
- Interception at llm_client.py:400 via a helper - extend the owner (not a new engine).

OPEN QUESTIONS
Q1. Flag name/values: PIPELINE_LLM_REPLAY = off|record|replay?
Q2. Cassette dir: products/<p>/.llm-cassettes?
Q3. CI gate scope: minimal stage-0 executor-replay, or full pipeline?
```

## IMPACT REVIEW
| claim | verdict | evidence (file:line) | recommendation |
|---|---|---|---|
| Record/replay seam at the single HTTP call | aligned | core/orchestrator/llm_client.py:400 | intercept via `_http_post` helper; default off |
| Extend the cache owner (no new store) | aligned | core/orchestrator/storage.py:128-238 | add `LLMReplay` to storage.py |
| Project-scoped cassettes | aligned | `.llm-cache` pattern storage.py:132 | products/<p>/.llm-cassettes |
| New env flag registered | aligned | config/env-flags.json; core/env_flags.py | register `PIPELINE_LLM_REPLAY` |
| Replay miss fails closed | aligned | EOS fail-closed | error, never network |
| CI dogfood-replay gate | aligned | scripts/dev/precheck.py gates | `scripts/dev/dogfood_replay_check.py` (deep) |
| Executor-level replay (minimal scope) | aligned | core/pipeline_executor.py execute_pipeline | stage-0 scope for determinism |

## Functionality summary
Adds a deterministic, network-free LLM **replay** mode (record once, replay in CI) so the integration dogfood
can run in CI. Extends the cache owner (`storage.py`) + the LLM client; adds one env flag + one gate.
No new engine/store; default **off** (production unaffected).

---

# Phase 3 design (BI-PF-0460) — scheduled live dogfood + trends/regression (API-first)

## RECONCILIATION (binding)
```
PRIOR DECISIONS
- One writer per concern; a NEW concern registers in config/store-registry.json (AGENTS.md).
- API-first; the legacy dashboard is FROZEN (do not reference dashboard/ anywhere).
- Product generation via run_entry/job_manager + executor (not the worker plane); single submission path.
- Reconciliation + IMPACT REVIEW + RCCA-per-defect are binding.

EXISTING PATH
- No cron/daemon in-repo. job_manager supports a one-shot due time: not_before -> state "scheduled"
  (core/job_manager.py:96-112,144). core/scheduler.py is backlog eligibility, not a clock.
- Long-running loop: core/portfolio.py:311 run_supervisor (poll) - a possible cadence host.
- Phase 1 API: api/routers/dogfood.py (POST /dogfood/run, GET /dogfood/runs/{id}); core/dogfood_run.py.
- Results store: validation-runs.json owner core/validation_engine (store-registry.json:417).
- store-registry config shape: {owner, kind:"config", scope:"global", concern, visibility}.

ASSUMPTIONS (need explicit yes/no)
A1. Cadence is provided by an operator/cron calling POST /dogfood/schedule/tick (NO in-repo daemon).
A2. Schedule lives in a NEW global config store config/dogfood-schedule.json (owner core/dogfood_schedule.py), registered.
A3. Trends/regression are a READ API over the existing validation-runs.json (no new store).
A4. No dashboard reference; API-first only (a future client consumes the API).

DIVERGENCES
- NEW config store + owner module + 2 API endpoints (/dogfood/schedule/tick, /dogfood/trends) = NEW PATH.
- Optionally hooking portfolio.run_supervisor to call the tick would COUPLE the scheduler loop - avoid.

OPEN QUESTIONS
Q1. Cadence trigger: external cron -> tick API (recommended) vs supervisor hook vs both?
Q2. Schedule store: global config/dogfood-schedule.json vs per-project project.json?
Q3. Regression definition: latest non-PASS following a PASS = regression?
```

## IMPACT REVIEW
| claim | verdict | evidence (file:line) | recommendation |
|---|---|---|---|
| Cadence via tick API (no daemon) | new-path | job_manager.py:96-112; no cron | needs approval |
| New config store dogfood-schedule.json | new-path | store-registry config shape :389-395 | register + single writer (core/dogfood_schedule.py) |
| Trends read over validation-runs.json | aligned | store-registry.json:417 | read-only; no new store |
| New endpoints /dogfood/schedule/tick + /dogfood/trends | new-path | api/routers/dogfood.py | needs approval |
| Supervisor hook for cadence | derails | core/portfolio.py:311 | avoid coupling; prefer external tick |
| No legacy-dashboard reference | aligned | legacy frozen (AGENTS.md) | API-first only |

## Functionality summary
Adds an API-first cadence + observability for dogfood: a schedule config + `core/dogfood_schedule.py` (single
writer) exposing a `tick` (enqueue due dogfood runs, idempotent per period) and a read-only `trends`/
regression API over the existing `validation-runs.json`. No daemon, no dashboard reference, no new results store.


