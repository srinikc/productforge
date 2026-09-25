# Two-Tier Orchestration — Portfolio (global) vs Project (per project)
Review from standards + systems research, and a concrete design.

## 1. Verdict
The idea is **correct and standard**: one **global/portfolio** layer managing *many*
projects, and one **project** layer managing *each* product end-to-end. It matches
both management standards and distributed-systems control patterns.

## 2. Standards mapping
| Standard | Global tier | Middle tier | Local tier | Notes |
|---|---|---|---|---|
| **PMI / PMBOK 7** | **Portfolio** (strategy alignment, prioritization, capacity, benefits realization) | **Program** (related projects, shared resources, interdependencies) | **Project** (deliver product within scope/cost/time) | Portfolio ≠ program ≠ project; distinct goals/owners |
| **PRINCE2** | Programme management | — | Project management (stage boundaries, **manage by exception**, tolerances) | Tolerances → our gates/HIL; stage boundaries → our stages |
| **SAFe** | Lean Portfolio Mgmt (LPM: funding, epics, guardrails) | Agile Release Train / Program (PI planning, shared capacity) | Team/ART execution | Program layer coordinates shared cadence |
| **ISO 21500 / 21502** | Portfolio guidance | Programme guidance | Project guidance | Formal separation of governance levels |
| **Governance (OPM3/PMO)** | Prioritize, gate, standardize, report rollups | Cross-project deps | Deliver, report | PMO = policy + portfolio rollup |

## 3. Systems / multi-agent research mapping
| Pattern | Global | Project |
|---|---|---|
| **Kubernetes** | **Control plane** (desired state, scheduling, policy) | Per-controller **reconcile loop** (per workload) |
| **Temporal / Argo / Airflow** | Cluster/scheduler | Workflow/DAG **run** (one execution) |
| **CI/CD** | Orchestrator/portfolio queue | **Pipeline run** (one branch/PR) |
| **Anthropic multi-agent (orchestrator–worker)** | Lead/orchestrator allocating subagents | Worker agents | 
| **LangGraph "supervisor"** | Supervisor routing | Sub-graphs |
| **Contract-Net / Blackboard** | Task announcement & allocation | Bidders/participants |
| **Reconciler principle** | Declare desired state | Drive actual→desired, emit events |

**Conclusion:** a **two-tier controller hierarchy** (with a possible program tier
in between) is the established pattern. Naming "orchestrator" for both tiers causes
confusion — call them **Portfolio Manager** (global) and **Project Manager/Controller** (per project).

## 4. Proposed model (2 tiers + shared services)
### Tier 1 — Portfolio/Program Orchestrator (GLOBAL)
- **Registry**: all projects, owners, targets, tiers.
- **Prioritization & scheduling**: which project/stage runs when; fairness, SLA/deadline.
- **Capacity governance**: shared **budget pool**, model **rate limits**, concurrency slots.
- **Policy & standards**: gates, naming, security, compliance, model/tier policy.
- **Cross-project concerns**: shared components/APIs, dependencies, blast radius.
- **Shared knowledge**: skills, model registry, patterns, learnings (cross-project).
- **Rollups & reporting**: portfolio RAG, aggregate QIR/Go-No-Go, risk register.
- **Governance/HIL**: funding/approvals, escalation, stop/pause across projects.

### Tier 2 — Project Orchestrator / Project Manager (PER PROJECT)
- Owns **scope/plan/features/phasing**, stages `0→12`, gates (`3a`,`10a`), risks, resources,
  iterations, feature branches, versioning, builds, defects, QIR/Go-No-Go, delivery report.
- **Control plane** = `PipelineExecutor` (deterministic).
- **Judgment plane** = LLM **Coordinator** (context-pack-driven, event-driven).

### Shared control-plane services (used by both tiers)
VCS manager (per repo) · build/version registry · test framework (QA console) · artifact
registry · **budget/rate governor** · **event bus** · notifications · secrets/vault.

## 5. Contract between tiers
- **Portfolio → Project**: priority, budget/quota, deadline, policy, shared components, target env.
- **Project → Portfolio**: status/RAG, QIR, Go/No-Go, risks, resource needs, blockers, releases.
(Events on an **event bus**; both tiers reconcile toward declared desired state.)

## 6. Where the LLM judgment sits
- **Project Coordinator (LLM)**: requirements refinement, pre-prod readiness, conflict
  arbitration, stuck/anomaly strategy, coverage-gap remediation, scope re-planning,
  model re-route, incident triage — **with a context pack**, bounded, logged, HIL-escalate.
- **Portfolio Advisor (LLM, optional/bounded)**: prioritization tradeoffs, risk/benefit,
  cross-project conflict mediation, resource reallocation advice — deterministic math does
  the scheduling; the LLM advises.
- Keep **all mechanical work deterministic** (branching, commits, versioning, tags, merges,
  budgets, scheduling).

## 7. Tradeoffs / risks
- **Contention**: multiple projects compete for models/rate limits/budget → needs a governor
  (fair-share, quotas, backpressure).
- **Coupling**: shared components/APIs create cross-project blockers → dependency graph + policy.
- **Fairness/starvation**: priority scheme + aging.
- **Blast radius**: one project’s failure must not stall the portfolio (isolation, circuit breakers).
- **Tenancy/isolation**: repos, secrets, artifacts per project; shared nothing by default.
- **Governance**: who approves portfolio changes; audit across tiers.
- **Observability**: per-project + portfolio dashboards; correlation IDs across both tiers.

## 8. Mapping to our codebase (what changes)
- Keep `PipelineExecutor` = **Project Controller** (rename conceptually; behavior unchanged).
- Add:
  - `core/portfolio.py` — project registry, priority/queue, capacity (budget + rate governor),
    cross-project deps, rollups.
  - `core/event_bus.py` — events between tiers (`project.completed`, `budget.exhausted`, `blocked`, …).
  - `core/orchestration_context.py` — context pack for the LLM Coordinator.
  - `core/event_router.py` — event → LLM Coordinator → decision | HIL.
  - `scripts/run_portfolio.py` — global entry (schedule N projects); `run_pipeline.py` stays per-project.
- Agent: rewrite `orchestrator` → **Coordinator (judgment plane)**; add optional **Portfolio Advisor**.
- Dashboards: **portfolio view** (all projects/RAG) + **project view**; shared services panel.

## 9. Build order (recommended)
1. **Event bus + context pack + Coordinator re-role** (project judgment plane).
2. **Event router** (stuck/anomaly/conflict/coverage/compliance) → Coordinator/HIL.
3. **Portfolio tier**: registry + scheduler + capacity/budget/rate governor + event bus consume.
4. **Rollups**: portfolio RAG (aggregate QIR/Go-No-Go), portfolio dashboard.
5. **LIVE/OPS phase** per project (monitoring/SLO/incident/maintenance) + portfolio ops view.
6. Remove dead `on_complete` labels; consistent orchestrator audit/events.

## 10. Answers to "does this make sense?"
**Yes.** It's the portfolio/program/project separation (PMBOK, PRINCE2, SAFe, ISO 21500)
implemented as a two-tier controller hierarchy (Kubernetes control plane vs reconcilers;
Temporal/Airflow scheduler vs run). Recommended names to avoid overload:
**Portfolio Manager (global)** and **Project Manager/Controller (per project)**, with the
LLM **Coordinator** as the project-level judgment plane (and an optional Portfolio Advisor).

## 11. Concurrency model — current vs target + background mapping

### 11.1 Current reality (as-is)
- One project = one folder (`products/<project>/`) = one `run_pipeline.py` process
  (one `PipelineExecutor`).
- Two projects = **two independent instances** (separate sessions). No process runs two projects.
- Concurrency is **cross-process**; `LockManager` locks **per project** (`products/.locks`),
  so different projects can run simultaneously — but there is **no global governor**
  (budget/rate-limit/scheduling across projects is uncoordinated).

### 11.2 Target
Portfolio Manager **coordinates N project controllers/workers** (like k8s control plane
vs pods, or Airflow scheduler vs task runs). It does NOT require a single process to host
all projects: each project stays isolated; the portfolio schedules, governs, and rolls up.

### 11.3 Background mapping (required for dashboard-driven multi-project)
| Map | Key → Value |
|---|---|
| `portfolio-registry.json` | project → {owner, priority, quota, target, tier, path} |
| `portfolio-state.json` | project → {run_id, pid/worker, status(RAG), current_stage, lock, started_at} |
| `runs/<run_id>.json` | run → {project, stages, budget_used, events, artifacts, logs_path} |
| `event bus` | `project.started/completed/blocked/budget.exhausted` (both tiers subscribe) |
| locks | per project (`products/.locks`) + **portfolio concurrency slots** |
| capacity governor | global budget pool + per-provider token/rate budget + slots |
| correlation id | one per run; propagated to logs/audit/artifacts/dashboards |

### 11.4 Dashboard implications
Create project → enqueue → portfolio schedules → project run (worker) → events →
portfolio rollup. Console shows a **portfolio view** (all projects, RAG, budget, queue)
drilling into a **project view** (stages/agents/QA/delivery) — same APIs either way.

### 11.5 Phases to get there
1. Event bus + run records + correlation ids (per project).
2. Portfolio registry + `run_portfolio.py` (queue, slots, priority).
3. Capacity governor (shared budget + provider rate limits).
4. Dashboard portfolio view + create/start/stop APIs.
5. Cross-project dashboard rollups (portfolio RAG/QIR).

## 12. Substrate, decisions, naming, compatibility

### 12.1 "Substrate" (plain term)
- **Model** = the org chart (portfolio → project → agents). Fixed.
- **Substrate** = *where the work runs* (this machine / worker pool / k8s / CI). Swappable.
- Two separate axes — do not conflate:
  - **Orchestration substrate** = where the *pipeline/agents* run.
  - **Deployment target** = where the *built product* goes (`deploy_providers`/`target_advisor`).

### 12.2 Decision: A and B now (local); C/D later (cloud)
| | Substrate | Where | Status |
|---|---|---|---|
| **A** | supervisor + child processes (files) | this machine | ✅ implementing now |
| **B** | queue + worker pool (sqlite/db) | this machine (more robust) | ✅ implementing now |
| C | k8s Jobs/Pods + reconciler | cloud, elastic | deferred (optional) |
| D | CI / serverless + webhooks | cloud | deferred (optional) |

A and B are **alternatives on the same machine** (not both required): A = simple; B = queue/workers (higher churn, cleaner retries). C/D are cloud evolutions. The **API contract is identical** across all — the dashboard/UI never changes.

### 12.3 Naming (global vs project) — keep terms consistent
| Term | Scope | Component / file | Notes |
|---|---|---|---|
| **Portfolio Manager / Supervisor** | **GLOBAL** | `core/portfolio.py`, `scripts/run_portfolio.py` | one per machine/portfolio universe; queue, slots, rollups |
| **Project Controller** | project | `PipelineExecutor` (`core/pipeline_executor.py`) | deterministic control plane; **id/class unchanged** |
| **Coordinator** (LLM) | project | the `orchestrator` **agent** | judgment plane; **agent id `orchestrator` kept** as alias |
| **orchestrator** | (legacy name) | aliases → Coordinator | kept as alias to avoid breakage |

### 12.4 What happens to the "orchestrator" entity
- **Runtime orchestrator** → renamed conceptually to **Project Controller** (`PipelineExecutor`); **no code rename needed**, behavior unchanged.
- **LLM orchestrator agent** → **re-roled** as **Coordinator (judgment plane)**; the **agent id stays `orchestrator`** (alias) so routing, budgets, tiers, `.opencode/agent/orchestrator.md`, `pipeline-definition.json` flows (`3`,`10`,`12`) keep working. Add `aliases: ["coordinator"]`.
- So: *one entity, two avatars* — **Controller** (deterministic, always) and **Coordinator** (LLM, event-driven/stages 3/10/12).

### 12.5 Compatibility (does anything break?)
**No breakage.** The portfolio layer is **additive** and wraps the existing runner:
- `scripts/run_pipeline.py` — unchanged entry (kept: flags, `new/continue`, banner, `pipeline-run.log`).
- Agents & `pipeline-definition.json` — unchanged (Coordinator keeps id `orchestrator`).
- Test framework / QA / VCS / build — unchanged; per-project as today.
- New: `run_portfolio.py` (A/B), `core/portfolio.py`; future: `core/event_bus.py`, `core/orchestration_context.py`, `core/event_router.py`.
Only **soft/optional** changes: re-role the `orchestrator` agent text; add `coordinator` alias; remove dead `on_complete` labels.

### 12.6 Capacity governor (B prerequisite at scale)
Shared budget pool + per-provider token/rate budgets + concurrency slots; prevents cross-project 429s/spend overruns. Highest-value scale item.
