## F-3: E2E Pipeline Initiation and Monitoring

**Feature ID:** F-3
**Summary:** F-3 covers the end-to-end execution experience for a pipeline project created under F-2 and registered under F-1: launching a run, driving it through the full ordered stage model, streaming live progress and telemetry, pausing at human-in-the-loop (HIL) gates for decisions, and retaining a complete, auditable record of everything that happened.

### Requirements

#### Functional Requirements

| ID | Requirement |
|---|---|
| FR-46 | **Run initiation from project** — Start a pipeline run for an existing project bound to an immutable pipeline version. Accept an optional idempotency key, optional run label, and optional starting stage override (only permitted for stages whose entry conditions permit a manual start). Return a stable run identifier immediately. |
| FR-47 | **Pre-flight readiness validation** — Before any stage executes, validate that the project has a seed idea, required metadata, a resolved model tier, a bound pipeline definition/version, and a satisfied gate policy. Block initiation with an actionable, itemized readiness report if any check fails. |
| FR-48 | **Run plan materialization** — Expand the pinned pipeline version into a concrete, ordered run plan covering every stage in the registered stage model, including stage dependencies, expected agent/lead assignments, gate markers, and the config revision snapshot. Persist the plan as an immutable snapshot for the run. |
| FR-49 | **Stage-by-stage execution progression** — Dispatch stages in dependency order, evaluate each stage's entry conditions, capture entry/exit timestamps, outcome, attempt number, and emitted artifacts, then transition to the next eligible stage(s). |
| FR-50 | **Live run monitoring view** — Provide a single monitoring surface per run showing overall status, current stage(s), elapsed time, progress through the plan, model tier in effect, and outstanding gates. |
| FR-51 | **Stage timeline / dependency view** — Visually represent the run plan as an ordered timeline (and dependency graph where stages are parallelizable) with per-stage status, duration, attempt count, and gate markers. |
| FR-52 | **Stage detail drill-down** — For any stage, expose inputs, outputs, resolved agent/lead assignment, model tier used, config revision, timing breakdown, artifacts, warnings, and errors. |
| FR-53 | **Console / streaming log view** — Provide an append-only, per-run and per-stage log stream with severity filtering, text search, and pagination for historical retrieval. |
| FR-54 | **Streaming telemetry and heartbeats** — Emit periodic liveness heartbeats for running stages and detect stalls (no heartbeat or no progress within the configured threshold), marking the stage as stalled without terminating it automatically. |
| FR-55 | **HIL gate detection and surfacing** — Detect when a run reaches any registered human-in-the-loop gate, transition the run to an awaiting-gate state, and surface the gate's payload, context, and required decision to eligible approvers. |
| FR-56 | **Gate decision capture** — Accept approve / reject / request-changes decisions with an optional comment and optional attachment, record the decision as an auditable event with actor, timestamp, and gate payload hash, and advance or halt the run accordingly. |
| FR-57 | **Gate timeout and escalation policy** — Apply a configurable gate service-level target per gate type, send reminders on approach, escalate to a configured escalation target on breach, and hold the run indefinitely rather than auto-approving. |
| FR-58 | **Pause / resume / cancel during run** — Allow an operator to pause a run between stage boundaries, resume a paused run, and cancel a run; cancellation stops new stage dispatch, marks in-flight stages as cancelled at their next checkpoint, and preserves all completed work. |
| FR-59 | **Retry and resume-from-stage** — Retry a failed or cancelled stage (incrementing attempt number and retaining prior attempts), or resume a run from a completed checkpoint without re-executing successfully completed stages. |
| FR-60 | **Run status and lifecycle model** — Enforce a canonical run state machine (`queued → preflight → running → awaiting_gate → paused → retrying → failed → cancelled → completed`) with documented, validated transitions; reject any command that is invalid for the current state. |
| FR-61 | **Notifications on run events** — Emit in-app notifications on run start, stage failure, gate arrival, gate decision, stall detection, cancellation, and completion, respecting per-user notification preferences. |
| FR-62 | **Run history and cross-run comparison** — List all historical runs for a project with status, duration, gate outcomes, and failure counts; allow side-by-side comparison of the same stage's outcome across two runs. |
| FR-63 | **Artifact and configuration association** — Record the exact configuration revision, model tier, and agent card set used by each run, and link every artifact produced to the run, stage, and attempt that produced it. |
| FR-64 | **Multi-project run queue and concurrency view** — Provide a cross-project/portfolio view of active, queued, and awaiting-gate runs, with visibility into concurrency limits and queue position. |
| FR-65 | **Run diagnostics export** — Export a complete run manifest (plan snapshot, stage outcomes, timings, gate decisions, artifact index, config revision, error records) in a machine-readable format for audit and offline analysis. |

#### Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-31 | **Monitoring performance** — The run monitoring view must reach first contentful paint in ≤1s and interactive in ≤2.5s on a standard connection; a backend stage transition must be reflected in the UI within ≤2s at the 95th percentile. |
| NFR-32 | **Log streaming throughput and latency** — Log lines must appear in the live view within ≤1.5s of emission at the 95th percentile; the system must sustain ≥5,000 log lines per minute per run without dropping or reordering lines. |
| NFR-33 | **Scalability** — Support ≥50 concurrent runs across ≥200 registered projects and ≥1,000,000 retained stage-execution records with no degradation of monitoring latency beyond NFR-31/NFR-32 targets. |
| NFR-34 | **Availability and durability** — The control plane and monitoring surface must maintain ≥99.9% monthly availability; run state must be durably persisted at every stage boundary so that no completed stage record is lost on process restart. |
| NFR-35 | **Security and authorization** — All run commands and gate decisions must be authenticated, authorized by role (viewer / operator / approver / admin), and written to an append-only audit log; gate approval must be attributable to a single named actor, and the gate policy must be able to require an approver distinct from the run initiator. |
| NFR-36 | **Data residency and retention** — Run records, telemetry, and logs must be stored in the region configured for the owning project; retention must be configurable (default: 90 days hot, with export available before expiry); telemetry payloads must contain no end-user PII. |
| NFR-37 | **Deployment and environment parity** — Run semantics must be identical across local, development, staging, and production environments; a pinned pipeline version must resolve to identical stage definitions in every environment, and no stage behavior may branch on environment identity. |

#### User Stories

| ID | Story |
|---|---|
| US-25 | As a **pipeline operator**, I want to start a run from a project with one action and receive immediate confirmation of readiness, so that I do not waste time on runs that cannot complete. |
| US-26 | As a **pipeline operator**, I want to watch a run progress through every stage in real time, so that I know exactly where the work stands without asking anyone. |
| US-27 | As a **stage lead / approver**, I want to be notified when my gate is reached and see the complete payload I am deciding on, so that I can make an informed, timely decision. |
| US-28 | As a **reviewer**, I want to drill into any stage's inputs, outputs, and logs, so that I can diagnose failures and verify quality of the produced artifacts. |
| US-29 | As a **pipeline operator**, I want to pause, resume, cancel, and retry stages safely, so that I can intervene without destroying completed work. |
| US-30 | As an **auditor**, I want to export a complete run manifest, so that I can reconstruct who decided what, when, and with which configuration. |

### Behaviour

1. **Initiation.** The operator selects a project and invokes *Start run*. The system creates a run in `queued`, then immediately moves it to `preflight` and executes readiness validation (FR-47). On success it materializes the run plan (FR-48) and transitions to `running`.
2. **Execution.** The scheduler resolves which stages are eligible, dispatches them, and records a stage-execution record for each attempt. Stage transitions are published to the monitoring surface and log stream.
3. **Gate interception.** When an eligible stage is a HIL gate, the run transitions to `awaiting_gate` instead of dispatching the stage. The gate payload is captured at that moment and frozen; later changes to the run do not mutate a pending gate payload.
4. **Decision.** On approve, the run returns to `running` and continues. On request-changes, the run returns to `running` with the gate's rework instructions attached to the targeted upstream stage, which is re-dispatched as a new attempt. On reject, the run transitions to `failed` with the rejection recorded as the terminal cause.
5. **Completion.** A run reaches `completed` when all non-skipped stages have a terminal successful outcome and no gates remain pending. A run reaches `failed` when a stage exhausts its retry allowance, a gate is rejected, or a stall escalates to a hard failure per policy.
6. **Monitoring.** All monitoring data is derived from persisted run state; the live view is a projection over the same records used for export, so the live view and the exported manifest can never disagree on outcomes.
7. **Cancellation.** Cancel takes effect at the next stage boundary. In-flight stages are signalled to stop and are recorded as `cancelled` with partial outputs retained and clearly marked as partial.

### Business Rules

| ID | Rule |
|---|---|
| BR-1 | A run is immutable with respect to its pinned pipeline version: upgrading the project's pipeline binding never alters an existing run's plan. |
| BR-2 | A run plan snapshot is created once at initiation and is never rewritten. All stage outcomes are appended against that snapshot. |
| BR-3 | No HIL gate may ever be auto-approved. Timeout escalates; it does not decide. |
| BR-4 | Every command that changes run state (start, pause, resume, cancel, retry, gate decision) is recorded as an auditable command with actor, timestamp, target, and prior state. |
| BR-5 | Retrying a stage never deletes the prior attempt; attempts accumulate and the latest attempt determines the stage's effective outcome. |
| BR-6 | Resuming from a checkpoint must not re-execute any stage whose latest attempt is terminally successful. |
| BR-7 | A stage may only be dispatched if all its declared dependencies have terminally successful latest attempts. |
| BR-8 | Request-changes at a gate must name at least one target stage or stage group to be reworked; an untargeted request-changes is rejected. |
| BR-9 | Gate decisions are attributed to exactly one authenticated actor; delegated or shared credentials are not a valid approval basis. |
| BR-10 | If the project's configuration revision changes while a run is active, the active run continues on its recorded revision; the change applies to subsequent runs only. |
| BR-11 | Stalled stages are surfaced and escalated but are never silently terminated. |
| BR-12 | Cancelled or failed runs remain fully readable and exportable; they are never deleted by retention until the configured retention window expires. |

### Validation

| ID | Validation |
|---|---|
| V-1 | Run initiation requires a valid project identifier that exists and is not archived or permanently deleted. |
| V-2 | Run initiation is rejected if the project has no bound pipeline definition/version. |
| V-3 | Run initiation is rejected if no model tier can be resolved for the project. |
| V-4 | Run initiation is rejected if the seed idea is empty or whitespace-only. |
| V-5 | A starting-stage override may only name a stage whose entry conditions permit manual start; otherwise rejected with the list of permitted stages. |
| V-6 | An idempotency key, if supplied, must be unique per project; a repeated key returns the original run rather than creating a second. |
| V-7 | A gate decision must be one of `approve`, `request_changes`, or `reject`. |
| V-8 | A `reject` or `request_changes` decision must include a comment of at least 10 characters. |
| V-9 | A `request_changes` decision must reference at least one valid target stage present in the run plan. |
| V-10 | A pause/resume/cancel/retry command must be valid for the run's current state, or it is rejected without side effects. |
| V-11 | Retry requires the target stage to be in a `failed` or `cancelled` state and to have remaining retry allowance. |
| V-12 | Log and telemetry queries require a valid run identifier and must reject offset/limit values outside the documented bounds. |
| V-13 | A run label, if supplied, must be ≤128 characters and must not contain control characters. |
| V-14 | Gate comments and rework instructions must be ≤5,000 characters. |

### Edge Cases

| ID | Edge case |
|---|---|
| EC-1 | Operator cancels a run while a gate is awaiting decision — the gate is closed as `cancelled_by_operator`, and the run moves to `cancelled` without a decision record. |
| EC-2 | Two approvers submit conflicting decisions for the same gate within the same second — the first persisted decision wins; the second is rejected with a conflict response and the winner is shown to both. |
| EC-3 | A stage emits an enormous artifact or log volume — the live view truncates display output with a "load full output" affordance; the persisted record remains complete. |
| EC-4 | A run is paused at a stage boundary while a parallel sibling stage is still executing — pause takes effect for new dispatches; the in-flight sibling is allowed to finish and its outcome is recorded. |
| EC-5 | The model tier referenced by the run plan is later removed from the tier catalog — the run continues using the pinned tier definition captured in the plan snapshot. |
| EC-6 | Resume is requested for a run whose last stage boundary is a gate awaiting decision — resume is rejected; the operator is directed to decide or cancel the gate. |
| EC-7 | A stall is detected but the stage recovers and emits a heartbeat — the stall flag is cleared, the stall event remains in the audit trail, and no failure is recorded. |
| EC-8 | A retry is requested on a stage whose downstream dependents already produced artifacts — dependents are marked `stale` and are re-dispatched after the retried stage succeeds. |
| EC-9 | A run plan contains a stage with zero dependencies and zero dependents (isolated stage) — it is dispatched in the first wave and its failure is recorded but does not block unrelated branches. |
| EC-10 | Two runs are started for the same project concurrently — both are permitted and tracked independently; the monitoring view clearly separates them by run identifier and start time. |
| EC-11 | Log stream client disconnects mid-run and reconnects — the client is replayed from its last acknowledged cursor without gap or duplication. |
| EC-12 | Retention expiry occurs while a run is still active — active runs and their associated logs are exempt from retention deletion until they reach a terminal state. |
| EC-13 | A gate escalation target is unconfigured — the gate remains in `awaiting_gate`, an outstanding-escalation warning is surfaced in the UI, and the run proceeds no further. |
| EC-14 | The pipeline version pinned by the run is later deprecated — the run continues; deprecation is communicated in the monitoring view but never blocks execution. |

### Error Handling

| ID | Condition | Handling |
|---|---|---|
| EH-1 | Pre-flight validation failure | Return HTTP 422 with a readiness report listing each failed check with a machine-readable code and a human-readable remediation hint. No run is created. |
| EH-2 | Duplicate idempotency key | Return HTTP 200 with the previously created run record; never create a second run. |
| EH-3 | Invalid state transition command | Return HTTP 409 with the current state, the attempted command, and the set of commands valid in that state. No state change occurs. |
| EH-4 | Unauthorized command or gate decision | Return HTTP 403; record the denied attempt in the audit log with actor and target; do not reveal run payload contents. |
| EH-5 | Concurrent gate decision conflict | Return HTTP 409 naming the winning decision and its actor; the losing decision is discarded and logged. |
| EH-6 | Stage execution error | Record a structured error (code, message, stage, attempt), mark the stage `failed`, emit a failure notification, and hold the run for operator action unless the run policy specifies a bounded automatic retry. |
| EH-7 | Dependency unreachable / stage never becomes eligible | Mark the dependent stage `blocked`, surface the blocking dependency chain in the timeline view, and notify the operator with the root blocking stage. |
| EH-8 | Log or telemetry stream unavailable to the client | Show a non-destructive "live stream interrupted" banner with a manual reconnect action; retain server-side buffering so no lines are lost. |
| EH-9 | Run record or plan snapshot read failure | Return HTTP 500 with a correlation identifier; the monitoring view shows a retryable error state rather than a blank or misleading view. |
| EH-10 | Persistence failure at a stage boundary | The run halts in a `faulted` sub-state, no further stages dispatch, and the operator is notified; recovery restores from the last durable boundary. |
| EH-11 | Export request exceeds size policy | Return HTTP 413 with the computed size, the applicable limit, and a suggestion to narrow the export by stage or time range. |
| EH-12 | Stall threshold breached with no recovery | Surface a stall event, notify the operator, and apply the configured stall policy (escalate or fail); never terminate silently. |

### Acceptance Criteria

| ID | Acceptance criterion |
|---|---|
| AC-1 | Starting a run on a valid, fully configured project creates a run in `queued` and returns a run identifier within 2 seconds. |
| AC-2 | Starting a run on a project missing a model tier is blocked, no run is created, and the readiness report names the missing tier. |
| AC-3 | A created run's plan snapshot lists every stage of the pinned pipeline version in dependency order, and the snapshot does not change when the project's pipeline binding is later upgraded. |
| AC-4 | The monitoring view reflects each stage transition within 2 seconds at the 95th percentile under the load defined in NFR-33. |
| AC-5 | Reaching each of the registered human-in-the-loop gates transitions the run to `awaiting_gate` and surfaces the gate to eligible approvers without advancing any further stage. |
| AC-6 | An approve decision returns the run to `running` and dispatches the next eligible stage; a reject decision moves the run to `failed` with the rejection recorded as the terminal cause. |
| AC-7 | A `request_changes` decision without a named target stage is rejected and the gate remains open. |
| AC-8 | A gate left undecided beyond its service-level target generates a reminder and, on breach, an escalation event; the run remains in `awaiting_gate` and no approval is recorded. |
| AC-9 | Pausing a run stops new stage dispatch, and resuming it dispatches the next eligible stage without re-executing any terminally successful stage. |
| AC-10 | Cancelling a run preserves all completed stage records and artifact links and marks the run `cancelled`. |
| AC-11 | Retrying a failed stage creates a new attempt with an incremented attempt number while the prior attempt remains retrievable. |
| AC-12 | A retried stage's downstream dependents are marked `stale` and are re-dispatched after the retry succeeds. |
| AC-13 | Log lines emitted by a stage appear in the live view within 1.5 seconds and the complete log set remains retrievable after run completion. |
| AC-14 | Reconnecting a log stream client after a disconnect yields no missing and no duplicated lines relative to its last acknowledged cursor. |
| AC-15 | Every state-changing command and gate decision appears in the audit log with actor, timestamp, target, and prior state. |
| AC-16 | A gate approval attempted by a user who is not an eligible approver is denied with HTTP 403 and logged. |
| AC-17 | The diagnostics export reproduces exactly the stage outcomes, timings, and decisions visible in the live monitoring view for a completed run. |
| AC-18 | A stage that has breached the heartbeat threshold without progress is flagged as stalled and notified, and is not terminated. |
| AC-19 | An active run is unaffected by its project's configuration revision changing mid-run; the change applies only to subsequent runs. |
| AC-20 | Historical runs remain readable and exportable for the full configured retention period, including failed and cancelled runs. |

### API Behaviour

| ID | Endpoint / interaction |
|---|---|
| API-1 | `POST /projects/{projectId}/runs` — initiates a run. Body: `{ idempotencyKey?, label?, startStageOverride?, gatePolicy? }`. Returns `201` with `{ runId, status, planSnapshotId, createdAt }`. Returns `422` with a readiness report on pre-flight failure; `200` with the existing run on duplicate idempotency key; `403` when the caller lacks the operator role. |
| API-2 | `GET /runs/{runId}` — returns the run record: status, plan snapshot reference, config revision, model tier, timings, current stage(s), pending gate reference, attempt counts, and terminal cause if any. `404` if the run does not exist or is not visible to the caller. |
| API-3 | `GET /runs/{runId}/plan` — returns the immutable run plan snapshot: ordered stages, dependencies, gate markers, agent/lead assignments, and the config revision captured at initiation. |
| API-4 | `GET /runs/{runId}/stages` — paginated list of stage executions with status, attempt number, start/end timestamps, duration, and artifact references. Supports `status`, `attempt`, and cursor pagination parameters. |
| API-5 | `GET /runs/{runId}/stages/{stageId}` — returns full stage detail: inputs, outputs, resolved assignment, model tier, timing breakdown, warnings, errors, and attempt history. |
| API-6 | `GET /runs/{runId}/logs?stageId=&severity=&cursor=&limit=` — paginated historical log retrieval. Returns a cursor for continuation; declared ordering is strictly monotonic by sequence number. |
| API-7 | `GET /runs/{runId}/stream` — server-sent event stream of run, stage, gate, telemetry, and log events. Supports a `cursor` parameter for gap-free resume; emits periodic heartbeat comments; terminates cleanly with a terminal event on run completion, failure, or cancellation. |
| API-8 | `POST /runs/{runId}/commands` — accepts `{ command: "pause" | "resume" | "cancel", reason? }`. Returns `202` with the accepted command record. Returns `409` with the current state and valid commands when the transition is invalid. |
| API-9 | `POST /runs/{runId}/stages/{stageId}/retry` — retries a failed or cancelled stage. Body: `{ reason? }`. Returns `202` with the new attempt record. `409` when the stage state or retry allowance does not permit a retry. |
| API-10 | `GET /runs/{runId}/gates` — lists gates for the run with status, reached-at time, service-level target, escalation state, and decision if present. |
| API-11 | `POST /runs/{runId}/gates/{gateId}/decision` — submits `{ decision: "approve" \| "request_changes" \| "reject", comment, targets?, attachments? }`. Returns `201` with the recorded decision. `403` when the caller is not an eligible approver; `409` on conflicting concurrent decision; `422` on validation failure (V-7–V-9, V-14). |
| API-12 | `GET /runs?projectId=&portfolioId=&status=&cursor=&limit=` — cross-project run listing used by the queue and concurrency view (FR-64). Returns run summaries with queue position and concurrency metadata. |
| API-13 | `GET /runs/{runId}/export?format=json` — returns a complete run manifest as a downloadable document. Returns `413` with size guidance if the export exceeds the configured limit. |
| API-14 | `GET /projects/{projectId}/runs/{runIdA}/compare/{runIdB}` — returns a stage-by-stage diff of status, duration, attempt count, gate outcome, and config revision between two runs. |
| API-15 | All mutating endpoints accept an optional `Idempotency-Key` header; repeated keys within the idempotency window return the original result rather than performing the mutation twice. All responses carry a request correlation identifier for support and audit tracing. |

### Priority

| Capability | Priority |
|---|---|
| Run initiation with pre-flight validation (FR-46, FR-47) | **Must-have** |
| Run plan materialization with pinned version and config revision (FR-48, FR-63) | **Must-have** |
| Stage-by-stage execution progression and lifecycle state machine (FR-49, FR-60) | **Must-have** |
| Live run monitoring view (FR-50) | **Must-have** |
| HIL gate detection, surfacing, and decision capture (FR-55, FR-56) | **Must-have** |
| Pause / resume / cancel (FR-58) | **Must-have** |
| Retry and resume-from-stage (FR-59) | **Must-have** |
| Log streaming and historical retrieval (FR-53) | **Must-have** |
| Security, authorization, and audit trail (NFR-35) | **Must-have** |
| Durability at stage boundaries (NFR-34) | **Must-have** |
| Stage timeline / dependency view (FR-51) | **Should-have** |
| Stage detail drill-down (FR-52) | **Should-have** |
| Streaming telemetry and stall detection (FR-54) | **Should-have** |
| Gate timeout and escalation policy (FR-57) | **Should-have** |
| Run history, comparison, and diagnostics export (FR-62, FR-65) | **Should-have** |
| Notifications on run events (FR-61) | **Should-have** |
| Multi-project run queue and concurrency view (FR-64) | **Should-have** |
| Cross-run stage comparison API (API-14) | **Nice-to-have** |
| Configurable retention windows and region pinning beyond defaults (NFR-36) | **Nice-to-have** |
