## F-6: Manual Input and Operation Control

**Feature ID:** F-6

**Summary:** F-6 covers the operator's direct, interactive command surface over live pipeline activity in Product Forge. Where F-1 owns the project/run registry and F-3 owns automated end-to-end execution, F-6 defines what a human operator can *do* to a run, a stage, a group of runs, or the system as a whole while it is executing — supplying manual input, deciding human-in-the-loop (HIL) gates, pausing/resuming/cancelling, retrying or skipping stages, overriding parameters, halting emergency-wide, and every supporting concern those actions require (preview/dry-run, confirmation, idempotency, conflict handling, audit, and role gating). Every manual action is a first-class, auditable command that respects the run/stage model defined elsewhere and never silently mutates historical records.

**Boundary note:** F-6 does not own project records or the run registry (F-1), the stage orchestration model or automated execution of stages (F-3), multi-project run-group structure (F-5), portfolio membership rules (F-4), or model-tier definitions (F-2). F-6 issues commands *against* those authoritative resources through their published contracts, and it owns the semantics of the manual-input and operator-control layer itself.

---

### Requirements

#### Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-116 | **Manual input submission** — An operator can submit free-form and/or structured input to a target run or a specific stage (e.g., clarifying context, corrected data, an answer to an agent's question). Input is attached to the run as a versioned, attributable artifact and is visible to the target stage on its next read. | must-have |
| FR-117 | **Human-in-the-loop gate decision** — At any HIL gate (of the 4 gates in the stage model), an operator can Approve, Reject (with reason), or Request-changes. The decision is recorded with actor, timestamp, reason, and the exact artifact revision it applied to, then unblocks or blocks the run per gate policy. | must-have |
| FR-118 | **Pause and resume** — An operator can pause and resume a whole run or a single stage. Pause takes effect at the next safe checkpoint; the run/stage records `paused`, the actor, and the reason. Resume continues from the recorded checkpoint without re-executing completed units. | must-have |
| FR-119 | **Cancel (graceful and force)** — An operator can cancel a run or stage. Graceful cancel lets the current unit finish and marks the remainder cancelled; force cancel interrupts the current unit immediately and marks it aborted. Both are recorded as distinct, auditable outcome classes. | must-have |
| FR-120 | **Retry** — An operator can retry a failed or aborted stage/run. Retry creates a new attempt with a fresh attempt counter, preserves prior attempts for audit, and re-enters entry-condition evaluation. Non-retryable failures are refused with a reason. | must-have |
| FR-121 | **Skip / force-advance override** — An operator can skip a stage or force-advance to the next stage, subject to a gate-policy check. Overrides require a reason and produce a distinct "overridden" transition type that is visible in the run timeline. | should-have |
| FR-122 | **Parameter and configuration override** — An operator can override run-scoped or stage-scoped parameters (e.g., model tier for a single stage, retry budget, timeout) mid-flight. Overrides are effective only for the scope chosen and are captured as a new configuration revision. | should-have |
| FR-123 | **Operation preview / dry-run** — Before executing a manual operation, the operator can request a preview describing the projected effect: which run(s)/stage(s) are affected, blocking preconditions, and irreversibility class. The preview performs no mutation. | should-have |
| FR-124 | **Confirmation for destructive operations** — Operations classified as destructive or irreversible (force cancel, skip gate, permanent delete of manual input, emergency halt) require an explicit confirmation step before dispatch. | must-have |
| FR-125 | **Operation queueing and conflict serialization** — Manual operations are queued per target and serialized so conflicting commands (e.g., resume while a cancel is in-flight) cannot race. A conflicting command is either rejected with a conflict reason or queued per an explicit operator choice. | must-have |
| FR-126 | **Idempotent command dispatch** — Every manual operation accepts a client-supplied idempotency key; re-submitting the same key returns the original result instead of re-applying the operation. | must-have |
| FR-127 | **Manual operation audit trail** — Every accepted, refused, previewed, and rolled-back manual operation is appended to an immutable audit log with actor identity, role, target, parameters, reason, idempotency key, outcome, and timestamps. Audit entries are never edited or deleted. | must-have |
| FR-128 | **Emergency halt** — An authorized operator can issue a system-wide or project-scoped emergency halt that immediately stops dispatch of new stage work across all affected runs and moves them to a halted state. Resume from halt follows the pause/resume rules. | must-have |
| FR-129 | **Role-gated operations** — Manual operations are gated by operator role/permission (e.g., viewer cannot control; controller can pause/resume/retry; approver can decide gates; admin can halt and skip gates). Unauthorized attempts are refused and audited. | must-have |
| FR-130 | **Operation feedback and live status** — After dispatch, the operator receives acknowledgement, then live status updates for the operation (pending → applied → failed) with the resulting run/stage state, surfaced in the run timeline. | must-have |
| FR-131 | **Rollback of manual input** — Where a manual input or override has not yet been consumed by its target stage, an operator can withdraw it, returning the run/stage to its prior input/config revision, recorded as a compensating audit entry. | should-have |
| FR-132 | **Bulk manual operations** — The same operation (pause, resume, cancel, retry, halt) can be applied to a set of runs, a portfolio's member runs, or a multi-project run group's children, with per-target outcomes reported. Target selection reuses F-4/F-5 scoping surfaces. | should-have |
| FR-133 | **Deferred / scheduled manual operation** — An operator can schedule a manual operation for a future time or condition (e.g., "pause when stage X completes", "retry after backoff"), which is dispatched automatically under the same authorization and audit rules. | nice-to-have |

#### Non-Functional Requirements

| ID | Requirement | Target / Measurement |
|---|---|---|
| NFR-68 | **Command acknowledgement latency** — Manual control commands acknowledge quickly independent of stage work. | p95 ack < 500 ms, p99 < 1 s, measured at the control API boundary. |
| NFR-69 | **Emergency halt propagation** — Halt stops new work across affected runs promptly. | ≥ 99% of affected runs stop dispatching new stage work within 2 s of halt acceptance. |
| NFR-70 | **Operation throughput / scalability** — The control surface handles many operators and targets concurrently. | Sustain ≥ 200 concurrent manual operations and ≥ 50 operators per project without >1% conflict-induced rejection increase. |
| NFR-71 | **Consistency (no orphaned operations)** — Every dispatched operation reaches a terminal state (applied/refused/failed) — no dangling pendings. | 100% of operations terminal within their SLA window; zero orphans over a 24 h soak. |
| NFR-72 | **Availability of the control plane** — Operators can reach controls while runs execute. | Control plane monthly availability ≥ 99.9%; control surface usable during worker degradation. |
| NFR-73 | **Security — authentication** — Every manual operation is performed by an authenticated principal (user or service). | 100% of operations carry a verified identity; anonymous operations rejected. |
| NFR-74 | **Security — authorization** — Role/permission checks are enforced server-side on every operation. | 100% enforcement (blocked attempts audited); no client-trusted authorization. |
| NFR-75 | **Audit immutability and retention** — Audit entries cannot be modified or deleted and are retained per policy. | Append-only store; retention ≥ 12 months; tamper-evidence verified in test. |
| NFR-76 | **Idempotency correctness** — Duplicate idempotency keys never double-apply an operation. | 100% dedup across retries/network replays; verified by fault-injection tests. |
| NFR-77 | **Data residency** — Run state, manual inputs, and audit records remain in the configured region. | No cross-region persistence of control/audit data outside the project's configured residency. |
| NFR-78 | **Deployment/environment parity** — Manual-control behavior is identical across dev/staging/prod environments. | Same contract version and semantics in all environments; verified via contract tests. |
| NFR-79 | **Reliability of command delivery** — Accepted operations are durably recorded before being reported as accepted. | 100% durability of accepted commands across single-node restart. |
| NFR-80 | **Observability** — Every operation emits structured metrics, logs, and traces keyed by operation id. | 100% of operations traceable end-to-end; metrics exposed for ack latency, terminal rate, conflict rate. |
| NFR-81 | **Localization/locale of operator surface** — Operator-facing messages, timestamps, and reason fields honor the operator's locale. | Timestamps in operator's timezone; UI strings internationalizable; RTL-ready. |
| NFR-82 | **Accessibility of the control surface** — Manual-control UI meets WCAG 2.1 AA. | Contrast ≥ 4.5:1, full keyboard operability, visible focus, screen-reader labels on all controls. |

#### User Stories

| ID | Story |
|---|---|
| US-61 | As an **operator**, I want to pause a running pipeline so that I can investigate an anomaly before more stages execute. |
| US-62 | As an **operator**, I want to resume a paused run so that work continues from where it stopped without re-running completed stages. |
| US-63 | As an **operator**, I want to cancel a run gracefully so that the current unit finishes but no further stages start. |
| US-64 | As an **operator**, I want to force-cancel a run so that a runaway stage is stopped immediately. |
| US-65 | As an **operator**, I want to retry a failed stage so that a transient failure does not require restarting the whole run. |
| US-66 | As an **approver**, I want to approve, reject, or request changes at a HIL gate so that the pipeline proceeds only with human sign-off. |
| US-67 | As an **operator**, I want to send clarifying input to a stage so that an agent acts on corrected or additional context. |
| US-68 | As an **operator**, I want to preview what a control action will do before I apply it so that I avoid unintended changes. |
| US-69 | As an **operator**, I want destructive actions to require confirmation so that I don't accidentally halt or cancel work. |
| US-70 | As an **operator**, I want to skip or force-advance a stage with a recorded reason so that I can unblock a run when policy permits. |
| US-71 | As an **admin**, I want to trigger an emergency halt so that all affected runs stop dispatching new work immediately. |
| US-72 | As a **compliance reviewer**, I want an immutable audit trail of every manual action so that I can reconstruct who did what and why. |
| US-73 | As an **operator**, I want to apply an operation to many runs at once so that I can manage a portfolio or run group efficiently. |
| US-74 | As an **operator**, I want to withdraw a manual input before it is consumed so that I can correct a mistake without disrupting the run. |
| US-75 | As an **operator**, I want real-time status on my submitted operation so that I know whether it succeeded and what state the run is now in. |

---

### Behaviour

**F-6.1 Command intake.** All manual operations enter through a single command surface. Each command carries: `operation_type`, `target` (run id / stage id / run-group id / portfolio scope / system), `scope`, `parameters`, `reason` (required for override, destructive, and halt classes), `idempotency_key`, and `actor` (resolved server-side from the authenticated principal, never trusted from the client).

**F-6.2 Preconditions and gate policy.** Before dispatch, the engine evaluates (a) target existence and current state, (b) entry-condition / gate policy for skip/advance operations, (c) operator authorization for the operation class, and (d) whether the operation is legal for the target's current state (e.g., resume requires `paused`; cancel requires a non-terminal run). A failed precondition yields a refusal with an itemized reason and no mutation.

**F-6.3 Preview path.** A preview resolves the same preconditions and returns the projected transitions and irreversibility class without dispatch. Previewed operations are audited as `previewed` and never mutate state.

**F-6.4 Dispatch and application.** Accepted operations are durably recorded, then applied against the authoritative run/stage resources. Pause/cancel take effect at safe checkpoints (graceful) or immediately (force). Retry re-enters entry-condition evaluation. HIL-gate decisions transition the run out of its gate-wait state. Emergency halt sets affected runs to `halted` and stops new dispatch.

**F-6.5 Feedback loop.** Each operation progresses through `pending → applied` or `refused` / `failed`, emits status to the operator's live surface and the run timeline, and terminates with a recorded resulting state.

**F-6.6 Rollback.** Withdrawable manual inputs (not yet consumed) can be withdrawn via a compensating command that restores the prior input/config revision and appends a compensating audit entry.

**F-6.7 Scheduling.** Deferred/scheduled operations are persisted with their trigger (time or condition), dispatched under the same authorization/audit rules when triggered, and cancellable before dispatch.

---

### Business rules

- BR-1: Every manual operation must be attributable to an authenticated principal and recorded in the immutable audit log before it is reported as accepted.
- BR-2: Role/permission checks are authoritative server-side; client-side hiding of controls is convenience only, never authorization.
- BR-3: Skip, force-advance, force-cancel, permanent withdrawal, and emergency halt require a non-empty reason and explicit confirmation.
- BR-4: Gate-policy rules determine which stages may be skipped/force-advanced; if policy forbids it, the operation is refused even for admins unless an admin-override policy explicitly permits it (and records that it was an override).
- BR-5: Historical attempts and audit entries are never mutated or deleted; retries and rollbacks create new records.
- BR-6: Idempotency keys are scoped per actor+operation type and honored for the operation's retention window.
- BR-7: Conflicting operations on the same target are serialized; a later conflicting command cannot displace an in-flight terminal command without an explicit operator choice.
- BR-8: Emergency halt stops *new* dispatch; already-running units follow graceful-cancel semantics unless escalated to force.
- BR-9: A terminal run (completed/cancelled/aborted/failed) rejects pause/resume/skip/retry until explicitly reopened (if reopen is supported).
- BR-10: Bulk operations report per-target outcomes; a partial failure never silently reports success.

---

### Validation

- V-1: `operation_type` must be one of the registered operation classes.
- V-2: `target` must reference an existing, resolvable run/stage/group/portfolio; unknown targets are refused.
- V-3: State legality — resume requires the target to be `paused`; pause requires a non-terminal state; cancel requires a non-terminal state; gate decision requires the target to be gate-waiting; retry requires a failed/aborted state.
- V-4: `reason` is required for override/destructive/halt classes and must be within length bounds.
- V-5: `idempotency_key` must be a non-empty string within length bounds when supplied.
- V-6: Parameter overrides must conform to the target parameter schema (type, range, allowed values).
- V-7: Scheduled operations must have a valid future time or a resolvable condition.
- V-8: Bulk targets must resolve to a non-empty set and pass authorization for each member.
- V-9: Actor identity must be resolvable and authorized for the operation class.

---

### Edge cases

- EC-1: A pause is requested exactly as the stage completes — the operation is applied to the next safe checkpoint or refused as "already advanced," with the actual outcome recorded.
- EC-2: A resume and a cancel race — serialized so that only one terminal transition occurs; the loser is refused with a conflict reason.
- EC-3: Retry requested on a non-retryable failure — refused with the non-retryable classification.
- EC-4: Duplicate submission of the same idempotency key after the first was applied — returns the original result, no second application.
- EC-5: Emergency halt issued while a force-cancel is in flight — halt stops new dispatch; the in-flight force-cancel completes and both are recorded.
- EC-6: Manual input submitted after the target stage has already consumed a prior input — the new input becomes the next revision and does not retroactively alter the consumed one.
- EC-7: Withdraw requested for an input already consumed — refused as non-withdrawable.
- EC-8: Bulk operation where some targets are already terminal — those targets are reported as skipped/refused, others are applied.
- EC-9: Scheduled operation whose target reaches a terminal state before the trigger — the operation is auto-cancelled and audited as such.
- EC-10: Operator loses authorization mid-flight (role changed) after dispatch but before application — authorization is re-checked at application; if now unauthorized, the operation is aborted and audited.
- EC-11: Target run is paused by an upstream automated policy while an operator also paused it — idempotent pause is a no-op with a recorded note.
- EC-12: Network retry delivers a command whose idempotency key was never persisted — a fresh operation is created only if no matching key exists within the retention window.

---

### Error handling

- EH-1: **Unauthenticated request** → `401`, no mutation, audited as refused.
- EH-2: **Unauthorized operation** → `403`, no mutation, audited with attempted operation and actor.
- EH-3: **Unknown/无效 target** → `404` with a structured body identifying the unresolvable target.
- EH-4: **Invalid state / precondition failure** → `409` with itemized failing preconditions and current target state.
- EH-5: **Validation failure** → `422` with field-level errors.
- EH-6: **Conflict (in-flight conflicting command)** → `409 conflict` with the conflicting operation id; operator may choose to queue.
- EH-7: **Duplicate idempotency key** → `200` returning the original operation result (not an error).
- EH-8: **Application failure after acceptance** → operation transitions to `failed` with a durable error record; operator sees the failure and can retry the operation itself.
- EH-9: **Downstream unavailability (run/stage service)** → command is queued with backoff up to its SLA window; if the window elapses, it is failed and audited.
- EH-10: **Partial bulk failure** → `207`-style multi-status reporting per target with an overall summary; no silent success.
- EH-11: **Preview of an illegal operation** → `200` preview describing why it would be refused, with no mutation.
- EH-12: **Emergency halt delivery failure to a subset of runs** → retried; any run not halted within the SLA is surfaced prominently as an unresolved halt and escalated.

---

### Acceptance criteria

- AC-1: An operator can pause a running run; the run reaches `paused` at the next safe checkpoint and no further stages start until resume.
- AC-2: An operator can resume a paused run; it continues from the recorded checkpoint without re-executing completed units.
- AC-3: An operator can gracefully cancel a run; the current unit finishes and the remainder is marked cancelled.
- AC-4: An operator can force-cancel a run; the current unit is aborted and the run is marked aborted, with the two outcome classes distinguishable in the timeline.
- AC-5: An operator can retry a failed stage; a new attempt is created, prior attempts remain, and entry conditions are re-evaluated.
- AC-6: An approver can Approve/Reject/Request-changes at a HIL gate; the decision is recorded with actor, time, reason, and artifact revision, and the run transitions accordingly.
- AC-7: An operator can submit manual input to a stage; the input is versioned, attributable, and readable by the stage on its next read.
- AC-8: A preview of any operation mutates nothing and returns the projected effect and irreversibility class.
- AC-9: Destructive operations cannot be applied without an explicit confirmation step.
- AC-10: Skip/force-advance obey gate policy; a policy-forbidden skip is refused, and a permitted skip records an "overridden" transition with a reason.
- AC-11: An authorized admin can trigger emergency halt; ≥ 99% of affected runs stop dispatching new work within 2 s.
- AC-12: Every accepted, refused, previewed, and rolled-back operation appears in the immutable audit log with actor, target, reason, idempotency key, outcome, and timestamps.
- AC-13: Re-submitting an operation with the same idempotency key returns the original result and does not double-apply.
- AC-14: Conflicting operations on the same target are serialized; a loser is refused with a conflict reason or queued by explicit choice.
- AC-15: A bulk operation reports per-target outcomes and never reports overall success when any target failed.
- AC-16: A withdrawable manual input can be withdrawn before consumption, restoring the prior revision and appending a compensating audit entry.
- AC-17: A scheduled operation triggers under the same authorization and audit rules and is cancellable before dispatch.
- AC-18: Unauthorized attempts are refused with `403` and audited; no mutation occurs.

---

### API behaviour

**Base:** control endpoints are versioned and consistent with the platform's resource conventions. All endpoints require an authenticated principal; all mutating endpoints accept an `Idempotency-Key` header.

| Method & Path | Purpose | Success | Key errors |
|---|---|---|---|
| `POST /v1/runs/{runId}/operations` | Submit a manual operation to a run (pause/resume/cancel/retry/skip/halt-scope) with body `{operation_type, reason?, parameters?, scope?}`. | `202 Accepted` with `operation_id` and `state: pending` | `401`, `403`, `404`, `409`, `422` |
| `POST /v1/runs/{runId}/stages/{stageId}/operations` | Submit a manual operation to a stage (pause/resume/cancel/retry/skip/force-advance). | `202 Accepted` with `operation_id` | `401`, `403`, `404`, `409`, `422` |
| `POST /v1/runs/{runId}/stages/{stageId}/input` | Submit manual input (free-form and/or structured) to a stage; creates a new input revision. | `201 Created` with `input_revision` | `401`, `403`, `404`, `409`, `422` |
| `DELETE /v1/runs/{runId}/stages/{stageId}/input/{revision}` | Withdraw an unconsumed manual input revision (compensating operation). | `200 OK` with restoring revision | `401`, `403`, `404`, `409` (already consumed) |
| `POST /v1/runs/{runId}/gates/{gateId}/decision` | Record a HIL-gate decision `{decision: approve|reject|request_changes, reason}`. | `200 OK` with resulting run state | `401`, `403`, `404`, `409`, `422` |
| `POST /v1/operations:preview` | Dry-run an operation; returns projected transitions and irreversibility class; no mutation. | `200 OK` with preview body | `401`, `403`, `404`, `422` |
| `GET /v1/operations/{operationId}` | Fetch operation status and outcome. | `200 OK` with `{state: pending|applied|refused|failed, result, target}` | `401`, `403`, `404` |
| `POST /v1/operations/{operationId}:cancel` | Cancel a pending/scheduled operation before it applies. | `200 OK` with updated state | `401`, `403`, `404`, `409` |
| `POST /v1/halt` | Emergency halt (system- or project-scoped) `{scope, reason}`. | `202 Accepted` with `halt_id` | `401`, `403`, `422` |
| `POST /v1/runs:bulkOperations` | Apply an operation to a set/portfolio/run-group scope; returns per-target outcomes. | `207 Multi-Status` body with per-target results | `401`, `403`, `404`, `422` |
| `POST /v1/operations:schedule` | Schedule a deferred operation `{operation, trigger: {at|condition}}`. | `201 Created` with `scheduled_operation_id` | `401`, `403`, `422` |
| `GET /v1/runs/{runId}/operations` | List operations and their states for a run (paginated). | `200 OK` with page of operations | `401`, `403`, `404` |

**Cross-cutting API behaviour**

- API-1: Mutating calls without a valid `Idempotency-Key` on retryable operations are still accepted but flagged; identical keys within the retention window return the original result.
- API-2: All error bodies follow a single structured shape: `{code, message, target?, failing_preconditions?, field_errors?}`.
- API-3: Accepted operations are durably persisted before the `202/201` response is returned (NFR-79).
- API-4: Rate/authorization failures are audited with actor and operation class, never leaking other operators' internals.
- API-5: Bulk and halt responses use multi-status semantics to convey partial outcomes explicitly.
- API-6: Every response for an operation carries the operation id, which is stable and usable in `GET /v1/operations/{operationId}` and in the audit trail.

---

**Priority:** must-have (core manual-input and operation-control surface). Sub-capabilities `skip/force-advance`, `parameter override`, `preview/dry-run`, and `bulk operations` are should-have; `scheduled/deferred operations` is nice-to-have. No sub-capability is deferred or reduced — all are specified above and available for the operator surface.
