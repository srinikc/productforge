## F-12: Test Management

**Feature ID:** F-12

**Summary:** F-12 covers the test management layer of Product Forge: the registry of test cases and their versioned definitions, the composition of those cases into suites and plans, the binding of plans to pipeline stages and projects, the execution of tests (on demand, scheduled, or as a governed step of a pipeline stage driven by F-3), the capture of deterministic outcomes and evidence, the evaluation of plan-level quality gates that stage advancement consumes, coverage tracking over pipeline artifacts, regression and flakiness management, waiver/approval, reporting, and the immutable audit trail. F-12 owns the *test domain* — what a test is, what it asserts, when it runs, what its outcome means, and whether a governed quality gate passes — and it publishes a stable API of test definitions, test runs, results, and gate verdicts that other features consume.

**Boundary note:** F-12 does not own project/run records (F-1), model-tier definitions (F-2), stage orchestration, stage advancement, or HIL gate definitions (F-3), portfolio membership and roll-up semantics (F-4), multi-project run-group structure (F-5), manual command semantics (F-6), auto-mode policy/ledger (F-7), the shared dashboard UX component system (F-8), conversational reasoning/grounding (F-9), voice I/O (F-10), or the mobile companion surface (F-11). F-12 reads the authoritative stage/run/artifact surfaces published by F-1 and F-3, and it *emits* gate verdicts and test telemetry that F-3 consumes to advance, block, or escalate a stage; it never advances a stage itself. Where F-12 produces a signal that a human must act on, the *command* semantics belong to F-6, the *notification rendering* to F-8/F-11, and the *explanation* to F-9.

### Requirements

#### Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| FR-239 | Test case registry | Create, read, list, update, archive, restore, and permanently delete test cases. Each test case carries a stable id, name, description, type (unit / integration / end-to-end / agent-evaluation / regression / safety / manual), owner, tags, status, and current revision pointer. |
| FR-240 | Immutable test definition versioning | Every edit to a test definition produces a new immutable revision; running test runs pin an exact revision. Historical outcomes always reference the revision that produced them and are never rewritten. |
| FR-241 | Assertion and step model | Define an ordered set of steps per test case; each step declares an assertion type, target (artifact, field, schema, metric, or behaviour), expected value or predicate, tolerance, and failure message. Step results roll up into a test outcome by a declared roll-up rule. |
| FR-242 | Test suite composition | Create named, versioned suites that group and order test cases (including nested suites), with suite-level tags, preconditions, and a declared execution policy. Changing a suite produces a new suite revision. |
| FR-243 | Test plan binding | Bind a suite (at a pinned revision) to a project and/or a pipeline stage to form a test plan that declares scope, required environment, retry policy, gate criteria, and blocking behaviour. A project may have multiple plans; a stage may consume one blocking plan and any number of advisory plans. |
| FR-244 | Test execution trigger | Trigger a test run on demand, scheduled, or as a governed step of a pipeline stage (dispatched by F-3 stage orchestration). Accept an optional idempotency key, run label, revision pin, and parameter set; return a stable test-run identifier immediately. |
| FR-245 | Artifact and agent-output evaluation | Evaluate artifacts and agent outputs published by pipeline stages (per F-1/F-3) against assertions: schema conformance, required-field presence, content predicates, quality thresholds, and declared safety constraints. F-12 reads artifacts, never mutates them. |
| FR-246 | Result capture and outcome model | Record per-step and per-test outcomes (passed / failed / errored / skipped / inconclusive / flaky) with duration, captured evidence (logs, diffs, artifact references), and the exact revision and parameter set executed. Results are immutable once written. |
| FR-247 | Quality gate evaluation | Evaluate a plan's pass criteria (must-pass sets, maximum failures, coverage minimums, and blocking thresholds) and emit a single deterministic gate verdict (`pass` / `fail` / `waived` / `inconclusive`) that F-3 stage advancement consumes. F-12 emits the verdict; F-3 decides the transition. |
| FR-248 | Coverage tracking | Track which pipeline stages, agents, artifacts, and declared behaviours are covered by at least one passing test; compute coverage percentages and enumerate uncovered surfaces for a project or portfolio. |
| FR-249 | Regression suite management | Designate suites as regression suites, schedule them (e.g., cadence or event-triggered), and compare each regression run against a named baseline, reporting newly passing, newly failing, and newly flaky tests. |
| FR-250 | Flakiness detection and quarantine | Statistically detect flaky tests from historical outcomes, flag them, and optionally quarantine them so they are excluded from hard gate criteria while remaining fully visible and reported. Quarantine is reversible and audited. |
| FR-251 | Test retry policy | Configure retry count, backoff, and retry-on-outcome set per test, suite, or plan; retries are recorded as distinct attempts within the same test run, and the final outcome follows a declared rule (e.g., pass-on-any-pass, fail-on-any-fail). |
| FR-252 | Fixture and test-data management | Register, version, and bind fixtures, factories, and datasets to tests; declare seeding and reset semantics; guarantee each execution starts from a declared, reproducible input state. |
| FR-253 | Environment binding | Bind test plans to declared environments and required capabilities; refuse to start a run when declared environment requirements are unmet, returning an itemized unmet-requirement report. |
| FR-254 | Parameterized and table-driven tests | Define parameter sets for a test case; expand them into individually identified executions within a test run, each with its own outcome, and aggregate them under a declared roll-up rule. |
| FR-255 | Test run history and trends | Retain immutable test-run records and provide pass rate, duration, flake rate, and coverage trends over time, scoped by test, suite, plan, project, or portfolio. |
| FR-256 | Manual test execution and attestation | Allow an authorized operator to execute a manual checklist test, record pass/fail per item with attached evidence, and attest the result with identity, time, and (where required) a reason. |
| FR-257 | Waiver and approval | Allow a privileged operator to waive a specific failing test or an entire failing gate with a required reason, scope, and expiry; waived failures remain visible and the waiver is bound to the exact revisions it waives. |
| FR-258 | Reporting and export | Produce per-run, per-suite, per-plan, per-project, and per-portfolio test reports and export them in structured, machine-readable formats; reports reflect only immutable recorded outcomes. |
| FR-259 | Test notifications | Emit notification events for gate-blocking failures, regressions against baseline, flake detection, quarantine changes, and waiver expiry, using the notification surfaces published by F-8 and F-11. F-12 emits events; those features render them. |
| FR-260 | Authorization and scoping | Enforce role-based permissions for creating, editing, running, waiving, quarantining, and deleting tests and plans; all reads and writes are scoped to the caller's authorized projects and portfolios. |
| FR-261 | Audit trail | Every mutation of test definitions, suites, plans, executions, results, waivers, and quarantines produces an immutable, timestamped, attributed audit event that cannot be edited or deleted. |
| FR-262 | Defect linking and triage | Link a failing outcome to a defect/ticket reference and a triage state (untriaged / triaged / accepted-risk / won't-fix); surface counts of untriaged gate-blocking failures. |
| FR-263 | Test management API | Publish a stable, versioned API for test definitions, suites, plans, test runs, results, coverage, and gate verdicts, consumed by F-3 (stage gating), F-6 (operator-initiated runs), F-9 (grounded explanation), and F-11 (mobile read surface). |

#### Non-Functional Requirements

| ID | Requirement | Target / Measurement |
|---|---|---|
| NFR-149 | Trigger responsiveness | A test-run trigger returns a stable run id within 500 ms at p95, independent of eventual execution duration. |
| NFR-150 | Result ingestion throughput | The platform ingests and persists at least 10,000 individual test-step results per second per active project without loss. |
| NFR-151 | Expansion performance | A fully parameterized plan expanding to 5,000 executions is materialized within 2 s. |
| NFR-152 | Scalability | Support at least 100,000 test cases and 1,000,000 recorded results per project with no degradation of query or gate-evaluation latency. |
| NFR-153 | Availability | The test management read and gate API is available 99.9% per calendar month; gate evaluation degrades to the last known verdict if the API is unavailable, never to silent pass. |
| NFR-154 | Durability and retention | Test results and gate verdicts are immutable and retained for at least 24 months by default, with configurable per-project longer retention. |
| NFR-155 | Security | Role-based authorization on every endpoint; secrets and credentials never appear in test definitions, payloads, or logged evidence; all access is audited. |
| NFR-156 | Data residency | Test definitions, fixtures, results, and evidence are stored and processed in the project's configured region and never cross it without explicit, audited configuration. |
| NFR-157 | Deployment and migrations | Test management supports blue/green deployment; schema migrations are backward compatible and never invalidate previously recorded results or verdicts. |
| NFR-158 | Determinism | Re-running the same test revision against the same declared inputs and fixture versions yields the same outcome, except where the test is explicitly marked flaky-prone; determinism attestations are per revision. |
| NFR-159 | Isolation | Test runs execute in isolated environments that cannot read or write production data and cannot interfere with concurrent test runs, except through declared shared fixtures. |
| NFR-160 | Observability | Every test run, step, and gate evaluation emits structured metrics, logs, and traces keyed by test-run id, plan id, and project id. |
| NFR-161 | Accessibility | The test management UI conforms to WCAG 2.1 AA as defined by the F-8 component system, including keyboard-only operation of result exploration. |
| NFR-162 | Idempotency | Re-triggering a test run with an identical idempotency key within its retention window returns the same test-run id and does not create duplicate executions. |
| NFR-163 | Localization | Reports, durations, timestamps, and numbers render in the caller's locale per the F-8 internationalization contract. |

#### User Stories

| ID | Story |
|---|---|
| US-139 | As an operator, I want to define a test case with explicit assertions so that pipeline outputs are checked reproducibly rather than by ad-hoc inspection. |
| US-140 | As a QA engineer, I want to group related test cases into a versioned suite so that I can reuse a curated body of checks across projects. |
| US-141 | As an operator, I want to bind a suite to a pipeline stage as a blocking plan so that a stage cannot advance on failing output. |
| US-142 | As an operator, I want to trigger a test run on demand and get a stable run id immediately so that I can monitor it without blocking my workflow. |
| US-143 | As an operator, I want tests to evaluate the artifacts my agents produced so that quality is asserted against real stage output, not assumptions. |
| US-144 | As an operator, I want a quality gate verdict I can trust so that stage advancement reflects a deterministic pass/fail rather than a guess. |
| US-145 | As an operator, I want to see which stages, agents, and artifacts are uncovered by tests so that I can close blind spots. |
| US-146 | As an operator, I want regression suites to run against a baseline on a schedule so that I catch newly broken behaviour early. |
| US-147 | As an operator, I want statistically flaky tests quarantined and clearly flagged so that they stop blocking gates without hiding the problem. |
| US-148 | As an operator, I want configurable retries for tests that are transiently unstable so that one unlucky run does not fail a gate. |
| US-149 | As an operator, I want versioned fixtures and datasets bound to tests so that every execution starts from a known input state. |
| US-150 | As an operator, I want per-run, per-suite, per-project, and per-portfolio reports so that I can review quality in the scope I am accountable for. |
| US-151 | As a privileged operator, I want to waive a specific failing gate with a reason and expiry so that a known-acceptable failure does not permanently block progress, while remaining visible. |
| US-152 | As an operator, I want notifications on gate-blocking failures, regressions, and quarantine changes so that I react to real quality risks without polling. |
| US-153 | As a security officer, I want all test management access scoped by role and project so that test evidence and control over gates cannot be abused. |

### Behaviour

1. **Definition.** An authorized operator creates a test case (FR-239); each edit produces a new immutable revision (FR-240). Test cases declare ordered steps with assertions (FR-241) and are grouped into versioned suites (FR-242).
2. **Binding.** An operator binds a suite revision to a project and/or a pipeline stage as a test plan, declaring environment requirements, retry policy, gate criteria, and whether the plan is blocking or advisory (FR-243).
3. **Pre-flight.** On trigger (FR-244), the platform resolves the pinned revisions, expands parameter sets (FR-254), checks environment requirements (FR-253), and either returns a stable run id or an itemized unmet-requirement report.
4. **Execution.** Whole test runs execute in isolation (NFR-159); each execution starts from declared fixtures (FR-252); retries follow the declared policy (FR-251). Manual tests are executed and attested by an operator (FR-256).
5. **Evaluation.** Each step is evaluated against its assertion (FR-245); step outcomes roll up to test outcomes (FR-246); test outcomes roll up to a plan verdict under the plan's criteria (FR-247).
6. **Gate emission.** The plan emits exactly one verdict (`pass` / `fail` / `waived` / `inconclusive`); F-3 consumes it to advance, block, or escalate the stage. F-12 never advances stages.
7. **Analysis.** Coverage is computed over pipeline surfaces (FR-248); regression runs are compared against a baseline (FR-249); flakiness is detected and optionally quarantined (FR-250); failures are linked to defects and triaged (FR-262).
8. **Reporting and notification.** Reports are produced scoped to any level (FR-258); notification events are emitted for gate-blocking failures, regressions, flake detection, quarantine changes, and waiver expiry (FR-259), and rendered by F-8/F-11.
9. **Governance.** Every mutation is authorized (FR-260) and audited (FR-261); waivers are bound to the exact revisions and expiry they cover (FR-257).
10. **Exposure.** All of the above is available through the stable, versioned test management API (FR-263).

### Business Rules

| ID | Rule |
|---|---|
| BR-1 | A test run always pins exact revisions of test cases, suites, and plans; revisions are never mutated in place, and historical results always reference the revision that produced them. |
| BR-2 | A blocking plan tied to a stage produces exactly one gate verdict per evaluation and is the only F-12 output F-3 may use to gate stage advancement. |
| BR-3 | A plan with unmet environment requirements must not start; it reports `inconclusive` with an itemized unmet-requirement list rather than a failure. |
| BR-4 | A waived failure remains a failure in all result and coverage views; a waiver affects only the gate verdict and carries a mandatory reason, scope, and expiry. |
| BR-5 | A quarantined test is excluded from hard gate criteria but remains visible, still executes if scheduled, and retains its full outcome history. |
| BR-6 | Retries never overwrite the original attempt; the original and every retry are retained and the final outcome is derived by the declared rule. |
| BR-7 | A test revision marked flaky-prone is the only case in which non-determinism is permitted; all other revisions are expected to be reproducible (NFR-158). |
| BR-8 | Deleting a test case archives it; it may only be permanently deleted when no retained result, gate verdict, or audit event references it, subject to retention policy (NFR-154). |
| BR-9 | Coverage is only credited by a passing outcome on a non-quarantined, non-waived execution against the current pinned revision. |
| BR-10 | Every waiver and every quarantine change requires an authorized role and is audited; expired waivers automatically cease to affect gate verdicts. |

### Validation

| ID | Validation |
|---|---|
| V-1 | Test case name is required, non-empty, and unique within its project scope. |
| V-2 | Test case type must be one of the registered types; unknown types are rejected. |
| V-3 | Each step requires an assertion type and a target; a step with an expected value requires the value, and a predicate step requires a syntactically valid predicate. |
| V-4 | A suite must reference existing test-case revisions; it may not reference a deleted or inaccessible revision. |
| V-5 | A plan's pinned suite revision must exist and must not be archived. |
| V-6 | Gate criteria must be internally consistent: maximum failures and must-pass sets may not contradict each other. |
| V-7 | Environment declarations must reference registered environments/capabilities; unrecognized requirements are rejected at plan save time, not at run time. |
| V-8 | Retry counts must be non-negative integers within the configured maximum; backoff must be a valid duration. |
| V-9 | Parameter sets must be non-empty and may not contain duplicate parameter identifiers. |
| V-10 | Idempotency keys must be non-empty when supplied and are unique per project and trigger scope. |
| V-11 | A waiver requires a non-empty reason, a valid scope, and a future expiry timestamp; expiry in the past is rejected. |
| V-12 | A defect link must reference an existing, accessible defect/ticket identifier and a valid triage state. |

### Edge Cases

| ID | Edge case | Expected handling |
|---|---|---|
| EC-1 | Two triggers arrive with the same idempotency key concurrently. | Only one test run is created; both callers receive the same run id (NFR-162). |
| EC-2 | A plan references a suite revision that is archived between pre-flight and execution. | The run is rejected at pre-flight with an itemized reason; no partial execution occurs. |
| EC-3 | A parameterized plan expands to zero executions (empty intersection of filters). | The run is created, reports `inconclusive` with an explicit "no executions matched" reason, and never reports `pass`. |
| EC-4 | An environment requirement becomes unmet after execution has begun. | In-flight executions finish; the run is marked `errored` with the environment cause; the gate verdict is `inconclusive`, never `pass`. |
| EC-5 | A test's artifact reference is deleted before evaluation. | The test is recorded as `errored` with a missing-artifact reason; it is not silently skipped. |
| EC-6 | Every test in a plan is quarantined. | The gate verdict is `inconclusive` with a "no eligible tests" reason; it is never an implicit `pass`. |
| EC-7 | A waiver expires mid-run. | The verdict is computed against waiver state at evaluation time; an expired waiver does not apply and the failure counts. |
| EC-8 | A flaky test passes on retry and fails on the original attempt. | Both attempts are retained; the outcome follows the declared retry rule; the flake is recorded for detection (FR-250). |
| EC-9 | A regression run finds a test newly passing and another newly failing. | Both transitions are reported against baseline; neither is suppressed. |
| EC-10 | A manual attestation is submitted without evidence where evidence is required by the plan. | The attestation is rejected with a missing-evidence reason. |
| EC-11 | The same test case appears twice in one suite via nested suites. | Execution is de-duplicated by pinned revision; the duplicate reference is reported as a warning. |
| EC-12 | A test compares a metric with a declared tolerance and the metric is exactly at the boundary. | Boundary handling is inclusive and deterministic, defined by the assertion type; the same input always yields the same verdict. |

### Error Handling

| ID | Error condition | Handling |
|---|---|---|
| EH-1 | Trigger requested for an unknown or archived project/stage. | Rejected with a not-found error and no run created. |
| EH-2 | Pre-flight readiness failure (unmet environment, missing fixture, missing artifact source). | Blocked with an itemized, actionable readiness report; the run is not created (mirrors the readiness discipline of F-3 pre-flight). |
| EH-3 | Result ingestion fails for a subset of steps due to a transient backend error. | Ingestion is retried with backoff; if still failing, the affected run is marked `errored` with an explicit ingestion-failure reason and never reported as `pass`. |
| EH-4 | Gate evaluation cannot reach a deterministic verdict (missing results, backend unavailable). | The verdict is `inconclusive`; F-3 is informed, and the failure is surfaced as an actionable item. Never default to `pass` (NFR-153). |
| EH-5 | Authorization failure on any endpoint. | Denied with a permission error; the attempt is audited; no partial mutation occurs. |
| EH-6 | Idempotency-key collision with a *different* prior payload. | Rejected with a conflict error explaining the mismatch; the prior run is not modified. |
| EH-7 | Evidence or result payload exceeds configured size limits. | Rejected with a clear size-limit error; the caller is directed to store large evidence by reference. |
| EH-8 | Defect link target is inaccessible to the caller. | The link is stored without exposing the target's contents; the operation succeeds but the target is shown as restricted. |

### Acceptance Criteria

| ID | Acceptance criterion |
|---|---|
| AC-1 | An operator can create a test case with at least one assertion step, and the case persists with a stable id and current revision (FR-239, FR-241). |
| AC-2 | Editing a test case produces a new revision; rerunning the old revision reproduces the old outcome record unchanged (FR-240, NFR-158). |
| AC-3 | An operator can group test cases into a versioned suite and bind it to a stage as a blocking plan (FR-242, FR-243). |
| AC-4 | Triggering a test run returns a stable run id within 500 ms at p95, and the same idempotency key returns the same id (FR-244, NFR-149, NFR-162). |
| AC-5 | Tests evaluate real artifacts published by pipeline stages, and a failing assertion produces a `failed` step outcome with captured evidence (FR-245, FR-246). |
| AC-6 | A blocking plan emits exactly one verdict, and F-3 receives `fail` for a failing must-pass set and `pass` only when all criteria are met (FR-247, BR-2). |
| AC-7 | Coverage reports enumerate uncovered stages and artifacts for a project without crediting quarantined or waived tests (FR-248, BR-9). |
| AC-8 | A scheduled regression run reports newly passing, newly failing, and newly flaky tests against a named baseline (FR-249). |
| AC-9 | A statistically flaky test is flagged and can be quarantined; quarantine removes it from hard gate criteria while keeping it visible and reversible (FR-250, BR-5). |
| AC-10 | Retries are recorded as distinct attempts and the final outcome follows the declared rule with the original attempt preserved (FR-251, BR-6). |
| AC-11 | Fixtures are versioned and bound to tests; each execution demonstrably starts from the declared input state (FR-252). |
| AC-12 | A plan with unmet environment requirements never starts and reports an itemized unmet-requirement list (FR-253, BR-3). |
| AC-13 | A parameterized plan expands into individually identified executions with per-parameter outcomes (FR-254). |
| AC-14 | Per-run, per-suite, per-project, and per-portfolio reports are produced and exported in a structured format (FR-258). |
| AC-15 | A privileged operator can waive a failing test/gate with a required reason and expiry; the failure remains visible and the verdict becomes `waived` until expiry (FR-257, BR-4). |
| AC-16 | Notification events fire for gate-blocking failures, regressions, flake detection, quarantine changes, and waiver expiry, and are rendered by F-8/F-11 (FR-259). |
| AC-17 | All access is role-scoped; unauthorized create/run/waive/quarantine attempts are denied and audited (FR-260, NFR-155). |
| AC-18 | Every mutation produces an immutable, attributed audit event (FR-261). |
| AC-19 | Failing outcomes can be linked to defects and triaged, and untriaged gate-blocking failures are surfaced (FR-262). |
| AC-20 | The test management API exposes definitions, runs, results, coverage, and gate verdicts consumed by F-3, F-6, F-9, and F-11 (FR-263). |

### API Behaviour

| ID | Endpoint behaviour |
|---|---|
| API-1 | `POST /projects/{projectId}/tests` — create a test case; returns the created case with id and initial revision; validates per V-1, V-2, V-3. |
| API-2 | `PUT /tests/{testId}` — creates a new immutable revision; response includes the new revision id; the prior revision remains retrievable. |
| API-3 | `GET /projects/{projectId}/tests` — lists test cases with filters by type, tag, owner, status, and coverage; paginated and stable-ordered. |
| API-4 | `POST /tests/{testId}/archive` / `POST /tests/{testId}/restore` — archives or restores a case; permanent delete (`DELETE`) is permitted only when unreferenced (BR-8). |
| API-5 | `POST /projects/{projectId}/suites` and `PUT /suites/{suiteId}` — create/revise a suite; references resolved to existing, accessible revisions (V-4). |
| API-6 | `POST /projects/{projectId}/plans` — create a test plan binding a pinned suite revision to a project and/or stage with environment, retry, and gate criteria (V-5, V-6, V-7). |
| API-7 | `POST /plans/{planId}/runs` — trigger a test run; accepts `idempotencyKey`, `label`, `revisionPin`, and `parameters`; returns a stable `testRunId` immediately (FR-244). |
| API-8 | `GET /test-runs/{testRunId}` — returns run status, expanded executions, and per-step outcomes with evidence references. |
| API-9 | `GET /test-runs/{testRunId}/verdict` — returns the single deterministic gate verdict (`pass` / `fail` / `waived` / `inconclusive`) and the criteria evaluation detail; this is the endpoint F-3 consumes. |
| API-10 | `GET /plans/{planId}/coverage` — returns coverage percentages and the enumerated uncovered pipeline surfaces (FR-248). |
| API-11 | `GET /projects/{projectId}/trends` — returns pass-rate, duration, flake-rate, and coverage trends (FR-255). |
| API-12 | `POST /test-runs/{testRunId}/attest` — records a manual attestation with per-item outcomes, evidence, and identity (FR-256). |
| API-13 | `POST /test-runs/{testRunId}/waivers` — creates a waiver with mandatory reason, scope, and expiry; validates V-11 (FR-257). |
| API-14 | `POST /tests/{testId}/quarantine` / `DELETE /tests/{testId}/quarantine` — sets/clears quarantine; both audited and both reflected in subsequent gate evaluations (FR-250). |
| API-15 | `POST /test-runs/{testRunId}/results/{resultId}/defect-links` — links a failing outcome to a defect and triage state; validates V-12 (FR-262). |
| API-16 | `GET /reports` with `scope=run|suite|plan|project|portfolio` and `format` — produces scoped, structured, localized test reports (FR-258, NFR-163). |
| API-17 | All endpoints enforce RBAC, return consistent error envelopes, honor idempotency keys where mutations are retryable, and emit audit events for every mutation (FR-260, FR-261, NFR-162). |
| API-18 | All endpoints are versioned and remain backward compatible within a major version; schema migrations never invalidate recorded results or verdicts (NFR-157). |

### Priority

**Priority: must-have.** F-12 is the quality-assurance backbone of Product Forge: because the platform orchestrates autonomous and semi-autonomous agents across a 32-stage pipeline, trustworthy, deterministic, auditable test management is what makes stage gating (F-3), operator control (F-6), autonomous policy (F-7), grounded explanation (F-9), and mobile review (F-11) meaningful. Without a governed verdict source, gate decisions would be unverifiable and the platform could not claim reproducible quality. Within F-12, the must-have subset is FR-239 through FR-247 (definition, versioning, binding, triggering, artifact evaluation, result capture, and gate verdict), FR-253, FR-257, FR-260, FR-261, and FR-263, with their supporting NFRs (NFR-149, NFR-150, NFR-153, NFR-154, NFR-155, NFR-158, NFR-159, NFR-162). The should-have subset is FR-248 through FR-255, FR-258, FR-259, and FR-262 (coverage, regression, flakiness, retries, fixtures, trends, reporting, notifications, defect linking) with NFR-151, NFR-152, NFR-156, NFR-157, NFR-160, NFR-161. The nice-to-have subset is FR-256 (manual attestation) with the remaining NFRs, which refine ergonomics and internationalization rather than core correctness.
