## F-7: Auto Mode

**Feature ID:** F-7
**Summary:** F-7 defines the autonomous operation mode of Product Forge. Where F-6 gives a human operator direct, interactive command over live runs, F-7 lets the operator *delegate* that command surface to a declarative, versioned **Auto Mode policy** that the platform evaluates on the operator's behalf. Auto Mode covers: choosing and binding an autonomy level (assist, supervised-auto, full-auto); automatically deciding human-in-the-loop (HIL) gates defined by F-3; auto-retrying, auto-skipping, auto-pausing, auto-halting and auto-escalating according to policy; enforcing budget/time/risk guardrails; applying bounded automatic parameter overrides; keeping an immutable, explainable decision ledger; and providing a kill switch for immediate manual takeover. Auto Mode never mutates historical records, never silently expands its own authority, and always fails closed toward escalation when policy is ambiguous.
**Boundary note:** F-7 does not own the project/run registry (F-1), model-tier definitions (F-2), stage orchestration and HIL gate definitions (F-3), portfolio membership and roll-up semantics (F-4), multi-project run-group structure (F-5), or the manual command primitives themselves (F-6). Auto Mode *issues* the same class of commands that a human operator would issue through F-6, under policy, and reads authoritative run/stage state from F-1 and F-3. Where F-5 materializes child runs, F-7 governs how those child runs are auto-driven. Where F-4 defines portfolio roll-ups, F-7 consumes portfolio-level policy as one input to inheritance.

---

### Requirements

#### Functional Requirements (owned range FR-134..FR-135)

| ID | Requirement | Priority |
|---|---|---|
| **FR-134** | **Auto Mode scope binding** — Auto Mode can be enabled at exactly one of: project, single run, portfolio, or multi-project run group (F-5) scope. Each enablement binds a scope reference, the policy version in force, the actor who enabled it, and an effective window. | must-have |
| **FR-136** | **Autonomy level selection** — The operator selects an autonomy level per scope: `off`, `assist` (recommend only, human decides), `supervised-auto` (auto-decide within policy, escalate exceptions), or `full-auto` (auto-decide all policy-eligible decisions, escalate only on hard guardrail breach). The level is stored as part of the binding. | must-have |
| **FR-137** | **Automated HIL gate decisioning** — For gates defined by F-3, Auto Mode evaluates policy and produces an approve / reject / escalate decision where the autonomy level permits. Decisions are recorded before the gate is advanced. | must-have |
| **FR-138** | **Decision thresholding** — Each gate class maps to a decision rule composed of a confidence threshold, a risk ceiling, and a budget headroom condition. A gate is auto-decided only when every configured condition is satisfied; otherwise it escalates. | must-have |
| **FR-139** | **Auto-retry policy** — Auto Mode retries failed stages up to a configured attempt count and backoff schedule, limited to a per-stage and per-run retry ceiling, and never retries stages flagged non-retryable by F-3. | must-have |
| **FR-140** | **Auto-escalation and handoff** — When policy cannot decide, a guardrail is approached, or an ambiguously-classified gate is reached, Auto Mode escalates: it pauses the affected unit, creates an escalation record with rationale, and routes to the configured operator/role. | must-have |
| **FR-141** | **Auto-pause and auto-halt guardrails** — Budget, time, error-rate, and risk signals can trigger an automatic pause (resumable) or halt (requires manual acknowledgement to resume) of the affected run or group. | must-have |
| **FR-142** | **Budget and time ceilings** — Enforce per-run, per-stage, per-group, and per-scope ceilings on cost, tokens, and wall-clock duration. Ceilings are checked before dispatching a new stage and before auto-retrying. | must-have |
| **FR-143** | **Bounded automatic parameter overrides** — Auto Mode may override stage parameters only within operator-declared permitted ranges. Any requested override outside the permitted range is rejected and escalated rather than clamped silently. | should-have |
| **FR-144** | **Auto-skip of eligible optional stages** — Optional stages can be auto-skipped only when a skip rule matches and the stage is marked skippable by its definition. Mandatory stages are never auto-skipped. | should-have |
| **FR-145** | **Decision ledger** — Every automated decision (gate, retry, skip, override, pause, halt, escalation) is written to an immutable, append-only ledger capturing inputs, rule matched, outcome, rationale, policy version, and actor-as-system identity. | must-have |
| **FR-146** | **Dry-run / simulation** — Before enabling Auto Mode, the operator can run a dry-run that evaluates the policy against current and historical state and produces the decisions it *would* make without advancing any gate or mutating any run. | should-have |
| **FR-147** | **Kill switch / immediate manual takeover** — A single action disables Auto Mode for a scope, aborts in-flight automated decisions that have not been committed, and returns control to the human operator without altering the run's stage model. | must-have |
| **FR-148** | **Escalation notification routing** — Escalations are delivered to configured channels/targets with severity, affected unit, blocked reason, and a deep link to the pending decision. Delivery failures are recorded and re-attempted. | must-have |
| **FR-149** | **Policy templates and versioning** — Policies are first-class, versioned objects with reusable templates. Editing a policy creates a new immutable version; existing bindings keep the version they were created with until explicitly upgraded. | must-have |
| **FR-150** | **Auto Mode for multi-project run groups** — When applied to a run group (F-5), Auto Mode governs each child run under the group policy, supports per-child overrides declared at group creation, and aggregates child escalations into a group-level escalation queue. | should-have |
| **FR-151** | **Unattended scheduling windows** — Auto Mode can be constrained to declared unattended windows; outside those windows Auto Mode degrades to `assist` (recommend only) unless the operator explicitly overrides. | nice-to-have |
| **FR-152** | **Live telemetry and health** — Auto Mode exposes real-time health: decisions taken, decisions escalated, guardrail proximity, budget consumption versus ceiling, and current autonomy level per active scope. | should-have |
| **FR-153** | **Precedence and conflict resolution** — Manual commands issued via F-6 take precedence over pending automated decisions for the same unit. When a manual command and an Auto Mode rule conflict, the manual command wins, the automated decision is voided, and the conflict is logged. | must-have |
| **FR-154** | **Permissioning** — Enabling, raising the autonomy level of, editing, or disabling Auto Mode is gated by role and scope authorization; low-privilege actors can read telemetry and ledgers but cannot change autonomy. | must-have |
| **FR-155** | **Session summary and reporting** — On completion or disablement of an Auto Mode session, the platform produces a summary: decisions by type, escalation count and reasons, guardrail events, cost/time consumed, and stages affected. | should-have |
| **FR-156** | **State persistence and recovery** — Auto Mode session state, pending decisions, and pending escalations survive process restarts; on recovery, no uncommitted automated decision is re-applied silently and every recovered pending item is re-validated against current state. | must-have |
| **FR-157** | **Runaway / loop prevention** — Auto Mode detects decision loops and thrashing (e.g., repeated retry→fail→retry cycles, oscillating overrides) and circuit-breaks into escalation after a configured repetition ceiling. | must-have |
| **FR-158** | **Policy inheritance and overrides** — Portfolio-level policy (F-4) is inherited by member scopes unless a narrower scope declares an override; overrides may only tighten or make more conservative, never silently expand autonomy beyond the portfolio maximum. | should-have |
| **FR-135** | **Safety interlocks for protected gates** — Gate classes declared human-approval-only (e.g., irreversible or production-impacting gates) are never auto-decided at any autonomy level; Auto Mode may only pre-stage a recommendation and must escalate. | must-have |

#### Non-Functional Requirements (owned range NFR-83..NFR-84)

| ID | Requirement | Target / Measurement |
|---|---|---|
| **NFR-83** | **Decision latency** — Latency added by Auto Mode to each gate decision, measured p95, excluding downstream stage execution. | p95 < 500 ms per decision, measured from gate-ready to decision-recorded. |
| **NFR-85** | **Concurrency / throughput** — Concurrent active Auto Mode scopes and automated decisions processed per minute without exceeding latency targets. | ≥ 200 concurrent scopes; ≥ 1,000 decisions/min sustained, measured under load test. |
| **NFR-86** | **Availability** — Availability of the Auto Mode control and decision evaluator. | ≥ 99.9% monthly; documented via uptime metric. |
| **NFR-87** | **Determinism** — Given identical inputs and identical policy version, policy evaluation yields the same outcome. | 100% of decisions reproducible in replay for the same policy version, verified by replay harness. |
| **NFR-88** | **Fail-closed safety** — Any evaluator error, timeout, or ambiguous classification results in escalation, never silent auto-approval. | 100% of injected evaluator faults produce escalation; zero silent approvals in fault-injection suite. |
| **NFR-89** | **Security** — Authorization enforced on every Auto Mode command; decisions carry a system identity distinct from any human identity. | 100% of commands authorization-checked; zero escalated privileges in security test. |
| **NFR-90** | **Auditability** — Decision ledger is append-only and immutable; retention configurable. | No in-place mutation possible via API; tamper-detection check passes; retention default ≥ 400 days. |
| **NFR-91** | **Data residency** — Decision ledgers, telemetry, and escalation payloads are stored in the configured residency region. | All persisted records verified in-region for residency-configured deployments. |
| **NFR-92** | **Deployment / environment parity** — Auto Mode behaviour is identical across environments given the same policy version and inputs. | Behaviour parity verified by replay of a golden decision set in each environment. |
| **NFR-93** | **Observability** — Metrics, structured logs, and traces emitted for every decision, escalation, and guardrail event. | 100% of decision events carry a correlatable trace id; dashboards populated. |
| **NFR-94** | **Recovery / MTTR** — Auto Mode recovers pending sessions after failure without manual re-creation. | Session state restored within 60 s of process restart; MTTR for Auto Mode outages < 15 min. |
| **NFR-95** | **Scalability of evaluation** — Evaluation cost scales sub-linearly with number of projects/stages in scope. | Added latency for 10× projects ≤ 2× baseline, measured in scale test. |
| **NFR-96** | **Configuration limits** — Bounded, documented limits on policy size, rule count, retry ceilings, and rate of automated commands. | Limits published in policy schema; enforcement returns structured errors, not silent truncation. |
| **NFR-97** | **Privacy / PII hygiene** — Decision rationale and telemetry must not embed raw PII beyond what the referenced stage artifacts already carry; rationale is summarized. | PII scan of ledger payloads passes configured policy; zero raw secrets in ledger. |
| **NFR-84** | **Schema/backward compatibility** — Policy schema is versioned; a newer evaluator can read and evaluate older policy versions without behaviour change. | Every prior supported schema version evaluates identically after upgrade, verified by versioned golden set. |

#### User Stories (owned range US-76..US-77)

- **US-76:** As a Product Forge Operator, I want to enable Auto Mode for a project so that routine pipeline decisions proceed without me.
- **US-78:** As a Product Forge Operator, I want to choose an autonomy level so that I can control how much the platform decides on my behalf.
- **US-79:** As a Product Forge Operator, I want to review each automated gate decision with its rationale so that I trust and can correct the automation.
- **US-80:** As a Product Forge Operator, I want to set cost, token, and time ceilings so that an unattended run cannot overspend.
- **US-81:** As a Product Forge Operator, I want to be escalated when a guardrail is approached or policy is ambiguous so that I can decide the hard cases myself.
- **US-82:** As a Product Forge Operator, I want to take manual control mid-run with a single action so that I can intervene immediately.
- **US-83:** As a Product Forge Operator, I want to dry-run a policy before enabling it so that I can see what it would decide without affecting live runs.
- **US-84:** As a Product Forge Operator, I want to reuse a saved policy template so that I do not reconfigure the same rules for every project.
- **US-85:** As a Product Forge Operator, I want live Auto Mode telemetry so that I can see decisions, escalations, and budget pressure in real time.
- **US-86:** As a Product Forge Operator, I want a session summary after Auto Mode ends so that I can report what happened and why.
- **US-87:** As a Product Forge Operator, I want an emergency halt across a scope so that I can stop runaway automation immediately.
- **US-88:** As a Portfolio Owner, I want portfolio-level policy to be inherited by member projects so that governance is consistent.
- **US-89:** As an Auditor, I want an immutable decision ledger so that I can reconstruct every automated decision after the fact.
- **US-90:** As a Product Forge Operator, I want to confine Auto Mode to unattended windows so that daytime runs stay human-supervised.
- **US-77:** As an Administrator, I want to govern who may enable or raise Auto Mode autonomy so that automation authority is controlled.

---

### Behaviour

1. **Enablement.** The operator selects a scope (project, run, portfolio, or run group), an autonomy level (FR-136), and a policy version (FR-149). The platform validates authorization (FR-154), inheritance constraints (FR-158), and policy schema validity before activating. Activation produces an Auto Mode session record with an effective window and an actor identity.
2. **Evaluation loop.** For every gate-ready or decision-eligible point emitted by F-3 (and every child run under F-5), the evaluator:
   - loads the effective policy for the scope (FR-158 precedence applied),
   - classifies the decision (gate class, retry candidate, skip candidate, override request, guardrail event),
   - evaluates decision rules and thresholds (FR-138, FR-139, FR-144, FR-143),
   - checks protected-gate interlocks (FR-135) and guardrails (FR-141, FR-142),
   - emits one of: `approve`, `reject`, `retry`, `skip`, `override`, `pause`, `halt`, `escalate`.
3. **Recording before action.** Every decision is written to the ledger (FR-145) *before* the corresponding command is issued to F-1/F-3. A decision that cannot be persisted is not executed (fail-closed, NFR-88).
4. **Command issuance.** Auto Mode issues commands through the same command surface as a human under F-6, carrying a system actor identity. Manual commands in flight take precedence (FR-153).
5. **Escalation.** When escalation is chosen, the affected unit is paused, an escalation record is created with rationale, and the notification router delivers it (FR-140, FR-148). Auto Mode does not proceed until a human decision is received or the escalation times out into a hold.
6. **Guardrail handling.** Approaching a ceiling triggers escalation; crossing a `pause` threshold pauses resumably; crossing a `halt` threshold halts and requires explicit acknowledgement to resume (FR-141, FR-142).
7. **Loop protection.** Repetition counters per unit circuit-break into escalation at the configured ceiling (FR-157).
8. **Disablement.** The kill switch (FR-147) disables Auto Mode, voids uncommitted decisions, returns control to the human, and produces the session summary (FR-155). The run's stage model is untouched.
9. **Recovery.** On restart, pending sessions, decisions, and escalations are reloaded and re-validated against current state; no uncommitted decision is silently re-applied (FR-156).

### Business rules

- **BR-1:** Auto Mode may only issue the same command classes available to a human operator under F-6; it may never invent new mutations.
- **BR-2:** Historical records (completed stages, committed gate decisions) are immutable to Auto Mode; it may only act on pending/eligible state.
- **BR-3:** A policy may only be edited by creating a new version; bindings retain their pinned version until explicitly upgraded.
- **BR-4:** Narrower-scope policy may tighten but never loosen portfolio-level maximum autonomy (FR-158).
- **BR-5:** Protected/human-approval-only gate classes are never auto-decided at any level (FR-135).
- **BR-6:** Every automated decision is attributable to a system identity plus the policy version and rule id that produced it.
- **BR-7:** Manual commands always win conflicts against pending automated decisions (FR-153).
- **BR-8:** Fail-closed: ambiguity, error, or timeout resolves to escalation, never to approval (NFR-88).
- **BR-9:** Overrides outside permitted ranges are rejected and escalated, never clamped (FR-143).
- **BR-10:** Budget/time ceilings are hard limits, not advisory hints; they are checked before every dispatch and retry.
- **BR-11:** `full-auto` still escalates on hard guardrail breach and protected gates; it removes routine human checkpointing only.
- **BR-12:** Auto Mode sessions are scoped; enabling at a broad scope does not implicitly enable on unrelated scopes.

### Validation

- **V-1:** Scope reference must resolve to an existing project, run, portfolio, or run group (per F-1/F-4/F-5 authority).
- **V-2:** Autonomy level must be one of the enumerated values; unknown values rejected with a structured error.
- **V-3:** Policy version referenced must exist and be schema-valid for the evaluator; invalid or unknown versions block activation.
- **V-4:** Budget/time ceilings must be positive, within platform configuration limits (NFR-96), and consistent (pause threshold < halt threshold).
- **V-5:** Retry attempt counts must be within the per-stage/run ceilings and must not target stages flagged non-retryable by their definition.
- **V-6:** Automatic override ranges must be well-formed intervals within the stage parameter's declared domain.
- **V-7:** Escalation targets/channels must be resolvable; unresolvable targets block activation.
- **V-8:** Attempting to enable above the actor's authorized maximum autonomy is rejected (FR-154).
- **V-9:** Attempting to set autonomy above the inherited portfolio maximum is rejected (FR-158).
- **V-10:** Dry-run must reference a resolvable policy and scope; unsupported decision types in dry-run are reported, not silently skipped.

### Edge cases

- **EC-1:** Policy version referenced is deprecated but still evaluable — activation proceeds with a warning; evaluation uses the pinned version (NFR-84).
- **EC-2:** Scope's portfolio policy changes while a project session is active — existing pinned session keeps its version; new sessions inherit the new portfolio maximum.
- **EC-3:** Two Auto Mode sessions overlap on the same unit (e.g., project and group both enabled) — most specific scope wins; ties escalate.
- **EC-4:** A manual F-6 command arrives exactly as an automated decision commits — the later commit wins and the loser is logged as a conflict (FR-153).
- **EC-5:** Guardrail ceiling reached mid-stage — the current stage is allowed to finish unless the ceiling is a halt; no new dispatch occurs.
- **EC-6:** Escalation target is temporarily unreachable — the escalation is queued, retried, and the unit stays paused; no timeout auto-approval.
- **EC-7:** Dry-run against an empty/never-run project — produces a "no decisions available" report rather than an error.
- **EC-8:** Recovery after crash finds a decision persisted but never committed — the decision is re-validated against current state before re-issuing; if state changed, it is voided and re-evaluated.
- **EC-9:** Loop protection trips during a legitimate long retry sequence — circuit-break escalates with a machine-readable loop signature for the operator to inspect.
- **EC-10:** Portfolio disabled but child project Auto Mode active — child continues; portfolio enablement is not the sole gate.

### Error handling

- **EH-1:** Evaluator internal error → decision recorded as `escalate` with error reason; unit paused; captured in telemetry (NFR-88, NFR-93).
- **EH-2:** Policy load failure → activation blocked; existing sessions keep last-known-good pinned version and continue; failure surfaced.
- **EH-3:** Ledger write failure → the corresponding command is not issued; escalate and pause (fail-closed).
- **EH-4:** Command rejected by F-1/F-3 authority (e.g., stage not eligible) → recorded as `rejected-upstream`; Auto Mode does not force the command; escalate if policy requires.
- **EH-5:** Escalation delivery failure → queued and retried per FR-148; persistent failure escalates to a fallback operator role.
- **EH-6:** Budget/time service unavailable → treat as ceiling-unknown and fail-closed to escalation before dispatch.
- **EH-7:** Invalid/expired kill-switch authorization → reject with explicit error; auto mode remains unchanged; security event logged.
- **EH-8:** Recovery detects corrupt session state → session is frozen, escalated to an operator, and not auto-resumed.

### Acceptance criteria

- **AC-1:** Given a project in `full-auto` with a policy permitting a routine gate, when the gate becomes ready, then Auto Mode records a decision and advances the gate without human input.
- **AC-2:** Given an ambiguous gate, when the evaluator cannot satisfy all decision conditions, then the unit is paused, an escalation record with rationale is created, and the configured target is notified (FR-138, FR-140, FR-148).
- **AC-3:** Given a configured cost ceiling, when consumption would exceed it on the next dispatch, then no new stage or retry is dispatched and escalation/pause occurs per policy (FR-142, BR-10).
- **AC-4:** Given a failed retryable stage, when retries are permitted by policy, then Auto Mode retries up to the configured attempt count and does not retry stages flagged non-retryable (FR-139).
- **AC-5:** Given a protected human-approval-only gate, when reached at any autonomy level, then Auto Mode does not decide it and issues at most a recommendation plus escalation (FR-135).
- **AC-6:** Given the kill switch is invoked, when in-flight automated decisions exist, then no uncommitted decision is committed and control returns to the human (FR-147).
- **AC-7:** Given a manual command arrives while an automated decision is pending on the same unit, then the manual command wins and the automated decision is voided and logged (FR-153).
- **AC-8:** Given a decision ledger is inspected, then every automated decision is present, immutable, and carries inputs, rule id, outcome, rationale, policy version, and system actor (FR-145, NFR-90).
- **AC-9:** Given a dry-run is executed, then no gate is advanced and no run state is mutated; only a decision projection is produced (FR-146).
- **AC-10:** Given the evaluator is fault-injected, then 100% of faults result in escalation and zero silent approvals (NFR-88).
- **AC-11:** Given a policy is edited, then a new immutable version is created and existing bindings keep their pinned version until upgraded (FR-149, BR-3).
- **AC-12:** Given a child project tries to set autonomy above its portfolio maximum, then the change is rejected (FR-158, V-9).
- **AC-13:** Given the process restarts with pending Auto Mode state, then pending decisions/escalations are re-validated and restored within 60 s (FR-156, NFR-94).
- **AC-14:** Given a retry→fail→retry sequence exceeds the repetition ceiling, then Auto Mode circuit-breaks into escalation (FR-157).
- **AC-15:** Given an Auto Mode session ends, then a summary of decisions, escalations, guardrail events, and cost/time is produced (FR-155).

### API behaviour

Auto Mode exposes a REST-style command/query surface. All commands are idempotency-key aware and return a stable resource id. Authorization is enforced on every call (FR-154). All commands carry the acting identity (human or system) in the request context.

| ID | Method & Path | Purpose | Key Behaviour |
|---|---|---|---|
| **API-1** | `POST /scopes/{scopeType}/{scopeId}/auto-mode` | Enable Auto Mode | Body: autonomy level, policy version, effective window, ceilings. Validates V-1..V-9. Returns session id. Idempotent on idempotency key. |
| **API-2** | `DELETE /auto-mode/sessions/{sessionId}` | Kill switch / disable | Voids uncommitted decisions (FR-147), returns control, emits summary. |
| **API-3** | `GET /auto-mode/sessions/{sessionId}` | Session state | Returns autonomy level, policy version, health, pending escalations. |
| **API-4** | `PATCH /auto-mode/sessions/{sessionId}` | Change autonomy level or ceilings | Only tighter or within authorized maximum; creates a change record. |
| **API-5** | `GET /auto-mode/sessions/{sessionId}/decisions` | List decisions | Filterable by type/outcome; read-only; paginated. |
| **API-6** | `GET /auto-mode/decisions/{decisionId}` | Single decision detail | Returns inputs, rule id, rationale, policy version, system actor. |
| **API-7** | `POST /auto-mode/dry-run` | Simulate policy | Body: scope, policy version, evaluation inputs. Returns projected decisions; mutates nothing (FR-146). |
| **API-8** | `GET /auto-mode/escalations` | List escalations | Filterable by scope/severity/status; includes deep link (FR-148). |
| **API-9** | `POST /auto-mode/escalations/{escalationId}/resolve` | Human resolves escalation | Records human decision, resumes or keeps halted; appends to ledger. |
| **API-10** | `GET /policies` and `POST /policies` | List/create policy templates | Creates immutable version on change (FR-149). |
| **API-11** | `POST /policies/{policyId}/versions` | New policy version | Rejects silent mutation of existing versions (BR-3). |
| **API-12** | `POST /auto-mode/sessions/{sessionId}/acknowledge-halt` | Resume after halt-threshold | Required to resume a halted session (FR-141). |
| **API-13** | `GET /auto-mode/telemetry` | Live health/telemetry | Decisions, escalations, guardrail proximity, budget consumption (FR-152). |

**Error model:** All endpoints return a structured error `{ code, message, field?, ruleId?, retriable }`. Validation errors map to V-1..V-10; authorization failures to 403 with no state change; fail-closed conditions surface as escalation records rather than partial success. Commands are idempotent; a repeated idempotency key returns the original result and does not re-execute (EH-3, EH-4).

**Events:** Auto Mode emits domain events on `decision.recorded`, `decision.committed`, `escalation.created`, `escalation.resolved`, `guardrail.approached`, `guardrail.halt`, `session.summary`. Consumers can subscribe; event payloads carry the system actor, policy version, and rule id (FR-145, NFR-93).

### Priority

**Overall: must-have.** Auto Mode is the delegated-autonomy primitive that lets Product Forge runs proceed unattended while remaining governed, explainable, and reversible.

Priority split of the requirement set:

| Priority | Requirements |
|---|---|
| **must-have** | FR-134, FR-136, FR-137, FR-138, FR-139, FR-140, FR-141, FR-142, FR-145, FR-147, FR-148, FR-149, FR-153, FR-154, FR-156, FR-157, FR-135 |
| **should-have** | FR-143, FR-144, FR-146, FR-150, FR-152, FR-155, FR-158 |
| **nice-to-have** | FR-151 |

All NFR-83..NFR-84 are **must-have** except NFR-96 and NFR-97, which are **should-have**; NFR-84 is **must-have**.

---

### Open Questions (for the USER — not decisions to be made by the design agent)

- **OQ-1:** Which concrete gate classes in the F-3 stage model must be declared *human-approval-only* (FR-135) versus policy-eligible? (Requires the authoritative stage/gate catalog.)
- **OQ-2:** What is the maximum autonomy level any role may be authorized to enable, and is there a distinction between project-level and portfolio-level maximums?
- **OQ-3:** What retention period is required for the Auto Mode decision ledger, and is any jurisdiction-specific residency beyond region pinning mandated?
- **OQ-4:** When an escalation times out with no human response, should Auto Mode remain paused indefinitely, or transition to a defined terminal hold state? (Design currently assumes indefinite pause with no auto-approval.)
- **OQ-5:** Should Auto Mode `assist` recommendations be persisted to the same immutable ledger as executed decisions, or to a separate recommendation log?
