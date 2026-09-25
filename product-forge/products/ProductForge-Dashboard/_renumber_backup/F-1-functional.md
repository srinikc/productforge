## F-1: Central Pipeline Control Plane

**Feature ID:** F-1
**Feature Name:** Central Pipeline Control Plane
**Summary:** The single authoritative surface through which an operator creates, configures, starts, observes, modifies, and governs every Product Forge pipeline project and portfolio. It owns the registry of modules, workflows, stages, HIL gates, agents/leads, stores, model tiers, and run state, and is the only component permitted to mutate run execution state.
**Users:** Product Forge Operator (primary), HIL Approver/Reviewer, Portfolio Owner, Platform Admin, Auditor.

---

### Requirements

#### Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| FR-1 | Project lifecycle registry | Create, read, list, update, archive, restore, and permanently delete pipeline projects. Every project carries name, description, owner, portfolio membership, status, pipeline binding, and configuration revision. |
| FR-2 | Portfolio grouping and roll-up | Create and manage portfolios; assign/unassign projects; present aggregate state across member projects (run counts by status, gate backlog, failure counts, last activity). |
| FR-3 | Pipeline definition and version pinning | Register pipeline definitions composed of ordered stages; pin each project to an immutable pipeline version; allow explicit upgrade to a newer version without mutating historical runs. |
| FR-4 | Run execution control | Start, pause, resume, cancel, and retry pipeline runs. Control commands apply to the whole run or to a specified stage, and are recorded as auditable commands. |
| FR-5 | Stage orchestration | Drive runs through the registered 32-stage model: resolve stage order, evaluate entry conditions, dispatch work, capture stage outcome, and transition to the next stage or terminate. |
| FR-6 | Workflow registry and binding | Enumerate and inspect the 176 registered workflows; bind workflows to stages; expose each workflow's inputs, outputs, and declared failure modes. |
| FR-7 | Module registry | Enumerate and inspect the 176 registered modules, including the owning workflow/stage, version, and declared capability surface. |
| FR-8 | HIL gate management | Present pending human-in-the-loop gates (the 4 gate types), capture approve/reject/request-changes decisions with rationale, and block or release the run accordingly. |
| FR-9 | Agent, lead, and sub-agent registry | Enumerate the 19 leads and 55 agent cards/sub-agents; expose capability, ownership of stages/workflows, and per-run assignments. |
| FR-10 | Store registry and residency binding | Enumerate the 120 registered stores; expose type, owning component, and residency/retention metadata; bind stores to projects and enforce residency constraints at bind time. |
| FR-11 | Model tier and provider configuration | Create, select, customize, or author new model tiers from the available models/providers; assign tiers per project and per stage; record the effective tier for every run. |
| FR-12 | Live run monitoring | Stream run state transitions, current stage, progress, active agent/workflow, gate waits, and errors to connected clients without polling as the sole mechanism. |
| FR-13 | Run history, audit trail, and lineage | Persist every run with its inputs, commands issued, stage outcomes, gate decisions, produced artifacts, and the lineage linking artifacts to the producing stage/workflow. |
| FR-14 | Project-scoped configuration overrides | Layer project and stage overrides on top of global configuration; validate the merged result; expose the effective configuration with provenance for each key. |
| FR-15 | Scheduling and concurrency governance | Queue starts when concurrency limits are reached; support deferred/scheduled start; enforce per-project and global concurrency ceilings. |
| FR-16 | Access control and policy enforcement | Enforce role-based permissions per project/portfolio for start, modify, approve, configure, and delete actions; deny by default. |
| FR-17 | Notification and escalation | Emit notifications on run completion, failure, gate waits exceeding threshold, and capacity breaches; route gate escalations to the configured approver set. |
| FR-18 | Checkpoint re-run and recovery | Re-run a run or a single stage from a recorded checkpoint without recomputing unaffected upstream stages; preserve artifact lineage across the re-run. |
| FR-19 | Health, capacity, and backpressure reporting | Report control-plane and executor health, queue depth, in-flight runs, and saturation; signal backpressure and shed or defer starts accordingly. |
| FR-20 | Search, filter, and bulk operations | Search and filter projects, runs, gates, and registry entities by name, status, owner, portfolio, and time; apply bulk actions (archive, cancel, assign tier) across a selection. |

#### Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Control-plane API responsiveness | Read operations p95 ≤ 300 ms, p99 ≤ 800 ms at nominal load; write operations p95 ≤ 600 ms excluding orchestration work. |
| NFR-2 | State propagation latency | A run/stage state change is visible to a connected monitoring client within 2 s; gate-wait indication within 2 s. |
| NFR-3 | Scalability | Support at least 1 000 concurrent projects and 100 concurrent active runs per environment without degrading NFR-1; registries scale to the full 176 modules / 176 workflows / 120 stores without full-scan reads. |
| NFR-4 | Availability | Control-plane read/write availability ≥ 99.9% monthly; submission of control commands must not be lost during a rolling restart. |
| NFR-5 | State durability | Run state and command log are durable and recoverable; no acknowledged control command is lost on process restart. |
| NFR-6 | Security | All requests authenticated; every action authorized against role and resource scope; secrets never returned in read APIs; least-privilege service identities. |
| NFR-7 | Audit immutability | Audit entries are append-only; no API path permits update or deletion of a recorded command, decision, or state transition. |
| NFR-8 | Data residency and retention | Store bindings are refused if a project's residency policy conflicts with the store's declared residency; retention periods are configurable per project and enforced on artifacts and audit records. |
| NFR-9 | Deployment and environment | Deployable to dev/staging/production with environment-supplied configuration; schema/contract evolution is backward compatible within a major API version; zero-downtime rolling deploys. |
| NFR-10 | Observability | Emit metrics, structured logs, and distributed traces for every control command and stage transition, correlated by run ID and project ID. |
| NFR-11 | Idempotency and concurrency safety | Control commands accept an idempotency key and are applied at most once; concurrent conflicting mutations are rejected via optimistic concurrency rather than silently merged. |
| NFR-12 | API compatibility | API version is explicit in the path; within a major version, additive changes only; deprecations announced for at least one minor cycle. |
| NFR-13 | Accessibility | Control-plane UI conforms to WCAG 2.1 AA: keyboard-operable controls, 4.5:1 text contrast, visible focus, status changes announced to assistive technology. |
| NFR-14 | Client support | Full functionality in current evergreen desktop browsers; monitoring and gate decisions usable on tablet viewports ≥ 768 px. |
| NFR-15 | Capacity limits | Published and enforced limits for concurrent runs, queued starts, event retention, and registry entity counts; exceeding a limit produces an explicit, actionable error. |

#### User Stories

- **US-1:** As a Product Forge Operator, I want to create a project from an idea and bind it to a pipeline version, so that I can start work without hand-editing configuration.
- **US-2:** As a Product Forge Operator, I want to start, pause, resume, cancel, and retry runs, so that I stay in control of long-running pipelines.
- **US-3:** As a Product Forge Operator, I want to see live run progress per stage, so that I can tell where a run is and whether it is stuck.
- **US-4:** As a HIL Approver, I want to review gate context and approve, reject, or request changes with a rationale, so that the run proceeds only with human sign-off.
- **US-5:** As a Platform Admin, I want to manage model tiers and providers, so that projects can select cost/quality-appropriate models.
- **US-6:** As a Portfolio Owner, I want a roll-up view of all projects in my portfolio, so that I can spot failing or blocked work quickly.
- **US-7:** As an Auditor, I want to inspect the full command and decision history of a run plus artifact lineage, so that I can explain how an output was produced.
- **US-8:** As a Configuration Owner, I want project-scoped overrides with provenance, so that I can tune a project without changing global defaults.
- **US-9:** As a Product Forge Operator, I want to re-run from a checkpoint after a failure, so that I do not repeat expensive completed stages.

---

### Behaviour

1. **Project creation.** The operator submits name, description, optional portfolio, pipeline version reference, model tier selection, and store bindings. The control plane validates the request, resolves the pipeline definition, creates the project in `draft`, writes the initial configuration revision, and returns the project with its revision token (FR-1, FR-3, FR-11, FR-14).
2. **Run start.** Starting a run snapshots the project's effective configuration and pipeline version at that instant, creating an immutable run record. Subsequent project configuration edits do not alter an in-flight run (FR-3, FR-4, FR-14).
3. **Stage orchestration loop.** For the active stage the control plane evaluates entry conditions from the previous stage's declared outputs, dispatches the bound workflow, listens for terminal outcome, records the outcome with timestamps and produced artifacts, then advances, retries, or halts (FR-5, FR-6, FR-13).
4. **Gate wait.** When a stage declares an HIL gate, the run transitions to `waiting_for_gate`. The control plane publishes the gate to the approver set, records the wait start, and does not advance until a decision is recorded (FR-8, FR-17).
5. **Decision application.** Approve releases the run to the next stage; reject terminates or routes the run per the gate's declared failure path; request-changes returns the run to the producing stage with the rationale attached (FR-8).
6. **Live monitoring.** Connected clients receive an ordered event stream scoped to a run or a portfolio. Each event carries run ID, stage ID, previous state, new state, timestamp, and correlation ID. Late subscribers receive a state snapshot followed by incremental events (FR-12).
7. **Modification during flight.** Configuration, tier, and store-binding changes are accepted only while the affected stage has not started; otherwise the change is queued for the next run or rejected with an explicit reason (FR-3, FR-11, FR-14).
8. **Checkpoint re-run.** On operator request, the control plane identifies the last successful checkpoint at or before the target stage, clones the run record's lineage, and starts a new run that reuses upstream artifacts and recomputes only from the target stage onward (FR-18, FR-13).
9. **Capacity behaviour.** When concurrency ceilings are reached, start requests enter a queue with a visible position. If the queue exceeds its limit, the control plane rejects new starts with a retryable capacity error rather than dropping them silently (FR-15, FR-19, NFR-15).
10. **Archive.** Archiving a project blocks new runs, permits in-flight runs to finish or be cancelled on request, and retains all history and audit records (FR-1, FR-13).

---

### Business Rules

- **BR-1:** A run's pipeline version, effective configuration, and model-tier assignment are frozen at run start and are immutable thereafter.
- **BR-2:** A run cannot be started on an archived project or on a project whose pipeline binding is invalid or whose store bindings violate residency policy.
- **BR-3:** Exactly one terminal outcome is recorded per stage execution; a second concurrent outcome for the same stage execution is rejected.
- **BR-4:** Only users holding the approver role for the project (or portfolio) may record a gate decision; the requesting user's own prior action on the same gate does not auto-approve it.
- **BR-5:** Every gate decision requires a non-empty rationale when the decision is `reject` or `request_changes`.
- **BR-6:** Cancelling a run does not delete history; cancelled runs remain queryable and are distinguished from failed runs.
- **BR-7:** Retry counts are bounded by the stage's declared maximum; exceeding the bound transitions the run to `failed` rather than retrying indefinitely.
- **BR-8:** Global configuration cannot be modified through the project-scoped override API; project overrides are additive layers only.
- **BR-9:** Audit records are append-only and are never removed by project deletion; deletion redacts personal data fields while preserving the event skeleton (NFR-7, NFR-8).
- **BR-10:** A model tier referenced by any non-archived project cannot be deleted; it may be deprecated and hidden from new selections.
- **BR-11:** Bulk operations are atomic per entity: a partial failure reports per-entity results and never silently applies to a subset.
- **BR-12:** Notification escalation thresholds are evaluated against gate wait duration measured from the recorded wait start, not from run start.

---

### Validation

- **V-1:** Project name — required, 1–120 characters, trimmed, unique within a portfolio; duplicate names outside the same portfolio are allowed but flagged.
- **V-2:** Description — optional, ≤ 2 000 characters.
- **V-3:** Pipeline version reference — required at run start; must resolve to an existing, non-retired immutable version.
- **V-4:** Portfolio assignment — optional; if supplied, the portfolio must exist and the requester must hold write scope on it.
- **V-5:** Model tier — required; must reference an existing tier; if a custom tier is submitted, its model/provider entries must all be resolvable and unique.
- **V-6:** Store bindings — each referenced store must exist in the registry; declared residency must satisfy the project's residency policy (NFR-8).
- **V-7:** Configuration overrides — keys must exist in the global configuration schema; values must match the declared type and constraint set; unknown keys are rejected, not ignored.
- **V-8:** Control commands — target run and optional stage must exist and must be in a state that permits the command (e.g. pause only from `running`).
- **V-9:** Gate decision — decision value must be one of `approve`, `reject`, `request_changes`; rationale required per BR-5; gate must currently be pending.
- **V-10:** Concurrency and schedule fields — concurrency ceiling must be a positive integer within the published maximum; scheduled start must be a future timestamp.
- **V-11:** Pagination and filter parameters — page size bounded by the published maximum; unknown filter fields are rejected.
- **V-12:** Idempotency key — when supplied, must be a non-empty opaque string; the same key with a different payload is rejected.

---

### Edge Cases

- **EC-1:** Two operators start the same project simultaneously — both starts are accepted as distinct runs if concurrency allows; if the ceiling is 1, the second is queued with a visible position.
- **EC-2:** A gate is approved by two approvers concurrently — the first decision wins; the second receives a conflict response and the run state is unchanged.
- **EC-3:** A pause command arrives as the run is already transitioning to a terminal state — the command is rejected with the current run state returned.
- **EC-4:** A re-run-from-checkpoint targets a stage that never produced a checkpoint — the request is rejected and the nearest available checkpoint stage is suggested.
- **EC-5:** A project's store binding becomes invalid after policy change (residency reclassification) — new runs are blocked with an actionable error; in-flight runs continue and the conflict is surfaced on the project.
- **EC-6:** The event stream disconnects mid-run — the client reconnects using the last seen event sequence and receives only the missed events plus a state snapshot.
- **EC-7:** A registry entity (module, workflow, store) is retired while a pinned run references it — the run continues against its pinned version; new bindings to the retired version are refused.
- **EC-8:** A bulk archive includes a project with an active run — that project is reported as skipped with reason `active_run`, the others are archived.
- **EC-9:** Configuration override is valid alone but conflicts with a stage-level override — the merged effective configuration is rejected with both offending keys identified.
- **EC-10:** Queue depth exceeds capacity during a burst — excess starts are rejected with a retryable capacity error; no partial run records are created.
- **EC-11:** A run's declared maximum retries is reached during a transient outage — the run transitions to `failed` and the last outcome is preserved rather than being overwritten by the terminal state.
- **EC-12:** Audit query spans a retention boundary — records within retention are returned; the response states the retention window and does not imply completeness beyond it.

---

### Error Handling

- **EH-1:** Validation failures return a structured error listing every offending field with a machine-readable code and a human-readable message; no partial mutation is applied.
- **EH-2:** Not-found references (project, run, stage, gate, tier, store) return a distinct not-found error identifying the missing resource type and identifier.
- **EH-3:** Unauthorized actions return a permission error that names the required role and the resource scope, without disclosing resources the caller cannot see.
- **EH-4:** State conflicts return the current authoritative state alongside the error so the client can reconcile without an extra read.
- **EH-5:** Duplicate idempotency key with a differing payload returns a conflict error and leaves existing state untouched.
- **EH-6:** Downstream executor or workflow unavailability marks the stage execution as failed with a retryable classification; the run follows its declared retry policy.
- **EH-7:** Event stream interruption is recoverable by sequence number; if the requested sequence has been evicted by retention, the client receives a snapshot and an explicit `sequence_gap` notice.
- **EH-8:** Capacity and rate-limit rejections carry a retry-after indication and never create orphan run or command records.
- **EH-9:** Internal failures return a correlation ID, log the full detail server-side, and expose no internal stack traces, identifiers, or secret material to the client.
- **EH-10:** Failed notification delivery does not fail the underlying run transition; the delivery failure is recorded and retried, and the run state remains authoritative.

---

### Acceptance Criteria

- **AC-1 (FR-1, FR-3):** Creating a project with a valid pipeline version returns a project in `draft` with a configuration revision and a resolvable pipeline binding.
- **AC-2 (FR-2):** A portfolio view lists all member projects and reports accurate per-status run counts, gate backlog, and last activity.
- **AC-3 (FR-3, BR-1):** After a project's configuration is edited, an already-started run's effective configuration and pipeline version are unchanged.
- **AC-4 (FR-4):** Start, pause, resume, cancel, and retry each produce the expected run state transition and appear in the run's command history.
- **AC-5 (FR-5, BR-3):** A run traverses stages in the registered order and records exactly one terminal outcome per stage execution.
- **AC-6 (FR-6, FR-7, FR-9, FR-10):** The registries enumerate the full declared sets — 176 workflows, 176 modules, 19 leads, 55 agent cards/sub-agents, and 120 stores — with no silent truncation; any applied limit is reported.
- **AC-7 (FR-8, BR-4, BR-5):** A pending gate blocks run advancement; only an authorized approver can decide; reject and request-changes without a rationale are refused.
- **AC-8 (FR-11, BR-10):** A custom tier built from available models/providers can be selected by a project and is recorded as the effective tier on the resulting run; a tier in use cannot be deleted.
- **AC-9 (FR-12, NFR-2):** A connected monitoring client observes a stage transition within 2 seconds of the transition being recorded.
- **AC-10 (FR-13, NFR-7):** For any completed run, the API returns the ordered command log, stage outcomes, gate decisions, produced artifacts, and artifact-to-stage lineage; no API path alters or removes an audit entry.
- **AC-11 (FR-14, V-7, BR-8):** An override with an unknown key is rejected; a valid override appears in the effective configuration with provenance identifying the source layer.
- **AC-12 (FR-15, EC-10, EH-8):** Starts beyond the concurrency ceiling are queued with a position, and starts beyond queue capacity are rejected with a retryable capacity error and create no run records.
- **AC-13 (FR-16, EH-3):** A caller lacking the approve role receives a permission error naming the required role; a caller without project read scope cannot discover the project.
- **AC-14 (FR-17, BR-12):** A gate exceeding its wait threshold produces a notification and an escalation to the configured approver set, measured from the recorded wait start.
- **AC-15 (FR-18, EC-4):** A checkpoint re-run recomputes only from the target stage onward, reuses upstream artifacts with intact lineage, and is rejected with a suggested stage when no checkpoint exists.
- **AC-16 (FR-19, NFR-15):** Health output reports queue depth, in-flight runs, and saturation, and published limits are enforced with explicit errors when exceeded.
- **AC-17 (FR-20, BR-11):** Search and filter return matching entities, and a bulk operation reports per-entity results, skipping ineligible entities with reasons.
- **AC-18 (NFR-1, NFR-3):** Under the nominal load defined for the environment, read p95 latency is ≤ 300 ms and write p95 is ≤ 600 ms with 100 concurrent active runs.
- **AC-19 (NFR-4, NFR-5):** A rolling restart during active runs loses no acknowledged control command, and run state is fully recoverable afterwards.
- **AC-20 (NFR-11, EH-5):** Replaying an identical command with the same idempotency key applies no additional state change; the same key with a different payload is rejected.
- **AC-21 (NFR-13, NFR-14):** All control actions performable by mouse are performable by keyboard, live status changes are announced to assistive technology, and monitoring plus gate decisions work at a 768 px viewport.

---

### API Behaviour

- **API-1 — Project lifecycle.** `POST /v1/projects`, `GET /v1/projects`, `GET /v1/projects/{projectId}`, `PATCH /v1/projects/{projectId}`, `POST /v1/projects/{projectId}:archive`, `POST /v1/projects/{projectId}:restore`, `DELETE /v1/projects/{projectId}`. Creation returns `201` with the project and its revision token; mutation returns `200` with the new revision; archive/restore return the updated project.
- **API-2 — Portfolios.** `POST /v1/portfolios`, `GET /v1/portfolios/{portfolioId}`, `POST /v1/portfolios/{portfolioId}/projects`, `DELETE /v1/portfolios/{portfolioId}/projects/{projectId}`. Membership changes are idempotent.
- **API-3 — Registries.** `GET /v1/registries/{registryType}` where `registryType` ∈ `{pipelines, stages, workflows, modules, stores, agents, leads, sub-agents, model-tiers}`; supports `q`, `status`, `owner`, `limit`, `cursor`. Each entity is addressable at `GET /v1/registries/{registryType}/{entityId}`. Registry reads are cacheable and may be served from a consistent read replica.
- **API-4 — Run submission.** `POST /v1/runs` with `projectId`, optional `pipelineVersion`, optional `scheduledAt`, and `Idempotency-Key`. Returns `201` with the run, or `202` when queued with a queue position, or `429` with `Retry-After` when capacity is exhausted.
- **API-5 — Run control.** `POST /v1/runs/{runId}:start|pause|resume|cancel|retry`, each accepting `Idempotency-Key` and an optional `stageId` scoping the command. Each returns the resulting run state; commands invalid for the current state return `409` with the authoritative state.
- **API-6 — Run read.** `GET /v1/runs/{runId}` returns run state, current stage, effective configuration reference, pipeline version, and per-stage summaries. `GET /v1/runs` supports filters `projectId`, `portfolioId`, `status`, `from`, `to`, `cursor`, `limit`.
- **API-7 — Event stream.** `GET /v1/runs/{runId}/events` and `GET /v1/portfolios/{portfolioId}/events` return an ordered event stream supporting resume from a sequence token. Each event carries `sequence`, `runId`, `stageId`, `fromState`, `toState`, `timestamp`, `correlationId`. On sequence eviction the stream emits a snapshot event followed by a `sequence_gap` event (EH-7).
- **API-8 — Gates.** `GET /v1/runs/{runId}/gates` lists gates with pending/decided status and wait duration. `POST /v1/runs/{runId}/gates/{gateId}:decide` accepts `decision` ∈ `{approve, reject, request_changes}` plus `rationale`; returns the updated gate and resulting run state, or `409` if already decided (BR-3, EC-2).
- **API-9 — Configuration.** `GET /v1/projects/{projectId}/config` returns the effective configuration with per-key provenance (global / project / stage). `PUT /v1/projects/{projectId}/config` replaces project-level overrides and returns the recomputed effective configuration, or a validation error naming every offending key (V-7, BR-8).
- **API-10 — Checkpoint re-run.** `POST /v1/runs/{runId}:rerun-from` with `stageId` and optional `overrides`; returns a new run record referencing the source run and its reused checkpoints, or a not-found error identifying the nearest available checkpoint stage (EC-4).
- **API-11 — Audit and lineage.** `GET /v1/runs/{runId}/audit`, `GET /v1/audit` (filters: `actor`, `action`, `resourceType`, `from`, `to`), and `GET /v1/runs/{runId}/lineage` returning the artifact-to-stage graph. Audit endpoints are read-only; no write or delete verb is exposed (NFR-7).
- **API-12 — Bulk operations.** `POST /v1/operations:bulk` with a target set and an action (`archive`, `cancel`, `assign-tier`, `bind-store`); returns a per-entity result array with `applied`, `skipped`, or `failed` plus a reason code (BR-11, AC-17).
- **API-13 — Health and capacity.** `GET /v1/health` and `GET /v1/capacity` return component health, queue depth, in-flight run count, configured ceilings, and saturation indicators (FR-19).
- **API-14 — Cross-cutting conventions.** All mutating calls accept `Idempotency-Key` (NFR-11) and an optimistic-concurrency token for resource updates. Errors use a single envelope containing `code`, `message`, `details[]`, and `correlationId`. Collections use cursor pagination with an explicit `nextCursor`. Rate and capacity rejections return `429` with `Retry-After`. API version is carried in the path and evolves additively within a major version (NFR-12).

---

### Priority

**must-have** — F-1 is the control plane for the entire product. Every other feature operates on projects, runs, registries, or gates that F-1 owns, so no other feature can be delivered without it.

Within F-1, the following are the non-negotiable core: FR-1, FR-3, FR-4, FR-5, FR-6, FR-8, FR-11, FR-12, FR-13, FR-16, and NFR-1, NFR-4, NFR-5, NFR-6, NFR-7, NFR-11. The remaining requirements (FR-2, FR-7, FR-9, FR-10, FR-14, FR-15, FR-17, FR-18, FR-19, FR-20) are **must-have for the declared first release** because the discovery scope explicitly includes the complete backend surface — 176 modules, 176 workflows, 32 stages, 4 HIL gates, 19 leads, 55 agent cards/sub-agents, all configs, and all 120 registered stores. Nothing in this section is deferred; any reduction of F-1's scope requires explicit user approval.
