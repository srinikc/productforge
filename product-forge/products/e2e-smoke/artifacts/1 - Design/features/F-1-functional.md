## F-1: Intelligent Task Prioritization

### Requirements

**Functional Requirements (global ids — owned range FR-1..FR-25)**

| ID | Title | Summary |
|---|---|---|
| FR-1 | Automatic priority scoring | The system assigns every active task a numeric priority score derived from the user's prioritization profile. |
| FR-2 | Ranked priority queue | The system exposes an ordered "Today" queue of active tasks sorted by descending priority score. |
| FR-3 | Ranking factors | Scoring uses at minimum: due date/time, explicit user importance, estimated effort, task age, and dependency state. |
| FR-4 | Factor weighting controls | The user can adjust the relative weight of each ranking factor. |
| FR-5 | Explainability | The user can view, per task, a plain-language explanation of why it has its current rank. |
| FR-6 | Manual override | The user can pin a task to the top of the queue or force it into a specific rank position. |
| FR-7 | Override scope and expiry | Overrides can be indefinite or time-boxed (until a date/time or until task completion). |
| FR-8 | Override visibility and removal | Pinned/overridden tasks are visually marked and the override can be removed by the user at any time. |
| FR-9 | Deadline urgency escalation | Tasks approaching or past their due date escalate in score as the deadline nears. |
| FR-10 | Blocked task handling | Tasks blocked by an incomplete dependency are demoted and labelled as blocked. |
| FR-11 | Dependency unblocking | When a blocking task completes, dependent tasks are re-scored and may re-enter the active queue. |
| FR-12 | Recompute triggers | Scores are recomputed on task create/update/complete/delete, due-date change, dependency change, override change, profile change, and on a periodic schedule. |
| FR-13 | Deterministic ordering | Ties are broken deterministically so the queue order is stable across identical recomputes. |
| FR-14 | Priority tiers | Each task is bucketed into a tier (Critical / High / Medium / Low) derived from its score, with tier thresholds configurable. |
| FR-15 | Queue filtering and segmentation | The queue can be filtered (e.g., by project, tag, due window, effort, blocked state) without altering underlying scores. |
| FR-16 | Deferred/hidden tasks | Tasks explicitly deferred by the user are excluded from the active queue but retain their score. |
| FR-17 | Stale score invalidation | A score older than its validity window is flagged stale and refreshed before being presented as authoritative. |
| FR-18 | Bulk recalculation | The user can trigger a full recalculation of all active task scores. |
| FR-19 | Score history | The system retains a bounded history of score changes per task for auditing and trend display. |
| FR-20 | Drift feedback signal | The system accepts lightweight user feedback (e.g., "this is not important") and applies it as a bounded adjustment. |
| FR-21 | Cross-device consistency | The priority queue and overrides are consistent for the same account across devices after sync. |
| FR-22 | Offline override capture | Overrides created while offline are queued locally and reconciled on reconnect using last-write-wins with conflict surfacing. |
| FR-23 | Explanation provenance | Every explanation lists the factors and weights that produced the score at the time it was generated. |
| FR-24 | Queue size limits | The active queue is paginated/limited to a configurable maximum with the remainder accessible via continuation. |
| FR-25 | Priority settings reset | The user can reset weighting and tier thresholds to system defaults. |

**Non-Functional Requirements (owned range NFR-1..NFR-15)**

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | Priority queue retrieval returns first page within 300 ms at p95 for accounts with up to 5,000 active tasks. |
| NFR-2 | Performance | Single-task score recomputation completes within 100 ms at p95. |
| NFR-3 | Performance | Full recalculation of 5,000 active tasks completes within 10 s and runs asynchronously. |
| NFR-4 | Scalability | Scoring must remain correct and within NFR-1 as task count grows linearly to 50,000 active tasks per account. |
| NFR-5 | Availability | Priority queue read endpoints must sustain 99.9% monthly availability; ranking degrades to last-known-good ordering rather than failing. |
| NFR-6 | Security | Only the owning account (or an explicitly delegated collaborator) may read or mutate scores, weights, and overrides. |
| NFR-7 | Security | Override and weighting changes are auditable with actor, timestamp, and before/after values. |
| NFR-8 | Data residency | Priority data, overrides, and score history are stored in the user's configured data region and are not replicated outside it. |
| NFR-9 | Data retention | Score history retains at most 90 days or 500 entries per task, whichever is smaller; overrides persist until removed. |
| NFR-10 | Deployment/environment | Scoring runs identically in local, staging, and production environments; behaviour is controlled by configuration, not environment-specific branches. |
| NFR-11 | Deployment/environment | Weight-profile schema changes are backward compatible for at least one prior version to allow rolling deploys. |
| NFR-12 | Reliability | Recompute operations are idempotent; repeated runs with unchanged inputs produce identical scores. |
| NFR-13 | Observability | Score computation emits metrics for latency, recompute volume, override rate, and stale-score count. |
| NFR-14 | Accessibility | Rank, tier, blocked state, and override markers are conveyed by text/label in addition to colour, and the queue is fully keyboard navigable. |
| NFR-15 | Privacy | Ranking factors must not require content inspection beyond task metadata already stored; no task body text is used unless the user opts in. |

**User Stories (owned range US-1..US-15)**

| ID | Story |
|---|---|
| US-1 | As a busy professional, I want my tasks automatically ordered by what matters most, so that I can start working without deciding what to do first. |
| US-2 | As a user, I want to see why a task is ranked where it is, so that I can trust the ordering. |
| US-3 | As a user, I want to pin a task to the top, so that I can override the system when I know better. |
| US-4 | As a user, I want blocked tasks pushed down, so that I am not nudged toward work I cannot start. |
| US-5 | As a user, I want to tune how much deadlines versus importance matter, so that the ranking matches how I actually work. |
| US-6 | As a user, I want overdue tasks to surface aggressively, so that nothing silently slips. |
| US-7 | As a user, I want to filter the queue without changing scores, so that I can focus on one project at a time. |
| US-8 | As a user, I want to defer a task out of the active queue, so that it stops competing for attention. |
| US-9 | As a user, I want my pins and settings to survive app restarts and device changes, so that my setup is portable. |
| US-10 | As a user, I want to record a pin while offline, so that I am not blocked by connectivity. |
| US-11 | As a user, I want to reset my weighting to defaults, so that I can recover from a bad configuration. |
| US-12 | As a user, I want to force a full recalculation, so that I can correct a queue that looks stale. |
| US-13 | As a user, I want to tell the system a ranking is wrong, so that it adapts over time. |
| US-14 | As a user, I want to remove an override, so that the task returns to automatic ranking. |
| US-15 | As a user, I want a large task list paginated, so that the app stays responsive. |

---

### Behaviour

**Scoring model (conceptual, technology-agnostic)**

Each active task receives a score computed from a bounded set of normalised factors, combined using the user's weighting profile, then adjusted by bounded modifiers.

| DM ID | Concept | Description |
|---|---|---|
| DM-1 | Task | A unit of work with due date/time (optional), importance (user-set), estimated effort, created-at, status, project/tags, and dependency links. |
| DM-2 | PriorityProfile | Per-user configuration: factor weights, tier thresholds, urgency horizon, staleness window, feedback adjustment cap, default override duration. |
| DM-3 | PriorityFactor | A named contributor to a score (e.g., deadline urgency, importance, effort fit, age, dependency state) with its weight and contribution value. |
| DM-4 | PriorityScore | Computed value for a task: numeric score, tier, ordered factor contributions, computed-at timestamp, model/profile version, staleness flag. |
| DM-5 | PriorityOverride | User- or system-created ordering instruction: type (pin / fixed-rank / defer), scope, expiry, creator, reason (optional), active flag. |
| DM-6 | PriorityAuditEvent | Immutable record of a score or override change: actor, timestamp, before/after values, trigger. |
| DM-7 | RankedQueue | The ordered, paginated projection of active tasks after scoring, overrides, deferral, and filtering. |
| DM-8 | FeedbackSignal | A bounded user reaction to a ranking ("too low"/"too high"/"not important") with a decay policy. |

**Behaviour flow**

1. A task is created or modified → the system marks it for scoring (FR-12).
2. The scorer normalises each factor to a comparable 0–1 range and multiplies by the profile weight for that factor (FR-1, FR-3, FR-4).
3. Modifiers apply in a fixed, documented order: dependency/blocked demotion (FR-10), urgency escalation as the deadline nears (FR-9), stale-score invalidation (FR-17), bounded feedback adjustment (FR-20).
4. A numeric score and a tier are produced and persisted with the factor breakdown and profile version (FR-14, FR-23).
5. Overrides are applied on top of the score at queue-assembly time, not baked into the score, so removing an override restores automatic ordering exactly (FR-6, FR-8).
6. The ranked queue is assembled: active, undeferred tasks sorted by override precedence, then score descending, then deterministic tie-breakers (FR-2, FR-13, FR-16).
7. Filters and pagination are applied to the assembled queue without mutating stored scores (FR-15, FR-24).
8. Explanations are generated from the stored factor breakdown of the score that produced the current rank (FR-5, FR-23).

**Ordering precedence (highest to lowest)**
1. Active `fixed-rank` overrides, ascending by target rank.
2. Active `pin` overrides, ordered among themselves by score descending, then tie-breakers.
3. Automatic score descending, then tie-breakers.

**Deterministic tie-breakers (FR-13), applied in order**
1. Earlier due date/time wins; tasks with no due date sort after tasks with one.
2. Higher user importance wins.
3. Older `created-at` wins.
4. Lexicographic ascending task identifier wins (guarantees total order).

**Recompute triggers and scheduling (FR-12, FR-18)**
- Event-driven: task create/update/complete/delete, due-date change, dependency link change, override change, profile change, feedback signal.
- Time-driven: periodic sweep (default every 15 minutes) to catch time-based urgency drift.
- User-driven: explicit full recalculation.
- Sweeps and full recalculations run asynchronously and are idempotent (NFR-3, NFR-12).

**Cross-device and offline behaviour (FR-21, FR-22)**
- Overrides and profile changes carry a client timestamp and a per-record version.
- On reconnect, server reconciles: highest version wins; if two different active overrides target the same task with equal versions, both are preserved in conflict state and the user is asked to choose; until resolved the task is shown with a conflict marker and uses automatic scoring.

---

### Business rules

| ID | Rule |
|---|---|
| BR-1 | Only tasks in an active (not completed, not archived, not deleted) status participate in scoring and the queue. |
| BR-2 | Completing or deleting a task removes it from the queue immediately and triggers recompute of its dependents. |
| BR-3 | A task cannot hold both a `pin` and a `fixed-rank` override simultaneously; the newer instruction replaces the older and the superseded one is recorded in the audit log. |
| BR-4 | A `fixed-rank` override that targets a rank beyond the queue size places the task at the end of the queue. |
| BR-5 | If two tasks are assigned the same `fixed-rank`, the later-created override takes the lower (worse) position and the earlier one shifts up by one. |
| BR-6 | A task with at least one incomplete dependency is demoted below all unblocked tasks with an equal or lower tier and is labelled "Blocked". |
| BR-7 | A blocked task may still be pinned by the user; the user's pin outranks the blocked demotion. |
| BR-8 | An overdue task is placed in the Critical tier regardless of computed score, unless the user has deferred it. |
| BR-9 | Deferred tasks are excluded from the active queue but keep their score and history; the deferral expires at its configured time or never, per BR-10. |
| BR-10 | A deferral without an expiry remains in force until the user removes it or the task is completed. |
| BR-11 | Score history is append-only from the user's perspective; entries are removed only by retention policy (NFR-9), never edited. |
| BR-12 | Feedback adjustments are capped by `feedback adjustment cap` in the profile and decay over time so that repeated feedback cannot permanently dominate ranking. |
| BR-13 | Weights are relative, not absolute: the system normalises weights so the total influence stays constant regardless of the raw numbers entered. |
| BR-14 | Tier thresholds must be strictly descending (Critical > High > Medium > Low); an invalid configuration is rejected, not silently coerced. |
| BR-15 | The queue is always scoped to a single account; no cross-account ranking exists. |
| BR-16 | A stale score is never presented as authoritative without a staleness indicator; the queue may serve last-known-good values while refresh is in flight. |
| BR-17 | A task aged beyond the configured "age ceiling" stops accruing additional age-based score, preventing indefinite drift upward. |
| BR-18 | Removing an override must restore the exact ordering the task would have had under current scores with no override present. |

---

### Validation

Validation applies to all inputs that affect scoring. Violations return a structured error (see API behaviour) and never partially apply.

- Weights: each factor weight must be a finite number in the inclusive range 0–100; at least one weight must be greater than 0. Non-numeric, negative, or out-of-range values are rejected.
- Tier thresholds: finite numbers, strictly descending, and each within the score scale's bounds.
- Urgency horizon: a positive duration, minimum 1 hour, maximum 365 days.
- Staleness window: a positive duration, minimum 60 seconds, maximum 24 hours.
- Feedback adjustment cap: a percentage in the inclusive range 0–50.
- Override type: must be one of `pin`, `fixed-rank`, `defer`.
- `fixed-rank` target: integer ≥ 1.
- Override expiry: an absolute timestamp strictly in the future at the moment of acceptance; relative expiries are converted server-side.
- Deferral without expiry: allowed only if the profile permits indefinite deferral; otherwise an expiry is required.
- Feedback signal value: must be one of the enumerated signals; free-text reasons are optional and length-capped.
- Task fields used in scoring: due date/time, if present, must parse as a valid instant; importance must be within its defined scale; estimated effort must be > 0 when provided.
- Pagination: page size within documented minimum/maximum; cursor must be well-formed and not expired.
- Dependency links: a task cannot depend on itself and cycles among dependencies are rejected.

---

### Edge cases

| ID | Case | Required behaviour |
|---|---|---|
| EC-1 | User has zero active tasks | Queue returns an empty result with an explicit empty-state payload; no error. |
| EC-2 | All active tasks are deferred or blocked | Queue returns the items it has; if none remain, the response indicates only deferred/blocked items exist and surfaces them in a separate count. |
| EC-3 | Task has no due date | Deadline urgency contributes nothing; the task is ranked on remaining factors only. |
| EC-4 | Task has no estimated effort | Effort factor is treated as neutral (contributes zero), not as zero effort. |
| EC-5 | Due date changed to the past | Task becomes overdue per BR-8 and is recomputed immediately. |
| EC-6 | Due date removed | Urgency contribution drops to zero; the change is reflected in the next recompute and in the explanation. |
| EC-7 | Clock skew between client and server | Server time is authoritative for urgency and expiry; client-supplied timestamps are used only for conflict resolution ordering, not for urgency. |
| EC-8 | Two clients pin different tasks within the same second | Both pins are honoured; relative order among pins falls back to score, then tie-breakers. |
| EC-9 | Same task pinned on two devices offline | Reconciles to a single pin (last-write-wins by version); no duplicate override records. |
| EC-10 | Override expires while the queue is being read | The read returns a consistent snapshot; the expiry takes effect at the next read or recompute, not mid-response. |
| EC-11 | Task is completed while pinned | Completion wins; the task leaves the queue and the override is marked inactive, retained in history. |
| EC-12 | Dependency chain longer than the configured depth | Cycle detection and depth cap prevent unbounded traversal; the task is labelled Blocked with the chain depth reported. |
| EC-13 | All weights set to zero | Rejected by validation; the previously saved profile remains in force. |
| EC-14 | Account exceeds the queue maximum | Queue is truncated per FR-24 with a continuation cursor and a count of remaining items. |
| EC-15 | Full recalculation requested while one is already running | The second request is coalesced into the running job; the user is told a recalculation is already in progress. |
| EC-16 | Stale scores served during an outage of the scoring path | Queue serves last-known-good ordering with a staleness indicator (NFR-5, BR-16); no error page. |
| EC-17 | Profile version newer than the scorer supports | The system falls back to the last supported profile version, flags the fallback, and logs an alert. |
| EC-18 | Task deleted between queue assembly and explanation fetch | Explanation request returns a not-found outcome with a clear message, not an internal error. |
| EC-19 | Very large task count (50,000 active) | Ranking honours NFR-4; pagination and asynchronous recompute keep responses within NFR-1. |
| EC-20 | User submits contradictory feedback repeatedly in a short window | Adjustment is capped (BR-12) and decays; no unbounded score movement. |

---

### Error handling

| ID | Condition | Handling |
|---|---|---|
| EH-1 | Invalid profile (weights/thresholds/horizons) | Reject with a 422-style validation outcome listing every offending field; no partial save. |
| EH-2 | Invalid override payload | Reject with the same structured validation outcome; existing overrides unchanged. |
| EH-3 | Override targets a task not owned by the account | Reject without revealing task existence; no state change. |
| EH-4 | Recompute job fails partway | Job is retryable and idempotent; previously written scores remain valid; failures are recorded in the audit log and surfaced in observability (NFR-13). |
| EH-5 | Scoring dependency (e.g., dependency graph store) unavailable | Serve last-known-good queue with staleness indicator; queue reads never 5xx solely because scoring is unavailable. |
| EH-6 | Queue cursor expired or invalid | Return a defined "cursor expired" outcome instructing the client to restart pagination from the first page. |
| EH-7 | Optimistic-concurrency conflict on profile update | Reject the second write with a conflict outcome including the current version; client must re-read and retry. |
| EH-8 | Rate limit exceeded on recompute or feedback endpoints | Return a throttling outcome with a retry-after hint; no work is queued. |
| EH-9 | Unexpected internal error in scoring | Task retains its last valid score; the error is logged with a correlation id and never blocks queue reads. |
| EH-10 | Explanation requested for a task with no stored breakdown | Recompute on demand; if unavailable, return an explicit "explanation unavailable" outcome rather than an empty or misleading one. |

---

### Acceptance criteria

| ID | Criterion |
|---|---|
| AC-1 | Given a set of active tasks with distinct due dates and importances, when the queue is fetched, then tasks are ordered by descending score with the documented tie-breakers applied. |
| AC-2 | Given an overdue task, when the queue is fetched, then the task appears in the Critical tier unless deferred. |
| AC-3 | Given a task with an incomplete dependency, when the queue is fetched, then it appears below unblocked tasks of equal or lower tier and is labelled Blocked. |
| AC-4 | Given the blocking task is completed, when recompute finishes, then the previously blocked task is re-scored and appears in its automatic position. |
| AC-5 | Given a user pins a task, when the queue is fetched, then the pinned task appears above all non-pinned tasks and is visually marked as pinned. |
| AC-6 | Given a pin is removed, when the queue is fetched, then the task's position exactly matches its position under current scores with no override. |
| AC-7 | Given a user requests an explanation for a task, then the response lists every factor, its weight, its contribution, the profile version, and the computation timestamp. |
| AC-8 | Given a user changes a factor weight, when the profile save succeeds, then all affected scores are recomputed and the new ordering is served. |
| AC-9 | Given all weights are set to zero, when the user attempts to save, then the save is rejected with a field-level error and the previous profile remains in force. |
| AC-10 | Given a task is deferred with an expiry, then it is absent from the active queue before expiry and present after the expiry time following the next recompute. |
| AC-11 | Given a task is completed, then it leaves the queue immediately and dependents are recomputed. |
| AC-12 | Given an account with 5,000 active tasks, then first-page queue retrieval meets the p95 latency target in NFR-1. |
| AC-13 | Given an account with 50,000 active tasks, then ranking is correct and pagination returns the full ordered set via cursors. |
| AC-14 | Given a full recalculation of 5,000 tasks is triggered, then it completes asynchronously within NFR-3 and produces scores identical to an incremental recompute of the same inputs. |
| AC-15 | Given two recomputes run with identical inputs, then the resulting scores and queue order are byte-identical (NFR-12). |
| AC-16 | Given an override is created offline, when connectivity returns, then the override is applied and visible on all of the user's devices. |
| AC-17 | Given conflicting offline overrides on the same task, then a conflict state is surfaced and the task uses automatic scoring until resolved. |
| AC-18 | Given scoring is unavailable, then the queue still returns the last-known-good order with a staleness indicator and HTTP success. |
| AC-19 | Given the user resets settings, then weights and tier thresholds return to documented defaults and scores are recomputed. |
| AC-20 | Given a non-owner attempts to read or mutate another account's scores, weights, or overrides, then the request is rejected without data leakage. |
| AC-21 | Given the queue is navigated using keyboard only, then every item, explanation trigger, and override control is reachable and labelled (NFR-14). |
| AC-22 | Given tier and override state, then they are distinguishable without relying on colour alone. |
| AC-23 | Given repeated contradictory feedback within a short window, then the cumulative adjustment never exceeds the configured cap. |
| AC-24 | Given a task aged beyond the age ceiling, then its age contribution stops increasing. |
| AC-25 | Given a user filters the queue by project, then the underlying stored scores are unchanged and clearing the filter restores the original order. |

---

### API behaviour

All endpoints are account-scoped and require authentication. All responses use a stable envelope: `data`, `meta` (pagination, profile version, staleness), and `errors` (array of field-level problems). Writes are idempotent where noted.

| ID | Method & path | Purpose | Key inputs | Success | Notable failures |
|---|---|---|---|---|---|
| API-1 | `GET /priority/queue` | Fetch the ranked active queue | `cursor`, `limit`, `filter[project]`, `filter[tag]`, `filter[dueWindow]`, `filter[blocked]`, `filter[tier]` | 200 with ordered items (task id, score, tier, blocked flag, override marker, stale flag) plus `meta.nextCursor` and `meta.profileVersion` | EH-6, EH-5, EH-8 |
| API-2 | `GET /priority/tasks/{taskId}/score` | Fetch a task's current score and factor breakdown | `taskId` | 200 with score, tier, factors, `computedAt`, `profileVersion`, `stale` | EH-10, EH-3 |
| API-3 | `GET /priority/tasks/{taskId}/explanation` | Fetch the plain-language explanation of current rank | `taskId`, `locale` | 200 with summary text plus the structured factor list and the rank it explains | EH-10, EH-3, EC-18 |
| API-4 | `POST /priority/tasks/{taskId}/overrides` | Create a pin, fixed-rank, or defer override | `type`, `targetRank` (fixed-rank only), `expiresAt` (optional), `reason` (optional), `clientVersion` | 201 with the created override and the resulting queue position | EH-2, EH-3, EH-7, EC-8 |
| API-5 | `DELETE /priority/tasks/{taskId}/overrides/{overrideId}` | Remove an override | `overrideId` | 204; subsequent queue reads reflect automatic ordering (AC-6) | EH-3, EH-6 |
| API-6 | `GET /priority/tasks/{taskId}/overrides` | List overrides for a task, including inactive history | `taskId`, `includeInactive` | 200 with override records and audit metadata | EH-3 |
| API-7 | `GET /priority/profile` | Read the user's weighting profile | — | 200 with weights, tier thresholds, horizons, staleness window, feedback cap, defaults for comparison | — |
| API-8 | `PUT /priority/profile` | Replace the weighting profile | Full profile body + `version` | 200 with normalised profile and `version` incremented; recompute scheduled | EH-1, EH-7 |
| API-9 | `POST /priority/profile/reset` | Reset weights and thresholds to defaults | optional `scope` (weights only / all) | 200 with default profile and recompute scheduled | EH-7 |
| API-10 | `POST /priority/recompute` | Trigger full recalculation | `scope` (account / project / task), `dryRun` (optional) | 202 with job id and status URL; coalesced if already running (EC-15) | EH-4, EH-8, EC-15 |
| API-11 | `GET /priority/recompute/{jobId}` | Poll recalculation status | `jobId` | 200 with state (`queued`/`running`/`succeeded`/`failed`), counts, and errors summary | EH-4 |
| API-12 | `POST /priority/tasks/{taskId}/feedback` | Submit a bounded ranking-feedback signal | `signal` (enum), `reason` (optional) | 200 with the adjusted score and the applied (capped) delta | EH-2, EH-8, EC-20 |
| API-13 | `POST /priority/queue/reorder` | Persist an explicit user drag-reorder as fixed-rank overrides | ordered list of task ids + `clientVersion` | 200 with the created/replaced overrides and the resulting order | EH-2, EH-7, BR-5 |
| API-14 | `GET /priority/tasks/{taskId}/history` | Read bounded score history | `taskId`, `limit`, `cursor` | 200 with entries (score, tier, trigger, actor, timestamp) within retention limits | EH-6, NFR-9 |

**Cross-cutting API rules**
- Read endpoints never fail solely because scoring is unavailable; they degrade per EH-5 and set `meta.stale = true`.
- Write endpoints validate fully before mutating; validation failures return field-level `errors` and change nothing (EH-1, EH-2).
- Override and profile writes require a client-supplied `version` for optimistic concurrency; mismatches return a conflict outcome (EH-7).
- `POST /priority/recompute` and `POST /priority/tasks/{taskId}/feedback` accept an idempotency key; replays return the original outcome.
- Pagination cursors are opaque, time-bounded, and account-scoped; expiry is explicit (EH-6).
- All list endpoints are stable-sorted: identical request parameters against unchanged state return identical ordering.

---

### Tests

| ID | Type | What it proves |
|---|---|---|
| T-1 | Unit | Factor normalisation and weighted combination for boundary inputs (0, max, missing). |
| T-2 | Unit | Tie-breaker chain produces a total order for fully equal scores. |
| T-3 | Unit | Weight normalisation keeps total influence constant across raw scales (BR-13). |
| T-4 | Unit | Override precedence: fixed-rank beats pin beats automatic. |
| T-5 | Unit | Removing an override restores the pre-override position exactly (AC-6, BR-18). |
| T-6 | Unit | Feedback adjustment is capped and decays (BR-12, EC-20). |
| T-7 | Unit | Age ceiling stops further age contribution (BR-17, AC-24). |
| T-8 | Unit | Validation rejects zero-weight, non-descending thresholds, and past expiries (EH-1, EH-2). |
| T-9 | Integration | Event-driven recompute fires on every trigger listed in FR-12. |
| T-10 | Integration | Dependency completion re-scores dependents and unblocks them (AC-4). |
| T-11 | Integration | Cycle and self-dependency in the dependency graph are rejected. |
| T-12 | Integration | Full recalculation output equals incremental recompute output for identical inputs (AC-14, NFR-12). |
| T-13 | Integration | Idempotency keys on recompute and feedback produce single effects. |
| T-14 | Integration | Optimistic-concurrency conflict returns conflict and preserves stored profile (EH-7). |
| T-15 | Performance | Queue first page within p95 target at 5,000 active tasks (NFR-1). |
| T-16 | Performance | Single-task recompute within p95 target (NFR-2). |
| T-17 | Performance | Full recalculation of 5,000 tasks within the NFR-3 budget. |
| T-18 | Scale | Correct ranking and pagination at 50,000 active tasks (NFR-4, EC-19). |
| T-19 | Resilience | Scoring unavailability yields last-known-good queue with staleness flag (EH-5, AC-18). |
| T-20 | Resilience | Mid-job failure leaves prior scores valid and the job retryable (EH-4). |
| T-21 | Security | Cross-account read and write attempts are rejected (NFR-6, AC-20). |
| T-22 | Security | Override and weighting changes produce audit records with actor and before/after values (NFR-7). |
| T-23 | Accessibility | Keyboard-only navigation and non-colour-dependent state labels (NFR-14, AC-21, AC-22). |
| T-24 | Sync | Offline override capture and reconnect reconciliation, including conflicts (AC-16, AC-17). |
| T-25 | Retention | Score history respects the 90-day / 500-entry bound (NFR-9). |

---

### Open questions

| ID | Question | Why it needs the user, not the designer |
|---|---|---|
| OQ-1 | What should the default weighting profile be (relative emphasis of deadline vs. importance vs. effort vs. age)? | This encodes the product's opinion about how users *should* work; the designer must not decide it unilaterally. |
| OQ-2 | Should overdue tasks always occupy the Critical tier, or only up to a configurable number so that a large backlog does not flatten the tier's meaning? | Changes visible behaviour and prioritisation philosophy. |
| OQ-3 | How much of the factor breakdown should be exposed to the user — full weights and contributions, or a simplified natural-language summary only? | Trade-off between trust/transparency and cognitive load; a product decision. |
| OQ-4 | Is indefinite deferral allowed, or must every deferral have an expiry? | Affects whether tasks can be permanently hidden from ranking. |
| OQ-5 | What is the intended queue maximum before pagination, and is a finite "Today" queue (e.g., top 10) the primary surface? | Determines the primary UX surface and the meaning of rank. |
| OQ-6 | Should feedback signals persist indefinitely or expire entirely after the decay window? | Affects long-term ranking personalisation and audit expectations. |
| OQ-7 | Confirm the data region(s) in which priority data must reside, and whether any cross-region replication is permitted. | Regulatory/product constraint that the designer cannot assume. |

---

### Priority

**must-have** — F-1 is the core differentiator of the product: the "Today" queue's value depends entirely on intelligent ordering. Within F-1, the must-have subset is FR-1 through FR-16 plus FR-12, FR-13, FR-17, FR-21, FR-23 (scoring, ranked queue, factors, weighting, explainability, override with expiry and removal, urgency escalation, blocked handling, dependency unblocking, recompute triggers, deterministic ordering, tiers, filtering, deferral, staleness, cross-device consistency, explanation provenance), along with NFR-1 through NFR-9, NFR-12, NFR-14, and US-1 through US-11 and US-14.

**should-have** — FR-18 through FR-20, FR-22, FR-24, FR-25 (bulk recalculation, score history, drift feedback, offline override capture, queue limits, settings reset), NFR-13, NFR-15, and US-12, US-13, US-15.

**nice-to-have** — Trend visualisation derived from DM-6/DM-4 history and any additional ranking factors beyond the five baseline factors in FR-3.
