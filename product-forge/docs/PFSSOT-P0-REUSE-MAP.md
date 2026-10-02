# PFSSOT-P0 — Reuse Map (Phase 0 Gate)

**Item:** BI-PF-0361 (epic BI-PF-0360) · **Source doc:** `docs/PF-Backlog-SSOT-Scheduler-Pluggable-Workers-updated.md`
**Purpose:** inventory what exists before extending the backlog into an execution SSOT + pluggable worker
scheduler. **No implementation begins until this map exists** (doc §39 Phase 0 gate).

Legend: **[E]** exists · **[P]** partial · **[X]** missing.

## 1. Requirement → reuse map

| Requirement | Existing implementation | Extension point | Required change | New code? |
|---|---|---|---|---|
| Backlog SSOT (ids/lifecycle/deps/priority/single-writer) | `core/backlog.py` (`_paths`, `_lock`, `add_epic`, `update`, `set_status`, indexes, history); registry `config/store-registry.json` | `add_epic`/`update` fields | add fields additively | No |
| Backlog analysis/grooming fields | **missing** (item keys: `id,tag,type,scope,project,origin,external_id,label,title,body,source,status,priority,moscow,value,effort,risk,deps,links,decisions,follow_up,created_at,updated_at,score`) | item dict | add `analysis{}`, `revision`, `priority_rank`, structured deps | Yes |
| Priority ordering | `priority` (often null), `moscow`, `score`; `list_open` order | item | add deterministic `priority_rank` | Yes |
| Dependencies | `deps[]` (flat ids) | item | typed deps (`BLOCKS/REQUIRES/RELATED`+`required_state`), `blocked_by`, `unlocks` | Yes |
| Scheduler primitives | `core/job_manager.py` (`enqueue`; `claim` = `BEGIN IMMEDIATE`; `finish`; priority; resume; `item_ids`) | `job_manager` | add lease/heartbeat/registry; read backlog deps at claim | Yes |
| Pure planner | `core/scheduler.py` (`plan`, `dependency_graph`, `capability_match`, `path_overlap`) | `scheduler` | eligibility over canonical backlog | Yes |
| Canonical enqueue | `core/run_entry.enqueue` → `job_manager.enqueue` | reuse | none | No |
| Worker execution | `core/worker.py` (`WorkerResult`, `run_task`, providers, isolated worktree, `record_result`, `run_totals`) | `worker` | registry/lifecycle/heartbeat/assignment | Yes |
| GitHub/PR/evidence | `core/github.py` (`build_evidence`, `record_pr`, `create_pr`, `ci_status`); `core/merge_gate.py`; `core/pr_gate.py` | reuse | auto-invoke on completion | Partial |
| Delivery write-back | `core/backlog.set_delivery` **exists, 0 callers** | `set_delivery` | wire a completion/merge hook | Yes |
| Task contract | `core/task_contract.py` (`FIELDS`, `create`, `set_status`, `set_metrics`) | `epic_id`/`feature_id` (soft) | bidirectional validated link | Yes |
| API surface | `api/routers/{backlog,engineering,workers,runs,validation,...}.py`; envelope+auth conventions | routers | add scheduler/registry/assignment endpoints | Yes |
| Queue substrate | `job_manager` on `data/portfolio/portfolio.db`; capacity `config/capacity.json` | `job_manager`+`capacity` | worker-scoped slots | Partial |
| OpenCode adapter | `core/worker.py:OpenCodeProvider`; `.opencode/command/pipeline.md` | adapter | keep optional; `/pf` surface | Partial (surface) |
| PIDL substrate | `learnings.py`, `persona.py`, `agent_memory.py`, `memory_api.py`, `human_proxy.py`, `execution_contract.py` | compose | resolver+engine (no new store) | Yes |

## 2. Confirmed single-path status (doc §43(c))

- ✅ **Fixed:** `core/intent_router._start_pipeline` enqueues via `core.run_entry` → `job_manager` (no direct executor).
- ⚠️ **Not fully closed (Phase 8A gate):**
  1. `core/backlog.accept(when="now")` → `core.portfolio.enqueue` (legacy) — bypasses `run_entry`.
  2. **Two claimers on one DB:** `core/portfolio.py` (`enqueue`/`claim`/`finish`, `BEGIN IMMEDIATE`) duplicates `core/job_manager.py`.
  3. `core/enhance.py` constructs an executor and calls `execute_pipeline()` without `begin_run` (blocked only by the guard).
  4. `scripts/run_pipeline.py` run directly (CLI) executes without a pre-existing JobManager job.

## 3. Missing capabilities

- Backlog: `analysis{}`, `revision`, `priority_rank`, structured deps, readiness, grooming state, `analyze_mode`.
- Scheduler: worker-scoped **leases** (`lease_id`/expiry/renew/recover), heartbeat, **worker registry**, claim-time backlog dep/capability/revision validation, unified priority scale.
- Worker: registry/registration protocol, scheduler-owned lifecycle, heartbeat/stale, assignment records, revocation.
- Execution path: enforce submit-before-execute; retire the duplicate `portfolio` claimer; mirror job outcome → backlog.
- Delivery/evidence: auto `set_delivery` on completion/merge; auto `github.build_evidence`/`record_pr`; revision bump.
- API: `scheduler get_next_work/claim/release`, `workers register/heartbeat/capabilities/unregister`, `assignments renew/complete/fail/recover`.
- PIDL: resolver + engine + decision contract + versioned traceability.

## 4. Second-store / second-engine risks (do NOT create)

1. **Two claimers** — `portfolio.claim` vs `job_manager.claim` (same DB). Extend `job_manager`; retire the legacy fallback.
2. **Two work stores** — `items/<ID>.json` vs `tasks/task-contracts.json`. Reference by id; never a second backlog.
3. **Result/metrics stores** — `worker-results.json`, `task_contract.metrics`, `agent_ledger`. Extend one; no fourth.
4. **Three "worker" notions** — static `config/engineering-workers.json`, `job_manager.jobs.worker`, `worker.py` providers. Reconcile, don't add a fourth.
5. **Reservations TTL ≠ worker lease** — path-scoped; don't reuse as assignment lease.
6. **Decision fragmentation** — `backlog.decisions[]`, `.conversations/decisions.json`, `agent_memory.DECISION`, `pr_gate` overrides. PIDL composes.
7. **Gate duplication** — `pr_gate` / `merge_gate` / `validation_engine` / `run_quality_gate`. Reuse; no fourth gate.
8. **Capacity slot ambiguity** — global `max_parallel_projects` vs worker concurrency. Define one authority first.

## 5. P0 gate result

Reuse map **complete**. Backlog/job_manager/run_entry/worker/github/pr_gate/merge_gate/validation_engine are the
correct extension points; no architectural rewrite required. Two defects found (§2.1/§2.2 residual bypass +
duplicate claimer) are raised as issues and tracked. **Proceed to P1 (backlog fields) after issue fixes.**
