# Orchestration — Roles, Stages, E2E (control plane vs judgment plane)

Two planes; only the control plane is always on.

| Plane | Component | LLM? | Runs |
|---|---|---|---|
| **Control (runtime)** | `PipelineExecutor` (+ `stage_runner`, `dag_executor`, compliance, gates, budget, VCS, checkpoints) | **No** | **always** |
| **Judgment** | `orchestrator` agent (`agents/orchestrator.agent.json`) | **Yes** | only where judgment is needed (fixed stages + events) |

Control plane = the real coordinator (scheduling, deps, retries, gates, status, re-runs).
Judgment plane = a consultant invoked at ambiguity/judgment points.

---

## 1. E2E stage table

Legend — **C:** control-plane actions (every stage) · **J:** judgment-plane (LLM orchestrator) · **G:** gate/HIL

| Stage / Phase | Flow (agents) | C: runtime orchestrator | J: LLM orchestrator / coordinator | G: gate / HIL |
|---|---|---|---|---|
| **0 Ideation** | ideation | schedule, budget, compliance, checkpoint, banner | — | — |
| **0a Discovery** | discovery | same | — | — |
| **1 Design** | design | same | — | `AG-scope-change` approval |
| **1a Product Design Spec** | product-design-spec | same | — | — |
| **1b Design Review** | design_critic | same | — | — |
| **1c UX/IA Review** | ux-ia | same | — | — |
| **1d Research** | researcher | same | — | — |
| **2 Architect** | architect | same + **diagram/sizing/targets** emit | — | `AG-architecture` approval |
| **3 Refine Requirements** | **orchestrator** | same | **YES** — turn design/arch into implementable, prioritized, testable requirements; resolve ambiguity; set acceptance criteria & phasing | — |
| **3a QA Spec Review** | validate | gate: review all specs; **blocking→block **4-0** | — | **HIL** on optional findings/waivers |
| **4-0 Skeleton** | implement, devops | branch (VCS), schedule, budget | — | — |
| **4a–4f Iterations** | implement(+db/api/logic/ui), devops(build), code-review, validate | per-iteration: build (version+`build.N`), test cycle, defects, compliance retry, merge→`develop`, WIP | — (only on events, §2) | reviewer (fix) |
| **4x-vqa Visual QA** | visual_qa | app up→tests→down; defects | — | — |
| **5 Security Scan** | security | schedule; CVE/secrets; defect routing | — | — |
| **6 NFR Tests** | validate | NFR cycle; coverage; insights | — | — |
| **7 Full Test Suite** | validate | full cycle; coverage; QIR data | — | — |
| **8 Document** | document | schedule; required docs (INSTALL/USER/API) | — | — |
| **9 Package** | package | packaging/install/BOM/footprint | — | — |
| **10 Pre-Production** | devops, **orchestrator** | schedule; env prep | **YES** — readiness consolidation, cross-stage reconciliation, hand-off decisions, risk flags | — |
| **10a QA Go/No-Go** | validate | **QIR + Go/No-Go matrix**; NO-GO blocks deploy | — (input consumed) | **HIL** (`qa.override_gonogo`) |
| **11 Deploy** | devops, production-deploy | provider select (docker/k8s/vmware/…), apply→verify→destroy, RC **tag**, smoke | — | **HIL** release (develop→main; release **tag**) |
| **12 Exit** | **orchestrator** | finalize, final report, `pipeline_complete`, manifest, snapshot | **YES** — wrap-up/exit coordination (role loosely defined) | — |
| **LIVE / ops (post-11)** | *(none wired)* | — | *(none)* | **TODO** — see §3 |

Runtime C-actions applied at **every** stage: dependency check, budget check, model routing, compliance suite (+retry), circuit breakers, live status (`agents-live.json`), checkpoint/resume, invalidate-downstream on rerun, audit + banner.

## 2. Judgment plane — event-driven invocations (target)
Not tied to a stage; invoked when rules can't decide (bounded + logged):

| Event | Triggered by | Orchestrator decides |
|---|---|---|
| `stuck` | no progress / repeated no-op loops | change strategy / re-scope / escalate |
| `anomaly` | stage duration ≫ avg, token spikes | reroute model/agent, split work |
| `compliance_exhausted` | retries hit cap | rethink, reassign, or HIL |
| `agent_conflict` | two agents disagree (e.g., review vs fix) | arbitrate, pick owner, escalate |
| `coverage_gap` | FR/NFR or category coverage missing | add tests/agents, extend scope |
| `scope_change` | user/feature change | re-plan phases/iterations |
| `escalation` | HIL/HITL request | summarize options for human |

## 3. Gaps / what needs to be done (review)
1. **Rewrite the orchestrator agent spec** — it still says *“Global Orchestrator … single source of truth for pipeline execution”* (stale; the runtime is the SSOT). Re-role it as **“Coordinator (judgment plane)”** with explicit inputs/outputs/limits.
2. **Remove dead `on_complete: "orchestrator"` labels** in `pipeline-definition.json` (no code executes them) — or make the runtime honor them as routing.
3. **Implement event-driven judgment invocation** (§2) — currently anomalies/stuck are detected/logged but not routed to the orchestrator.
4. **Define Stage 12 (Exit) orchestrator output** — what artifact/decisions it must produce.
5. **Add a LIVE/OPS phase after Deploy (11)** — post-deploy monitoring, SLO/error-budget, incident + maintenance loops (agents exist: `post-production`, `guardian`, `observer`, `maintenance`, `finops`), rollback policy. Currently nothing runs after `11` except `12 Exit`.
6. **Review Stage 6 dependency** — NFR Tests depends on `4c-vqa` (looks like it should be `4f-vqa`).
7. **Explicit orchestrator audit** — log an “orchestrator (runtime) routed/invoked …” line per decision (some exist; make consistent).
8. **Document** this file + link from README/`ENTRYPOINTS.md`.

## 4. Review questions
- Keep the LLM orchestrator at **3, 10, 12**, or make it purely **event-driven** (and drop from 10/12)?
- For LIVE/OPS: separate **Stage 13** (`13 Monitor`, `13a Incident`, `13b Maintenance`) or a detached supervisor loop?
- Should `on_complete` become real routing, or be removed?
