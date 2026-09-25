## F-13: API-First Access

**Feature ID:** F-13
**Summary:** F-13 defines the first-class, versioned, machine-readable API surface of Product Forge, and the guarantee that it is *not* a second-class citizen behind the dashboard. Every capability an operator can exercise in the dashboard — creating projects (F-1, F-2), launching and driving runs and stages (F-3), grouping portfolios and multi-project runs (F-4, F-5), issuing manual commands and human-in-the-loop (HIL) gate decisions (F-6), configuring Auto Mode (F-7), and governing tests and quality gates (F-12) — must be reachable through a documented, contract-verified API. F-13 owns the API contract itself: versioning and lifecycle, machine-readable contract publication, client authentication and scope-based authorization, credential lifecycle, the uniform request/response envelope (errors, pagination, filtering, sparse fieldsets, idempotency, concurrency control), the asynchronous long-running-operation pattern, the streaming surface for live run telemetry, webhook/event subscriptions, bulk operations, dry-run preview, rate limiting and quotas, capability discovery, API activity auditing, SDK/CLI generation, sandbox environment, changelog and deprecation mechanics, canonical time/unit/enum representation, and the documentation/exploration surface.

**Boundary note:** F-13 owns no domain state. It does not own project or run records (F-1), project creation rules or model-tier definitions (F-2), stage orchestration, run execution, HIL gate definitions or telemetry (F-3), portfolio membership and roll-up semantics (F-4), multi-project run-group structure (F-5), the semantics of manual commands (F-6), Auto Mode policy or its decision ledger (F-7), the dashboard presentation contract (F-8), conversational reasoning/grounding/refusal policy (F-9), the voice I/O contract (F-10), the mobile companion experience (F-11), or test definitions, results and quality-gate verdicts (F-12). F-13 *exposes* those authoritative resources through a stable contract and enforces cross-cutting transport concerns; where a conflict exists, the owning feature's rules win and F-13 reflects them. F-13 likewise does not choose the runtime technology, database, or hosting model — those remain the Architect agent's decision; F-13 specifies behaviour, not implementation.

### Requirements

#### Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-264 | **Universal capability parity** — Provide an API-reachable equivalent for every user-facing capability offered by the dashboard surfaces of F-1 through F-12. No capability may exist only as a UI affordance. Parity is asserted by a maintained parity registry (capability → dashboard surface → API operation) and a parity test suite that fails the build when a dashboard-only capability is introduced. | Must-have |
| FR-265 | **API versioning and lifecycle** — Expose all resources under explicit major version namespaces (e.g. `/v1/...`). The major version is part of the path; additive, backward-compatible changes may ship within a major version. Breaking changes require a new major version. A published lifecycle states the current status of each version (current, deprecated, sunset) with dates. | Must-have |
| FR-266 | **Machine-readable contract publication** — Publish a complete OpenAPI 3.x description plus JSON Schemas for every request body, response body, and event payload. The contract is retrievable from the API itself and is versioned alongside the running deployment. The published contract must be byte-identical to what a client can fetch from a live environment. | Must-have |
| FR-267 | **Client authentication** — Support authenticated machine clients via long-lived scoped API keys and short-lived bearer access tokens obtained from a token exchange endpoint using OAuth2 client-credentials-style flow with a client identifier and secret. Optionally support mutually authenticated TLS for high-assurance integrations. Every request is attributable to a principal (user, service account, or automation identity). | Must-have |
| FR-268 | **Scope-based authorization with dashboard role parity** — Every operation declares a required scope. Scopes map deterministically onto the dashboard role/permission model so that an API client can never exceed the privileges its corresponding role would have. Authorization is enforced per tenant and per resource, with deny-by-default for undeclared or unmatched scopes. | Must-have |
| FR-269 | **Credential lifecycle management** — Create, list, label, rotate, disable, and revoke API keys and service-account secrets through the API itself. Expose creation time, last-used time, expiry, owning principal, granted scopes, and optional source-IP allowlist for each credential. Secrets are shown exactly once at creation/rotation and never retrievable afterwards. Rotation is possible without downtime (overlapping validity window). | Must-have |
| FR-270 | **Resource endpoints for every domain resource** — Provide create/read/list/update/mutate operations for the authoritative resources of F-1 through F-12: projects (F-1), model tiers and tier bindings (F-2), runs, stages, stage outcomes and HIL gates (F-3), portfolios and memberships (F-4), multi-project run groups (F-5), manual commands and command previews (F-6), Auto Mode policies, bindings and decision ledger entries (F-7), and test cases, suites, plans, test runs, results and quality-gate verdicts (F-12). Resource shapes mirror the owning feature's model and link to it by stable identifier. | Must-have |
| FR-271 | **Uniform error model** — Return all errors as a stable problem-details envelope carrying: a machine-readable error code, a human-readable message, the affected field(s) for validation failures, the correlation identifier, the API version, and a documentation link for the code. The same envelope shape is used for 4xx and 5xx responses, including rate-limit and authentication failures. | Must-have |
| FR-272 | **Pagination, filtering and sorting** — Every collection endpoint supports opaque cursor-based pagination with a stable total-ordering guarantee, a caller-specified page size bounded by a platform maximum, declarative filtering over documented fields, and multi-field sorting with deterministic tie-breaking. Cursors remain valid across concurrent inserts without skipping or duplicating items that have not changed. | Must-have |
| FR-273 | **Sparse fieldsets and related-resource expansion** — Allow callers to select the exact fields returned and to expand linked resources by name (e.g. a run expanded with its project and pinned pipeline version) instead of issuing N+1 requests. Expansion depth is bounded and documented. Unknown fields or expand targets are rejected with a validation error rather than silently ignored. | Should-have |
| FR-274 | **Idempotency for mutating requests** — Accept a caller-supplied idempotency key on every unsafe operation (create, start, command, bulk). Replays of the same key with the same payload and principal return the original outcome without re-executing side effects. Replays with a differing payload are rejected. Keys are retained for a documented window and are scoped per principal. | Must-have |
| FR-275 | **Optimistic concurrency control** — Expose a version token (ETag) on mutable resources. Update and state-transition operations require the caller to supply the token they read; a mismatch results in a conflict error rather than a lost update. Concurrent conflicting writes surface as retryable conflicts, never as silent overwrites. | Must-have |
| FR-276 | **Asynchronous long-running operations** — Any operation that cannot complete within the synchronous request budget (run initiation, bulk commands, portfolio-wide actions, large exports) returns immediately with an operation resource and a status location. The operation resource reports progress, current phase, partial results, and terminal outcome, and is pollable and/or observable via webhook. | Must-have |
| FR-277 | **Streaming surface for live telemetry** — Provide a streaming subscription to run and stage telemetry (progress, stage transitions, HIL gate arrivals, log/trace fragments, Auto Mode decisions) whose information content matches the live dashboard view published by F-3/F-7/F-8. Streams are resumable from a caller-supplied cursor, deliver sequenced events, and signal gaps explicitly when the cursor is too old to resume. | Should-have |
| FR-278 | **Webhook event subscriptions** — Allow clients to register subscriptions for a documented catalogue of events (run started/finished, stage transitioned, HIL gate waiting, command executed, run failed, quality gate failed, Auto Mode escalation, credential about to expire). Deliver signed payloads with timestamps, event identifiers and sequence metadata; support per-subscription filtering, delivery retries with backoff, delivery history inspection, dead-letter visibility, and manual replay of failed deliveries. | Must-have |
| FR-279 | **Bulk operations with partial-failure semantics** — Accept bulk mutations over explicit or filtered resource sets and return a per-item outcome report distinguishing succeeded, skipped (with reason) and failed (with problem details) items. Bulk requests are bounded in size, are idempotent when keyed, and never leave the caller unable to determine the fate of an individual item. | Should-have |
| FR-280 | **Dry-run and command preview** — Mirror the preview/dry-run semantics of the manual command surface (F-6): allow a caller to submit a command or bulk action with a preview flag and receive the fully resolved effect — target resources, policy checks, guardrail evaluations (F-7), and predicted outcome class — without mutating any authoritative state. | Must-have |
| FR-281 | **Rate limiting and quotas** — Enforce per-principal, per-scope, and per-tenant request limits and coarser quotas (e.g. concurrent runs, stream subscriptions, webhook deliveries). Return standard rate-limit headers on every response including remaining allowance and reset timing, and a retry hint on rejection. Limits are discoverable per credential/tenant. | Must-have |
| FR-282 | **Capability and limits discovery** — Provide an unauthenticated-or-lightly-authenticated discovery endpoint returning the supported API versions, enabled feature capabilities for the tenant, resource limits, pagination bounds, retention windows for idempotency keys and deliveries, event catalogue, and the location of the current contract document. Clients must be able to self-configure from this endpoint alone. | Should-have |
| FR-283 | **API activity audit trail** — Record every authenticated API call with principal, credential identifier, method, route, target resources, outcome, correlation identifier, source address, and timestamp. Records are queryable through a documented endpoint, exportable, retained per the platform retention policy, and tamper-evident. | Must-have |
| FR-284 | **Generated clients and command-line parity** — Generate and publish client libraries and a command-line client directly from the contract for the supported languages, kept in lockstep with each published API version. Generated artifacts are integrity-labelled and their provenance (contract version) is verifiable. | Should-have |
| FR-285 | **Sandbox environment** — Provide an isolated sandbox environment with the same contract, seeded with representative projects, runs, gates and portfolios, in which mutating calls produce no external side effects (no real pipeline execution, no outbound notifications to production systems). Credentials are environment-scoped and not valid across environments. | Should-have |
| FR-286 | **Changelog, migration guidance and in-band deprecation signals** — Publish a machine- and human-readable changelog per version, migration guidance for breaking changes, and emit in-band deprecation warnings on requests that touch soon-to-be-removed fields or operations, including the announced sunset date. | Must-have |
| FR-287 | **Canonical representation of time, units and enumerations** — All timestamps are ISO-8601 with explicit UTC offset; durations carry explicit units; identifiers are opaque strings; enumerations are stable, documented, and forward-compatible (clients must tolerate unknown values and must not be broken by additions). | Must-have |
| FR-288 | **Browsable documentation and exploration surface** — Publish human-readable reference documentation derived from the same contract, with per-operation request/response examples, error-code explanations, authentication walkthroughs, and a try-it capability against the sandbox. Documentation drift from the deployed contract is treated as a defect. | Should-have |

#### Non-Functional Requirements

| ID | Requirement | Target / Measurement |
|---|---|---|
| NFR-164 | **API performance** | p95 latency < 300 ms for reads and < 500 ms for writes at reference load; first streamed event delivered < 1 s after subscribe; measured by continuous synthetic probing per region and per version. |
| NFR-165 | **Scalability** | Sustain the documented per-tenant request rate and concurrent stream subscriptions under linear horizontal scale with no contract-visible degradation; verified by load tests at 2× documented quota. |
| NFR-166 | **Availability** | 99.9% monthly availability of read and write API operations, excluding announced maintenance; degraded read-only mode is acceptable for write unavailability, and health is published per capability. |
| NFR-167 | **Write durability and read-after-write** | Acknowledged mutating calls are durable before the response is returned; a principal reading its own just-written resource observes the write; verified by fault-injection tests. |
| NFR-168 | **Security posture** | TLS 1.2+ for all transport; mitigations for the OWASP API Security Top 10 including broken object-level authorization, mass assignment, excessive data exposure and resource-consumption attacks; no credential or secret material in logs, traces or error payloads; strict input size and type limits. |
| NFR-169 | **Credential protection and revocation latency** | Secrets stored only in hashed/irreversible form; revocation effective within 60 seconds across all regions; rotation completes without client-visible downtime; verified by automated rotation drills. |
| NFR-170 | **Data residency and tenant isolation** | Regional endpoints keep tenant data within the declared region; tenant scoping is enforced at the data-access layer, not only at the routing layer; cross-tenant access attempts are impossible and generate security audit events. |
| NFR-171 | **Privacy and data minimization** | Responses return only fields the principal's scope permits; PII and secret-bearing fields are redacted by default and gated behind an explicit elevated scope; tenant-level export and erase operations are supported through the API. |
| NFR-172 | **Backwards-compatibility window** | Each major version is supported for at least 12 months after a successor is announced generally available; within a major version, additive changes only; breaking changes only in a new major version; verified by contract-diff checks in CI. |
| NFR-173 | **Observability of the API surface** | Every request carries and echoes a correlation identifier; per-route metrics, distributed traces and structured logs are emitted; SLO dashboards exist for latency, error rate, quota rejection rate, webhook delivery success and stream resumption failure. |
| NFR-174 | **Environment parity** | Sandbox, staging and production expose the same contract for the same version; a contract-conformance suite runs in CI against every environment after deploy and fails the release on any divergence. |
| NFR-175 | **Graceful degradation under pressure** | Rate-limit and quota rejections return actionable retry guidance; overload protection sheds load in a documented priority order (read before write, streaming before bulk) rather than failing indiscriminately. |
| NFR-176 | **Bounded payloads and timeouts** | Maximum request body size, maximum page size, maximum expansion depth, maximum bulk item count, and maximum stream backlog are documented, enforced and advertised through discovery; server-side timeouts are shorter than client retry horizons. |
| NFR-177 | **Event delivery reliability** | Webhook delivery is at-least-once with exponential backoff, signature verification, replay protection, dead-letter capture and manual replay; per-subscription ordering of related events is preserved where declared, and delivery success rate is measured and alerted. |
| NFR-178 | **Contract freshness (zero drift)** | The published contract is generated from and verified against the implementation on every deploy; any divergence between served behaviour and published contract fails the release pipeline. |

#### User Stories

| ID | Story |
|---|---|
| US-154 | As a platform integrator, I want to create, list and update pipeline projects through the API so that onboarding of new product work can be automated instead of clicked. |
| US-155 | As a CI/CD engineer, I want to start runs and poll or subscribe to their status through the API so that Product Forge pipelines can be triggered from my build system. |
| US-156 | As an SRE, I want to register webhook subscriptions for failure, gate-waiting and escalation events so that my incident tooling reacts without polling. |
| US-157 | As a security engineer, I want scoped, rotatable, revocable credentials with last-used visibility so that every integration follows least privilege. |
| US-158 | As a data engineer, I want cursor pagination, filtering and field selection so that I can incrementally synchronise large project and run inventories cheaply. |
| US-159 | As an operator, I want every dashboard capability to be reachable through the API so that automation is never second-class and nothing requires manual clicking. |
| US-160 | As an integration author, I want machine-readable error codes with field-level validation detail so that my client can handle failures programmatically instead of parsing prose. |
| US-161 | As a release manager, I want versioned contracts, changelogs and an announced deprecation window so that upgrades are predictable and never surprise my services. |
| US-162 | As an automation author, I want idempotency keys on unsafe operations so that retries after a network failure never create duplicate runs or duplicate commands. |
| US-163 | As a companion-app developer, I want a resumable streaming surface for live run telemetry so that what I display matches the dashboard in real time. |
| US-164 | As a partner developer, I want generated client libraries and an isolated sandbox so that I can build and test without touching production data or triggering real pipelines. |
| US-165 | As an auditor, I want to query and export API activity records with correlation identifiers so that I can trace exactly which principal did what. |
| US-166 | As an operator, I want to dry-run a command or bulk action through the API and see its resolved effect so that large changes are safe. |
| US-167 | As a capacity planner, I want rate-limit and quota headers plus a discovery endpoint so that my clients self-throttle before being rejected. |
| US-168 | As a developer, I want browsable, example-rich documentation generated from the live contract so that integrating takes hours rather than weeks. |

### Behaviour

**1. Contract-first equivalence.** The API is the primary expression of Product Forge's capabilities; the dashboard is a consumer of the same surface (see F-8's rendering contract). For each capability owned by F-1 through F-12, F-13 exposes an operation whose effect, validation and authorization semantics are identical to the dashboard's. When a feature adds or changes a capability, its API representation is updated in the same change; a capability with no API operation is a contract violation detected by the parity suite (FR-264).

**2. Versioned namespaces.** Clients address resources as `/v1/<resource>`. The major version namespace is immutable in meaning: within `v1`, only additive changes (new operations, new optional fields, new enum values, new event types) are permitted. Removing a field, tightening validation, changing a status code's meaning, or changing a default is breaking and occurs only in a new major version (FR-265, NFR-172).

**3. Authentication flow.** A client presents either a long-lived scoped API key or a short-lived bearer token obtained by exchanging a client identifier and secret at the token endpoint (FR-267). Tokens carry the granted scopes, the tenant, the expiry and the originating credential identifier. The platform resolves the request principal, evaluates the required scope(s) for the operation, applies resource-level authorization, and rejects on any failure before touching domain state (FR-268).

**4. Uniform request/response conventions.**
- Requests and responses are JSON with an explicit content type; unsupported media types are rejected.
- Collections always use the same envelope: the item array, an opaque next cursor, an optional previous cursor, and a bounded total when cheaply computable (FR-272).
- Field selection and expansion are expressed as query parameters validated against the contract (FR-273).
- Mutating responses return the resulting resource representation where the owning feature defines one, plus the resource's new version token.
- Every response carries a correlation identifier, the API version, and rate-limit headers (FR-271, FR-281, NFR-173).

**5. Idempotency and concurrency.** Unsafe operations accept an idempotency key; the platform records the key, principal and request fingerprint and replays the stored outcome for duplicate submissions within the retention window, rejecting key reuse with a differing fingerprint (FR-274). Mutable resources expose a version token; conditional updates must present the token and conflicts are returned as retryable conflict errors (FR-275). Together these make client retries safe without server-side session state.

**6. Long-running operations.** Operations exceeding the synchronous budget are accepted with a `202`-class response carrying an operation resource: identifier, kind, target resources, status, progress, phase, timestamps, partial results and, on completion, either the produced resource reference or the terminal problem (FR-276). The same operation is observable by polling and by webhook, with identical content.

**7. Streaming.** A client subscribes to a telemetry stream for a run, run group, portfolio or Auto Mode session and receives sequenced, timestamped events whose information content is equivalent to the dashboard's live view (FR-277). Streams resume from a caller-supplied cursor; when the cursor predates retention, the server signals an explicit gap with the oldest available cursor rather than silently continuing.

**8. Events and webhooks.** Subscriptions are per tenant and per event type, with optional filters. Deliveries are signed so receivers can verify authenticity and detect replays; failures retry with backoff, then land in dead-letter where they are inspectable and replayable (FR-278, NFR-177). Delivery history is itself an API resource.

**9. Bulk and preview.** Bulk mutations accept an explicit identifier set or a filter, are bounded, and always return per-item outcomes, so partial failure is never ambiguous (FR-279). Any command or bulk action can be issued in preview mode, which resolves targets, policy checks and guardrail evaluations and returns a predicted-effect report with no mutation — the same preview semantics the manual command surface exposes (FR-280, and see F-6 and F-7 for the rules being previewed).

**10. Discovery and self-configuration.** A client can learn, without prior configuration, which versions exist, which capabilities are enabled for its tenant, what its limits are, which events it can subscribe to, and where to fetch the current contract (FR-282). This makes generated clients and the CLI runnable with no hardcoded assumptions (FR-284).

**11. Auditability.** Every authenticated call is recorded with enough context to reconstruct who did what and why the platform allowed it (FR-283). Audit records are queryable, exportable and retained per policy; they are never mutated in place.

**12. Environments.** Sandbox exposes the same contract as staging and production for a given version, is seeded with representative data, and produces no external side effects; credentials do not cross environment boundaries (FR-285, NFR-174).

### Business Rules

- **BR-1:** The API is authoritative and the dashboard is a peer consumer of it. A capability reachable only from a dashboard surface is a defect, not a design choice. (FR-264)
- **BR-2:** Within a major version, changes are additive only. Removing, renaming, or retyping a field, or tightening a previously accepted input, requires a new major version. (FR-265, NFR-172)
- **BR-3:** A published API version is supported for at least 12 months after its successor is generally available; sunset is announced no later than the start of that window and is surfaced in-band on affected requests. (FR-265, FR-286)
- **BR-4:** Authorization is deny-by-default. An operation with no matching scope grant is rejected regardless of credential validity. (FR-268)
- **BR-5:** API clients can never exceed the privileges their mapped dashboard role would hold; scopes are a projection of the role model, never an escalation path. (FR-268)
- **BR-6:** Secrets are displayed once and never again; any credential whose secret has been lost must be rotated, not recovered. (FR-269, NFR-169)
- **BR-7:** Idempotency keys are scoped to a principal and a route; the same key with a different payload is an error, never a silent overwrite. (FR-274)
- **BR-8:** Conditional writes without a current version token are rejected for resources that declare one; last-write-wins is not an accepted outcome. (FR-275)
- **BR-9:** Preview/dry-run never mutates authoritative state and never emits side-effecting outbound notifications. (FR-280, FR-285)
- **BR-10:** Webhook subscription destinations must be authenticated, and payloads must be signed; unsigned or unverifiable delivery is a contract violation. (FR-278)
- **BR-11:** Bulk operations are all-or-report: the caller always receives the fate of every requested item, even when the request is only partially successful. (FR-279)
- **BR-12:** Sandbox credentials are invalid outside sandbox, and production credentials are invalid inside sandbox. (FR-285)
- **BR-13:** The published contract is the single source of truth for clients; where documentation and served behaviour disagree, the divergence is a release-blocking defect. (FR-266, NFR-178)
- **BR-14:** Unknown enumeration values returned by the server must not break clients — the contract states this explicitly and compatibility tests enforce it. (FR-287)

### Validation

- **V-1:** Version namespace must match a currently served major version; unknown or sunset versions are rejected with an actionable error naming supported versions. (FR-265)
- **V-2:** The credential presented must be syntactically valid, unexpired, unrevoked, and within any configured source-IP allowlist. (FR-267, FR-269)
- **V-3:** The resolved principal must hold every scope the operation declares, and the tenant/resource scope must match the target resource. (FR-268)
- **V-4:** Collection parameters must satisfy documented bounds: page size within minimum/maximum, sort fields within the allowed set, filter fields and operators within the allowed grammar. (FR-272)
- **V-5:** `fields` and `expand` values must resolve to contract-declared fields and relationships; expansion depth must be within the documented bound. (FR-273)
- **V-6:** Idempotency keys must satisfy the documented format and length, and must be absent-or-consistent with any prior use by the same principal on the same route. (FR-274)
- **V-7:** Conditional mutating requests must present a version token that matches the resource's current token. (FR-275)
- **V-8:** Request bodies must conform to the contract schema: types, formats, required fields, enum membership, string length, numeric ranges, and array cardinality. (FR-271, FR-287)
- **V-9:** Bulk requests must not exceed the maximum item count and must supply either an explicit identifier set or a filter, never both conflicting. (FR-279)
- **V-10:** Webhook subscription destinations must be reachable-format absolute URLs with an allowed scheme, carry the required signing configuration, and declare at least one known event type from the catalogue. (FR-278)
- **V-11:** Stream subscriptions must present a cursor that is syntactically valid and within retention. (FR-277)
- **V-12:** Timestamps supplied by clients are validated as ISO-8601 with an explicit offset; durations must carry explicit units; ambiguous formats are rejected. (FR-287)
- **V-13:** Request body size, header size, and total parameter count must be within documented limits. (NFR-176)

### Edge Cases

- **EC-1:** A client retries a mutating request after a timeout using the same idempotency key and identical payload while the original is still in flight — the platform returns the eventual original outcome, not a duplicate side effect. (FR-274)
- **EC-2:** A client sends the same idempotency key with a materially different payload — rejected as a conflict, with the original request's fingerprint referenced. (BR-7)
- **EC-3:** The idempotency retention window has elapsed and the same key is resubmitted — treated as a new request, and the response makes clear that replay protection no longer applies. (FR-274)
- **EC-4:** Two clients update the same resource from the same read — the second receives a conflict and must re-read; no lost update occurs. (FR-275)
- **EC-5:** A long-running operation completes between the client's `202` receipt and its first poll — the operation resource still reports the terminal outcome with the produced result, exactly once. (FR-276)
- **EC-6:** A streaming client disconnects and reconnects with a cursor that is still within retention — it resumes with no gap and no duplicate event identities. (FR-277)
- **EC-7:** A streaming client reconnects with a cursor older than retention — the server returns an explicit gap signal plus the oldest resumable cursor, and never fabricates continuity. (FR-277)
- **EC-8:** A webhook receiver is down for an extended period — deliveries retry with backoff, exhaust, and land in dead-letter where they are inspectable and replayable without re-triggering duplicate domain actions on the receiving side (event identifiers are stable across replay). (FR-278)
- **EC-9:** A webhook payload is replayed to a receiver by an attacker — the signature and event identifier allow the receiver to detect and reject it. (BR-10)
- **EC-10:** A bulk request over 500 targets contains 3 invalid identifiers — the response reports the valid items' outcomes and the 3 failures with problem details; nothing is ambiguous. (FR-279)
- **EC-11:** A preview for a command that would be rejected by policy returns the rejection reason in the preview report without producing an error status, because nothing was attempted. (FR-280, BR-9)
- **EC-12:** A credential is revoked mid-request — in-flight requests using it are allowed only if already authorized; subsequent requests fail within the revocation latency target and are security-audited. (FR-269, NFR-169)
- **EC-13:** A tenant exceeds its request rate — responses return rate-limit headers with remaining allowance and a retry hint; the platform does not degrade other tenants. (FR-281, NFR-175)
- **EC-14:** A tenant exceeds a coarse quota (concurrent runs or stream subscriptions) — the request is rejected with a quota-specific code distinguishing quota exhaustion from rate limiting. (FR-281)
- **EC-15:** A client requests a field or expansion target that was removed in a previous version but is still requested under an older namespace — the correct version's contract governs, and the request succeeds against that version's shape. (FR-265, BR-2)
- **EC-16:** The server returns a new enumeration value the client has never seen (e.g. a new stage outcome) — a conforming client must continue to function. (FR-287, BR-14)
- **EC-17:** A capability is disabled for a tenant by feature configuration — the discovery endpoint omits it and calling its operation returns an explicit "capability not enabled" code rather than a generic authorization failure. (FR-282)
- **EC-18:** A client attempts to use a production credential in the sandbox (or vice versa) — rejected as an invalid-environment credential, with no partial execution. (FR-285, BR-12)
- **EC-19:** A requested page size exceeds the maximum — the platform either clamps to the maximum and reports the applied value, or rejects it; in either case the behaviour is documented and consistent, never silently different per route. (FR-272)
- **EC-20:** A stream subscriber requests telemetry for a run that has already finished — the platform delivers the retained tail and then signals end-of-stream rather than hanging open. (FR-277)

### Error Handling

- **EH-1:** All errors use the single problem-details envelope with a machine-readable code, human-readable message, correlation identifier, API version, and documentation link; there are no route-specific error shapes (FR-271).
- **EH-2:** Validation failures return field-level detail: each offending parameter or body path with the violated constraint, so clients can render or route precisely (FR-271, V-8).
- **EH-3:** Authentication failures are distinguishable from authorization failures: missing/invalid/expired/revoked credentials yield authentication errors; valid credentials lacking scope yield authorization errors naming the missing scope (FR-267, FR-268).
- **EH-4:** Resource-level authorization failures never reveal the existence of resources outside the principal's tenant or scope — the response is indistinguishable from "not found" to unauthorized principals (NFR-168, NFR-170).
- **EH-5:** Conflicts (version mismatch, idempotency-key mismatch, concurrent state transition) return a retryable conflict code with the current version token so the client can re-read and retry deterministically (FR-275, BR-7).
- **EH-6:** Rate-limit and quota rejections return retry-after guidance differentiating request-rate throttling from quota exhaustion, so clients can back off appropriately rather than abandoning the integration (FR-281, NFR-175).
- **EH-7:** Domain-level failures surfaced through the API retain the owning feature's error semantics (e.g. a run-initiation refusal from F-3, or a command rejection from F-6, including its reason and any guardrail verdict from F-7) wrapped in the uniform envelope, so clients see one transport contract and one faithful domain reason.
- **EH-8:** Server-side faults return a generic internal-error code plus the correlation identifier; internal details, stack traces and infrastructure identifiers are never exposed to clients but are logged against the same correlation identifier for support (NFR-168, NFR-173).
- **EH-9:** Partial failures in bulk operations never fail the whole request silently — the request succeeds with a per-item report whose failed items carry their own problem details (FR-279, BR-11).
- **EH-10:** Webhook delivery failures are retried with backoff, then dead-lettered; the subscription owner can inspect failure reasons, the response status from the receiver, and replay deliveries. Failure of one subscription never blocks delivery to others (FR-278, NFR-177).
- **EH-11:** Stream transport interruptions are distinguishable from stream termination: clients receive an explicit signal to reconnect-with-cursor versus end-of-stream, so clients do not silently miss events (FR-277).
- **EH-12:** When a request targets a version that has been sunset, the response names the sunset state and the supported versions rather than returning a generic routing failure (FR-265, FR-286).
- **EH-13:** Contract-conformance failures detected between published contract and served behaviour block the release rather than being reported to clients at runtime (NFR-178).

### Acceptance Criteria

- **AC-1:** A parity suite enumerates every dashboard capability of F-1 through F-12, maps it to at least one API operation, and fails when any capability lacks a mapping or when the mapping's semantics diverge. (FR-264)
- **AC-2:** Every served operation is present in the published contract for the corresponding version, with matching paths, parameters, schemas, status codes and error codes; the contract is fetchable from each environment and is identical for a given version across environments. (FR-266, NFR-174, NFR-178)
- **AC-3:** A client can authenticate using both a scoped API key and a short-lived exchanged token; requests attributable to a principal appear in the API activity audit. (FR-267, FR-283)
- **AC-4:** A credential missing a required scope is rejected with an authorization error naming the missing scope; a credential with the scope succeeds; cross-tenant reads and writes are impossible and produce security audit events. (FR-268, NFR-170)
- **AC-5:** Keys can be created, listed with last-used time, rotated with an overlap window, and revoked; revocation takes effect within the stated latency; secrets are never retrievable after creation. (FR-269, NFR-169)
- **AC-6:** Every collection endpoint supports cursor pagination and returns stable, non-overlapping pages under concurrent insertion as documented; page-size bounds are enforced and advertised. (FR-272, NFR-176)
- **AC-7:** Field selection and expansion return exactly the requested shape; unknown fields or expand targets are rejected, not ignored. (FR-273)
- **AC-8:** Replaying a mutating request with the same idempotency key and payload produces one side effect and an identical response; replay with a different payload is rejected. (FR-274, AC on BR-7)
- **AC-9:** Concurrent conflicting updates produce a conflict, never a lost update; a retry using the fresh version token succeeds. (FR-275)
- **AC-10:** A long-running operation returns immediately with an operation resource whose final state equals the eventual domain result; the same outcome is observable via polling and via webhook. (FR-276)
- **AC-11:** A stream subscriber receives telemetry information-equivalent to the live dashboard view, resuming from a cursor without duplicates or gaps within retention, and receiving an explicit gap signal outside retention. (FR-277)
- **AC-12:** Webhook payloads verify against the published signature scheme; a failed receiver triggers documented retries, dead-letter capture and successful manual replay with stable event identifiers. (FR-278, NFR-177)
- **AC-13:** A bulk request with mixed validity returns per-item outcomes covering every requested item. (FR-279)
- **AC-14:** A preview request produces the resolved target set, policy/guardrail evaluations and predicted effect with zero mutations and zero outbound side effects, and matches the dashboard's preview for the same inputs. (FR-280, BR-9)
- **AC-15:** Rate-limit and quota headers appear on every response; exceeding limits yields retryable, differentiated rejections; other tenants are unaffected. (FR-281, NFR-175)
- **AC-16:** The discovery endpoint alone provides versions, enabled capabilities, limits, retention windows and the contract location; a client configured from it can operate without hardcoded constants. (FR-282)
- **AC-17:** API activity records are queryable and exportable, correlate to server logs and traces by correlation identifier, and are immutable once written. (FR-283, NFR-173)
- **AC-18:** Generated clients and the CLI build from and stay in lockstep with the published contract for a given version; provenance is verifiable. (FR-284)
- **AC-19:** The sandbox accepts the same operations as production, produces no external side effects, and rejects credentials from other environments. (FR-285, BR-12)
- **AC-20:** A version marked deprecated emits in-band warnings naming its sunset date and replacement; the changelog and migration guide describe the change and both are machine-readable. (FR-286, NFR-172)
- **AC-21:** Timestamps, durations, identifiers and enums conform to the canonical representation rules, and a client that encounters a previously unknown enum value continues to function. (FR-287, BR-14)
- **AC-22:** Reference documentation is generated from the live contract, includes actionable examples per operation, and a drift check fails the release when documentation and served behaviour disagree. (FR-288, BR-13)
- **AC-23:** A contract-diff check in CI blocks any non-additive change inside an existing major version. (BR-2, NFR-172)

### API Behaviour

| ID | Operation / Surface | Behaviour |
|---|---|---|
| API-1 | `POST /v1/auth/token` | Exchange a client identifier and secret for a short-lived bearer token carrying tenant, scopes, credential identifier and expiry. Invalid, revoked or environment-mismatched credentials are rejected without revealing which check failed. |
| API-2 | `GET /v1/capabilities` | Return served major versions, tenant-enabled capabilities, limits (page size, expansion depth, bulk size, body size), retention windows (idempotency keys, streams, deliveries), the event catalogue, and the contract location. Safe to call before resource access. |
| API-3 | `GET /v1/openapi.json`, `GET /v1/openapi/{version}.json` | Return the machine-readable contract for the requested version as served by this environment. Immutable for a released version; verified against behaviour at deploy time. |
| API-4 | `/v1/projects`, `/v1/projects/{projectId}` | CRUD over projects reflecting the registry of F-1; portfolio membership references resolve against F-4's portfolio resource; creation may originate from the project-creation rules of F-2. Mutating calls support idempotency keys and conditional version tokens. |
| API-5 | `/v1/model-tiers`, `/v1/projects/{projectId}/model-tier` | Read available model tiers and bind or change a project's tier using the definitions governed by F-2; validation and allowed transitions follow F-2, not redefined here. |
| API-6 | `POST /v1/runs`, `GET /v1/runs`, `GET /v1/runs/{runId}` | Initiate and inspect runs under the initiation, pre-flight and plan-materialisation rules of F-3. Initiation returns a stable run identifier synchronously, or an operation resource when pre-flight or materialisation exceeds the synchronous budget. |
| API-7 | `/v1/runs/{runId}/stages`, `/v1/runs/{runId}/gates` | Read stage states, stage outcomes, and pending human-in-the-loop gates as defined by F-3, including gate input requirements so a client can construct a valid decision call. |
| API-8 | `POST /v1/runs/{runId}/commands`, `POST /v1/commands:preview` | Submit manual commands (pause, resume, cancel, retry, skip, gate decision, parameter override, emergency halt) carrying the semantics of F-6, or preview them. Preview returns resolved targets, policy and guardrail evaluations and predicted effect with no mutation. Command submission is idempotent and auditable. |
| API-9 | `/v1/operations/{operationId}` | Report status, progress, phase, timestamps, partial results and terminal outcome for any asynchronous operation; terminal outcomes reference the produced resource or the terminal problem. |
| API-10 | `GET /v1/runs/{runId}/events` (stream) | Deliver sequenced telemetry events for a run, resumable by cursor, with explicit gap signalling when the cursor predates retention and explicit end-of-stream when the run is finished. |
| API-11 | `/v1/webhook-subscriptions`, `/v1/webhook-deliveries` | Register, inspect, update and delete subscriptions; list delivery attempts with status, response code and failure reason; replay failed deliveries. Payloads are signed and events carry stable identifiers. |
| API-12 | `POST /v1/bulk/{resource}:act` | Apply a bounded bulk action over an explicit identifier set or filter, returning per-item succeeded/skipped/failed outcomes with problem details for failures. |
| API-13 | `/v1/audit-events` | Query and export API activity records (principal, credential, route, target resources, outcome, correlation identifier, source address, timestamp). Read-only and immutable. |
| API-14 | `/v1/portfolios`, `/v1/run-groups`, `/v1/auto-mode/policies`, `/v1/tests/*` | Expose the authoritative resources of F-4, F-5, F-7 and F-12 respectively, with their owning features' validation and lifecycle rules and F-13's cross-cutting conventions (pagination, filtering, idempotency, concurrency, errors). |

**Cross-cutting API conventions applied to every operation:** JSON content type; correlation identifier echoed on every response; ISO-8601 UTC timestamps and explicit duration units; opaque identifiers; stable, forward-compatible enums; uniform problem-details errors; rate-limit headers; idempotency keys on unsafe calls; conditional version tokens on mutable resources; and pagination envelopes on collections.

### Priority

**Overall feature priority: Must-have.** The product's premise is that Product Forge is a control plane operated both by humans and by automation; a first-class, contract-verified API is intrinsic to that premise rather than an enhancement. Within the feature:

- **Must-have (delivery-blocking):** FR-264 (parity), FR-265 and FR-266 (versioning and published contract), FR-267 and FR-268 (authentication and scoped authorization), FR-269 (credential lifecycle), FR-270 (resource endpoints), FR-271 (uniform errors), FR-272 (pagination/filter/sort), FR-274 (idempotency), FR-275 (concurrency control), FR-276 (async operations), FR-278 (webhooks), FR-280 (preview/dry-run), FR-281 (rate limiting/quotas), FR-283 (audit), FR-286 (changelog/deprecation), FR-287 (canonical representation). Corresponding NFRs: NFR-164, NFR-166, NFR-168, NFR-169, NFR-170, NFR-172, NFR-173, NFR-174, NFR-177, NFR-178.
- **Should-have (high value, may follow initial delivery):** FR-273 (sparse fieldsets/expansion), FR-277 (streaming telemetry), FR-279 (bulk), FR-282 (discovery), FR-284 (generated clients/CLI), FR-285 (sandbox), FR-288 (docs/exploration surface). Corresponding NFRs: NFR-165, NFR-167, NFR-171, NFR-175, NFR-176.
- **Nice-to-have (deferred only by explicit user decision, never by agent assumption):** none currently identified; if any item above is to be deferred, the decision belongs to the user and must be recorded in Open Questions before delivery scope is reduced.

### Open Questions

- **OQ-1:** Which client languages must have generated SDKs at first release (FR-284), and is a first-party command-line client required at launch or acceptable as a follow-on? The feature is specified regardless; only the breadth of generated artifacts depends on this answer.
- **OQ-2:** What is the minimum backwards-compatibility window the user requires (NFR-172 proposes 12 months)? A longer contractual window changes the release cadence obligations but not the design.
- **OQ-3:** Is the sandbox environment (FR-285) required at first release, or may it ship immediately after, provided staging remains contract-identical? This is a user scope decision, not an agent decision.
- **OQ-4:** Are there data-residency regions that must be supported at launch (NFR-170)? Region count affects deployment topology, which the Architect agent owns, but the API surface must expose the residency boundary either way.
- **OQ-5:** Should the streaming telemetry surface (FR-277) be exposed to all scopes or gated behind an elevated scope given its volume and cost? Either answer is implementable; the choice affects quota modelling (FR-281).
- **OQ-6:** Must mutual-TLS authentication (FR-267, optional) be enabled for first release for any known integration partner? No design change results, but it changes acceptance testing scope.
