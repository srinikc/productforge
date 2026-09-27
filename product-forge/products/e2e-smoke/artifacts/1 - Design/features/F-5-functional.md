## F-5: Integration Hub
> **Feature id:** F-5 · **Owned global id ranges:** FR-101..FR-125, NFR-61..NFR-75, US-61..US-75 · **Local ids** (BR-, EC-, AC-, API-, DM-, T-, OQ-) are scoped to this feature and numbered sequentially from 1. References to F-1 / F-2 / F-3 / F-4 ids are plain text only; this section never re-defines them.

### Requirements

**Functional Requirements (global ids — owned range FR-101..FR-125)**

| ID | Name | The feature must… |
|---|---|---|
| FR-101 | Connection catalogue | Present a browsable catalogue of connectable source types (calendar, email, issue/backlog tracker, code host, messaging, file store, generic webhook bridge) with a plain-language description of what data each type can read and write. |
| FR-102 | Connect account | Let the user start and complete an authorization handshake with a provider without typing provider credentials into the product's own fields; the connection appears in the user's connection list only after a successful callback. |
| FR-103 | Connection lifecycle management | List all connections with label, type, account identity, state (`connected`, `degraded`, `expired`, `error`, `paused`, `disconnected`) and last-sync time; support rename/label, pause, resume, reconnect, disconnect, and delete. |
| FR-104 | Credential storage, refresh, revocation | Store credentials/tokens securely outside user-visible surfaces, refresh them automatically before expiry, and revoke them on disconnect; never expose secret values in the UI, logs, or exports. |
| FR-105 | Connection health & diagnostics | Provide a per-connection health view: state, last successful sync, next scheduled sync, consecutive-failure count, last error in plain language, and a "test connection" action. |
| FR-106 | Multiple accounts per provider | Allow more than one account of the same provider type to be connected simultaneously, each with a distinct user-assigned label, independent scope, direction, and mappings. |
| FR-107 | Sync direction per connection | Let the user choose inbound-only, outbound-only, or bidirectional sync independently per connection and per scope. |
| FR-108 | Field mapping | Let the user map external fields to task fields (title, due date/time, explicit importance, tags/project, notes/description, status/completion, assignee) and define a default for unmapped fields. |
| FR-109 | Sync scope filters | Let the user include/exclude by external container (calendar, folder, list, project, label, saved query) and by rule (e.g., only items with a due date, only items assigned to me). |
| FR-110 | Inbound item ingestion | Create or update tasks in the product from external items that match the connection's scope, preserving a stable link to the source item; imported due dates are treated as first-class deadlines by the prioritization feature (F-1), and imported completion events count toward the analytics feature (F-4). |
| FR-111 | Outbound task propagation | Push task create, update, complete, reopen, and delete events to the external system according to the connection's direction, scope, and mapping. |
| FR-112 | Field-level conflict policy | Resolve concurrent edits per field using a user-selected rule: product wins, external wins, most-recent-change wins, or always-ask; the chosen rule is visible and changeable per connection. |
| FR-113 | Conflict detection & resolution inbox | Detect conflicts, hold the losing value (never silently discard), and present a conflict inbox where the user can keep the product value, keep the external value, merge per field, or apply the resolution to all similar conflicts. |
| FR-114 | Idempotent sync | Guarantee that retries, duplicate events, and restarts never create duplicate tasks or duplicate outbound writes; every external item maps to at most one task. |
| FR-115 | Deletion, unlink & tombstone semantics | Define and enforce what happens when an external item is deleted, moved out of scope, or the connection is removed: the user pre-selects "keep as standalone task", "archive", or "delete", and no task is destroyed without that rule or an explicit confirmation. |
| FR-116 | Sync cadence & manual trigger | Run scheduled syncs at a per-connection configurable interval and expose a "Sync now" action that works regardless of the schedule. |
| FR-117 | Event-driven near-real-time updates | Where a provider supports change events, apply changes from those events with a scheduled-sync fallback so that lag targets in NFR-61 hold even when events are missed or delayed. |
| FR-118 | Sync progress & completion report | Show live progress for a running sync (items seen, created, updated, skipped, failed) and a completion summary with a link into the activity log. |
| FR-119 | Sync activity log / audit trail | Keep a per-connection, per-item chronological record of what changed, in which direction, by which rule, and with which outcome, filterable by date range, direction, and outcome. |
| FR-120 | Failure handling, retry & notification | Classify failures (auth expired, permission denied, rate-limited, provider unavailable, invalid mapping, payload rejected), retry transient classes with backoff, stop retrying permanent classes, and notify the user through the product's notification surface when action is required. |
| FR-121 | Rate-limit & quota handling | Detect provider throttling, defer and re-queue affected work without dropping it, report a `throttled` state on the connection, and never exhaust the provider quota with retry storms. |
| FR-122 | Selective pause | Pause and resume an entire connection or a single scope without deleting mappings, filters, or history; while paused, no inbound changes are applied and no outbound writes are sent. |
| FR-123 | Configuration export/import | Export connection configuration (label, direction, scope, mapping, conflict policy) as a portable file that contains no credentials or tokens, and import it to recreate a connection that then requires fresh authorization. |
| FR-124 | Permission scoping & transfer disclosure | Request only the access scopes the configured mapping and direction require, show the user exactly which fields will be read and written before the connection is activated, and require re-consent before any scope expansion takes effect. |
| FR-125 | Generic outbound webhooks & inbound endpoint | Allow user-defined outbound webhook subscriptions on task events with configurable payload fields and a shared secret, and accept inbound external payloads on a per-user endpoint that are mapped to task fields; both directions respect dedupe, auth, and the activity log. |

**Non-Functional Requirements (global ids — owned range NFR-61..NFR-75)**

| ID | Category | Target |
|---|---|---|
| NFR-61 | Performance — sync latency | Event-driven inbound change becomes visible in the product within 30 s at p95; scheduled-only connections within 60 s of the schedule tick at p95. |
| NFR-62 | Performance — sync throughput | A manual sync of 5,000 scoped items completes within 5 minutes; a manual sync request is acknowledged within 1 s. |
| NFR-63 | Scalability | Support at least 10 connections per user, 100,000 tracked external items per connection, and horizontal scaling of sync workers without per-user manual sharding. |
| NFR-64 | Availability & isolation | 99.9% monthly availability for the integration control plane; a provider outage or integration failure must not block task creation, prioritization (F-1), focus sessions (F-3), or analytics (F-4) for unaffected users. |
| NFR-65 | Security — secrets at rest & in transit | Tokens and shared secrets encrypted at rest with a managed key, TLS 1.2+ in transit, secrets redacted from logs, error messages, telemetry, and configuration exports. |
| NFR-66 | Security — authorization | Least-privilege scopes, per-connection revocation, and re-consent on scope expansion; a disconnect makes the stored credential unusable within 60 s. |
| NFR-67 | Data residency & retention | Integration configuration and sync logs stored in the deployment region declared for the product; sync logs retained per a configurable window (default 90 days) and connection data purged within 30 days of delete. |
| NFR-68 | Privacy & consent | No data is transmitted to a provider unless the user has activated a connection whose disclosed mapping covers that field; the disclosure shown at activation matches the fields actually transmitted. |
| NFR-69 | Observability | Every sync operation carries a correlation id; success rate, lag, queue depth, and error class are measured per connection and per provider, with alert thresholds on sustained failure or lag regression. |
| NFR-70 | Reliability & idempotency | At-least-once delivery with dedupe keys yielding exactly-once effect; a process restart resumes without duplicate tasks and without losing queued changes. |
| NFR-71 | Resilience to provider failure | Circuit breaker per provider, exponential backoff with jitter, bounded retry window, and graceful degradation to scheduled sync when events fail. |
| NFR-72 | Rate-limit fairness | Global and per-connection concurrency caps are configurable; queued work is scheduled fairly so no single connection starves others. |
| NFR-73 | UI responsiveness | Integration list, health, conflict inbox, and activity log views are interactive within 2 s at p95 on a 3G-equivalent connection and remain usable with 1,000 log rows via paging or virtualization. |
| NFR-74 | Deployment & environment | Connection definitions and sandbox/test credentials are environment-configurable; non-production environments never hold production secrets; schema migrations are reversible and integration contracts remain backward compatible for at least two released versions. |
| NFR-75 | Locale & time-zone correctness | External timestamps are normalized to UTC internally and rendered in the user's locale and time zone; date-only external values keep the intended calendar day without time-zone shifting, including across DST boundaries. |

**User Stories (global ids — owned range US-61..US-75)**

- **US-61** — As a busy professional, I want to connect my calendar so that deadline-bearing events appear as tasks automatically.
- **US-62** — As a busy professional, I want to connect my issue tracker and email inbox so that assignments become tasks without retyping.
- **US-63** — As a user, I want to choose which calendars, lists, and projects sync so that I am not flooded with irrelevant tasks.
- **US-64** — As a user, I want to control which fields sync and in which direction so that my data stays consistent with the tool I actually work in.
- **US-65** — As a user, I want conflicting edits resolved by my chosen rule so that I do not have to referee every change.
- **US-66** — As a user, I want a conflict inbox where I can resolve ambiguous cases myself so that nothing is silently overwritten.
- **US-67** — As a user, I want to trigger a sync on demand and watch its progress so that I know exactly when my data is current.
- **US-68** — As a user, I want an activity log of every synced change so that I can audit what happened and why.
- **US-69** — As a user, I want to be told when a connection breaks or expires so that I can restore it before my task list goes stale.
- **US-70** — As a user, I want to pause a connection temporarily without losing its configuration so that I can silence a noisy source and re-enable it later.
- **US-71** — As a user, I want to disconnect an account and have its access revoked so that I stay in control of my data.
- **US-72** — As a user, I want to connect two accounts of the same provider (work and personal) with separate labels so that contexts stay apart.
- **US-73** — As a user, I want imported deadlines to influence my priority queue exactly like native deadlines so that my "Today" list is trustworthy.
- **US-74** — As a user, I want to open the original external item from a task so that I can act on it in its own context.
- **US-75** — As a user, I want tasks created by quick add (F-2) and tasks used in a focus session (F-3) to carry their external link so that context is never lost.

### Behaviour

1. **Connection creation.** The user picks a source type (FR-101), starts authorization (FR-102), is shown the exact fields and direction the connection will use (FR-124), completes the handshake, and lands on a configuration screen where scope (FR-109), direction (FR-107), mapping (FR-108), conflict policy (FR-112), cadence (FR-116), and deletion semantics (FR-115) are set before activation.
2. **Steady-state sync loop.** For each active scope the hub evaluates the source set, classifies each external item as new, changed, unchanged-out-of-scope, or deleted (FR-110, FR-115), applies the field mapping, resolves conflicts per policy (FR-112/FR-113), writes idempotently (FR-114), and records an activity entry per decision (FR-119).
3. **Outbound loop.** Task lifecycle events raised anywhere in the product (including F-2 quick add and F-3 focus completion) are matched against connections with outbound direction and a covering scope, mapped, and written to the provider with dedupe keys (FR-111, FR-114).
4. **Event acceleration.** Where the provider publishes change events, those events enqueue the same work units as scheduled sync; scheduled sync always remains the reconciliation backstop (FR-117).
5. **Failure loop.** Failures are classified, transient classes retried with backoff, permanent classes surfaced to the user, degraded connections flagged in the connection list, and dependent scopes continue independently (FR-120, NFR-71).
6. **Cross-feature integration.** A task linked to an external item renders its source badge and deep link in the task detail view and in focus mode (F-3); its due date and mapped importance participate in prioritization scoring (F-1) under the same rules as native values; its completion state flows into completion metrics (F-4) exactly once.

### Business Rules

- **BR-1** — A connection becomes active only after authorization succeeds, at least one scope is selected, and a field mapping is valid; partial configurations persist as drafts and never sync.
- **BR-2** — Only one task may be linked to a given external item; additional matches update the existing task rather than creating a second one.
- **BR-3** — When the same field is edited in the product and externally between two sync passes, the connection's conflict policy decides the winner; a losing value is always preserved and reversible for the retention window.
- **BR-4** — Deletion semantics are declared before activation; if the user has not declared them, the safe default is "keep as standalone task" with the external link marked broken.
- **BR-5** — A paused connection (FR-122) sends no outbound writes. Changes made while paused are reconciled on resume using the same conflict policy; the resume summary states how many items were reconciled.
- **BR-6** — Disconnecting revokes and destroys the stored credential; already-imported tasks remain subject to the declared deletion semantics, and the user is told the resulting effect before confirming.
- **BR-7** — Sync never overwrites user-authored content with an empty external value; an omitted external field is treated as "no change", not as a deletion, unless the mapping explicitly declares "external authoritative for this field".
- **BR-8** — Imported tasks keep their source attribution permanently visible; removing the connection does not remove provenance from tasks that were kept.
- **BR-9** — Webhook subscriptions (FR-125) are scoped to the owning user's data only; inbound payloads may never address another user's tasks.
- **BR-10** — Configuration export (FR-123) contains no secrets, and import always requires fresh authorization before the imported connection can sync.
- **BR-11 (validation)** — A sync interval must be a whole number of minutes within the supported minimum and maximum; a value below the provider's own minimum is rejected with the provider minimum stated.
- **BR-12 (validation)** — A scope must select at least one container or rule; the empty scope is rejected as "would import nothing".
- **BR-13 (validation)** — A field mapping must map the title-equivalent field; a mapping that leaves the title unmapped cannot be saved as active.
- **BR-14 (validation)** — A conflict policy must name exactly one rule per field; two rules for the same field are rejected as contradictory.
- **BR-15 (validation)** — A webhook secret must meet the minimum length and entropy policy defined for the deployment, and a subscription without a secret cannot be enabled.
- **BR-16 (validation)** — A connection label must be unique within the user's connection list and non-empty.

### Edge Cases

- **EC-1** — The external item's title is empty or whitespace only; the task title falls back to the declared title-default rule rather than creating an untitled task.
- **EC-2** — The external item has a date-only due value; it must not shift to the previous or next day when rendered (NFR-75).
- **EC-3** — An external item moves out of scope (relabelled, reassigned) — it is unlinked per the declared out-of-scope rule, not deleted silently.
- **EC-4** — The same external item is reachable through two scopes on the same connection; it is ingested once, with the union of matched scopes recorded.
- **EC-5** — The same provider account is connected twice under different labels; items are ingested once and attributed to the earliest active connection, with a duplicate-connection warning shown at setup.
- **EC-6** — A very large first sync (over the NFR-62 throughput envelope) proceeds in resumable batches with visible progress, and a refresh mid-sync does not restart it.
- **EC-7** — The user deletes a task that is linked and outbound-synced; the external side follows the declared delete-propagation rule, and if that rule is "ask", the user is prompted once.
- **EC-8** — The user edits a task while an inbound update for the same task is in flight; the in-flight change lands in the conflict inbox rather than overwriting.
- **EC-9** — The provider returns a payload with unexpected or additional fields; unknown fields are ignored, the known fields apply, and the event is logged as partially mapped.
- **EC-10** — A webhook is delivered out of order; ordering is not assumed, and the most-recent-change rule (or the configured rule) decides the final state.
- **EC-11** — Clock skew between the provider and the product pushes an external timestamp into the future or the past; timestamps are stored as received with the skew recorded in the activity log.
- **EC-12 (error handling)** — Authorization expires or is revoked externally: state becomes `expired`, scheduled work stops for that connection only, and the user is notified with a one-action reconnect path.
- **EC-13 (error handling)** — The user revokes access at the provider while a sync is running: the run terminates for that connection, no partial state is left inconsistent, and the connection moves to `disconnected`.
- **EC-14 (error handling)** — The provider is unavailable or returns 5xx: the circuit opens, work is re-queued, and the connection shows `degraded` rather than failing the whole hub.
- **EC-15 (error handling)** — The provider rate-limits or refuses the request: work is deferred with backoff, the connection shows `throttled`, and no item is dropped (NFR-72).
- **EC-16 (error handling)** — Outbound write is rejected as invalid (forbidden field, closed project): the item is quarantined, the task stays intact in the product, and the user is told which task and which reason.
- **EC-17 (error handling)** — An inbound webhook fails authentication or dedupe: it is rejected with no side effect and counted in a rejection metric.
- **EC-18 (error handling)** — Malformed or partially valid import configuration is loaded: valid sections apply, invalid sections are listed with reasons, and nothing activates until the user resolves them.

### Error Handling

- **User-visible errors** name the connection, the affected item count, the reason in plain language, and a single primary recovery action (Reconnect, Adjust scope, Fix mapping, Retry, Open conflict).
- **Transient errors** are never surfaced as user errors while automatic retry is still within its window; only exhaustion or a permanent class triggers notification (FR-120).
- **Input errors** (BR-11..BR-16, EC-18) are reported inline against the offending field and block activation of the affected scope, not activation of unrelated scopes.
- **Data-safety errors** (EC-12..EC-16) must always leave the product-side task in a valid, readable state with provenance retained, even when the external write or read failed.

### Acceptance Criteria

- **AC-1** — Given a valid provider account, when the user completes authorization and sets scope, direction, mapping, and conflict policy, then the connection appears as `connected` and the first sync starts within 60 s. (FR-101, FR-102, FR-103)
- **AC-2** — Given an active inbound connection, when a new matching external item is created and the provider supports events, then a linked task exists within 30 s at p95; when only scheduled sync is available, within one interval. (FR-110, FR-117, NFR-61)
- **AC-3** — Given a task linked to an outbound-synced connection, when the user edits its due date, then the external item's due date matches within one sync cycle. (FR-111)
- **AC-4** — Given a connection in bidirectional mode, when the same field is changed on both sides between sync passes, then the declared policy determines the stored value and the losing value is retrievable from the conflict record. (FR-112, BR-3)
- **AC-5** — Given a conflict record exists, when the user keeps the external value, then the task shows that value and no further conflict is raised for the same change. (FR-113)
- **AC-6** — Given a sync run is interrupted by a restart, when it resumes, then no duplicate task exists and every queued change is applied exactly once. (FR-114, NFR-70)
- **AC-7** — Given an external item is deleted, when the declared deletion rule applies, then the resulting task state matches the rule and the activity log records the decision. (FR-115, BR-4)
- **AC-8** — Given a connection is paused, when task changes occur, then no outbound writes are sent, and on resume a reconciliation summary reports the applied changes. (FR-122, BR-5)
- **AC-9** — Given the provider credential is revoked, when the next sync attempts to run, then the connection enters `expired`, other connections continue unaffected, and the user receives a reconnect notification. (FR-120, EC-12, NFR-64)
- **AC-10** — Given the provider throttles requests, when retries occur, then no item is dropped, the connection reports `throttled`, and retry traffic stays within the configured concurrency caps. (FR-121, EC-15, NFR-72)
- **AC-11** — Given the user opens a task imported from a provider, when they activate the source link, then the external item opens in the provider's own surface. (US-74, FR-110)
- **AC-12** — Given an imported task with an external due date, when the prioritization queue is computed, then that deadline affects the ranking exactly as a native due date would. (FR-110, US-73)
- **AC-13** — Given the user disconnects an account, when the disconnect completes, then the stored credential is unusable within 60 s and kept tasks retain their source attribution. (FR-104, EC-13, NFR-66, BR-8)
- **AC-14** — Given an activity log with more than 1,000 entries, when the user filters by date range and outcome, then the filtered result renders within the NFR-73 budget. (FR-119, NFR-73)
- **AC-15** — Given a configuration export is produced, when it is inspected, then it contains no credentials or tokens, and importing it requires fresh authorization before sync. (FR-123, BR-10)
- **AC-16** — Given a webhook subscription is enabled, when a matching task event occurs, then exactly one signed payload is delivered; an inbound payload replayed with the same dedupe key has no effect. (FR-125, BR-9, EC-17)

### API Behaviour

Transport and concrete protocol are the Architect's decision; the semantics below are binding on whatever interface is chosen. All operations are user-scoped, authorize against the owning user's session, and return a correlation id usable in the activity log.

| ID | Operation | Semantics |
|---|---|---|
| API-1 | List available source types | Returns catalogue entries with the read/write fields each type supports and the scopes it will request. |
| API-2 | Begin authorization | Returns a handshake reference and the destination the user must visit; creates a pending, non-syncing connection draft. |
| API-3 | Complete authorization | Callback/redeem step; on success the draft becomes a configured connection, on failure it returns a classified reason and remains a draft. |
| API-4 | List / read connections | Returns every connection with label, type, state, direction, scope summary, last sync, next sync, and consecutive-failure count. |
| API-5 | Update connection | Accepts label, direction, scope, mapping, conflict policy, cadence, and deletion rule; validates atomically per BR-11..BR-16 and rejects the whole change set on any invalid member. |
| API-6 | Pause / resume connection or scope | Idempotent; resume returns the reconciliation summary. |
| API-7 | Test connection / read health | Performs a live probe; returns state, latency, and the last error in plain language without leaking secrets. |
| API-8 | Disconnect / delete connection | Revokes the credential, applies the declared deletion semantics to retained tasks, and purges connection data per NFR-67. |
| API-9 | Trigger sync | Enqueues a run (or a scoped re-sync); returns a run id immediately and never blocks for completion. |
| API-10 | Read run status | Returns phase, counts (seen, created, updated, skipped, failed, conflicted), and a terminal outcome. |
| API-11 | Read activity log | Cursor-paged, filterable by date range, direction, outcome, and item; entries are read-only and never mutated. |
| API-12 | Resolve conflict | Applies a keep-product / keep-external / per-field-merge decision; the decision is recorded and the resulting value is synced per the connection's direction. |
| API-13 | Inbound webhook receive | Authenticates the caller, dedupes by key, validates the payload, maps it to task fields, and returns a non-retryable status for permanently invalid payloads so senders stop retrying. |
| API-14 | Manage webhook subscriptions | Create/list/update/disable subscriptions; secrets are write-only and returned masked. |
| API-15 | Export / import configuration | Export omits all secrets; import validates and stages configuration, requiring authorization before activation. |

### Data Model (concepts; storage is the Architect's decision)

- **DM-1 Connection** — owner, source type, label, account identity, state, direction, cadence, deletion rule, timestamps.
- **DM-2 Credential record** — connection reference, secret material, expiry, refresh metadata; never readable through any user-facing interface.
- **DM-3 Scope** — connection reference, container/rule selector, direction override, pause flag.
- **DM-4 Field mapping** — connection reference, external field, task field, authority flag, defaults.
- **DM-5 External item link** — connection, external item id, task reference, last seen version, provenance state (linked, broken, out-of-scope).
- **DM-6 Sync run** — connection, trigger type (schedule, manual, event), phase, counts, outcome, correlation id.
- **DM-7 Activity entry** — run reference, external item, task reference, direction, rule applied, outcome, timestamp.
- **DM-8 Conflict record** — task, field, product value, external value, detected time, state, resolution.
- **DM-9 Webhook subscription** — owner, target, event filter, secret reference, enabled flag, delivery stats.
- **DM-10 Provider definition** — source type capabilities, field catalogue, required scopes, minimum interval, event support.

### Priority

| Priority | Requirements |
|---|---|
| **Must-have** | FR-101, FR-102, FR-103, FR-104, FR-105, FR-107, FR-108, FR-109, FR-110, FR-111, FR-112, FR-113, FR-114, FR-115, FR-116, FR-118, FR-119, FR-120, FR-121, FR-122, FR-124 |
| **Should-have** | FR-106, FR-117, FR-123, FR-125 |
| **Nice-to-have** | None in this feature; every requirement above is in scope and none may be dropped without explicit user approval. |

Feature-level priority: **must-have** (the hub is the mechanism by which external commitments enter the user's "Today" queue).

### Traceability

| Requirement | Acceptance | Interface | Data | Notes |
|---|---|---|---|---|
| FR-101, FR-102 | AC-1 | API-1, API-2, API-3 | DM-1, DM-2, DM-10 | T-1: connect flow end-to-end against a sandbox provider account. |
| FR-103, FR-105 | AC-1, AC-9 | API-4, API-6, API-7 | DM-1 | T-2: lifecycle and health state-transition tests. |
| FR-104, FR-124 | AC-13 | API-8, API-15 | DM-2 | T-3: secret-leak scan over logs, errors, and exports. |
| FR-107, FR-108, FR-109 | AC-3 | API-5 | DM-3, DM-4 | T-4: direction/scope/mapping matrix tests. |
| FR-110, FR-117 | AC-2, AC-11, AC-12 | API-9, API-10 | DM-5, DM-6 | T-5: ingest latency and cross-feature ranking tests (F-1). |
| FR-111 | AC-3 | API-9 | DM-5 | T-6: outbound propagation for create/update/complete/reopen/delete. |
| FR-112, FR-113 | AC-4, AC-5 | API-12 | DM-8 | T-7: conflict-policy table tests for all four rules. |
| FR-114 | AC-6 | API-9 | DM-5, DM-6 | T-8: duplicate-event and restart-injection tests. |
| FR-115 | AC-7 | API-8 | DM-5 | T-9: deletion-rule matrix tests for all three semantics. |
| FR-116, FR-118, FR-122 | AC-2, AC-8 | API-6, API-9, API-10 | DM-6 | T-10: cadence, progress, and pause/resume reconciliation tests. |
| FR-119 | AC-14 | API-11 | DM-7 | T-11: activity-log completeness and filter performance tests. |
| FR-120, FR-121 | AC-9, AC-10 | API-7, API-10 | DM-6, DM-7 | T-12: fault-injection tests for each classified error class. |
| FR-123 | AC-15 | API-15 | DM-1, DM-3, DM-4 | T-13: export/import round-trip without secrets. |
| FR-125 | AC-16 | API-13, API-14 | DM-9 | T-14: signed-delivery, dedupe, and rejection tests. |
| NFR-61..NFR-75 | AC-2, AC-6, AC-10, AC-13, AC-14 | API-* | DM-* | T-15: non-functional verification plan owned by the Architect/Implement stages. |

### Open Questions (for the USER — not decided by this agent)

- **OQ-1** — Which source types must be in the launch catalogue (FR-101), and in what order? The catalogue content is a scope decision for the user; this section assumes calendar, email/issue tracker, messaging, and generic webhook bridge are all in scope.
- **OQ-2** — Is true bidirectional write-back required for every connected source type, or is inbound-only acceptable for some types (for example email)? The spec above delivers bidirectional capability per connection and treats it as in scope.
- **OQ-3** — Which deployment region(s) must hold integration configuration and sync logs (NFR-67), and does any provider or user segment impose a residency restriction the spec must reflect?
- **OQ-4** — What is the required default retention for sync logs (assumed 90 days) and for kept tasks after a connection is deleted (assumed retained as standalone tasks)?
- **OQ-5** — Are multiple accounts of the same provider required at launch (FR-106 is marked should-have), or is one account per provider acceptable initially?
- **OQ-6** — Are outbound webhooks and inbound generic endpoints (FR-125) required at launch, or may they follow the first release? They remain in scope in this specification.
