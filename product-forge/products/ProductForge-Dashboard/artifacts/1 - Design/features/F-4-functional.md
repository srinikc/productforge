## F-4: Portfolio Management

**Feature ID:** F-4
**Summary:** F-4 covers the portfolio layer of Product Forge: creating and governing portfolios as durable groups of pipeline projects, controlling which projects belong to them, and presenting an aggregated, always-current view of everything happening across those projects — run counts by status, gate backlog, failure counts, capacity pressure, and last activity. F-1 exposes a portfolio grouping and roll-up on the project registry; F-4 owns the full portfolio resource, its membership rules, its roll-up semantics, its scoped bulk operations over member projects and runs, its authorization scope, and its reporting surface. F-2 allows assigning a new project to a portfolio during creation; F-4 defines the portfolio being assigned to.

**Boundary note:** F-4 does not own project records (F-1), run/stage execution (F-3), or model tier definitions (F-2). F-4 reads their authoritative state to compute roll-ups and issues scoped commands against them. Where F-4 triggers a run, the run is created and governed by the run initiation and pre-flight rules of F-3.

---

### Requirements

#### Functional Requirements

| ID | Name | Requirement | Priority |
|---|---|---|---|
| FR-66 | Portfolio registry and lifecycle | Create, read, list, update, archive, restore, and permanently delete portfolios. Every portfolio carries a stable immutable identifier, name, description, owner, tags, visibility, lifecycle state (`active` / `archived`), configuration revision, and creation/update timestamps. Archived portfolios reject mutations to membership and configuration while remaining readable. | must-have |
| FR-67 | Portfolio metadata and identity | Maintain descriptive metadata per portfolio: name, description (up to the documented character limit), owner, one or more tags, visibility scope, and an optional display accent (icon/colour token from a fixed system palette). Metadata is editable and every edit bumps the configuration revision. | must-have |
| FR-68 | Project membership assignment | Assign a project to a portfolio and remove it from that portfolio. A project belongs to at most one portfolio at a time. Assignment is an explicit operation with an optional reason note that is captured in the audit trail. Membership is idempotent: re-assigning an already-member project succeeds without creating a duplicate membership. | must-have |
| FR-69 | Bulk membership operations | Add or remove many projects in a single operation, addressed by explicit project identifiers or by a declarative selector (e.g. tag, status, owning team). The operation returns a per-item outcome so partial success is visible and reportable, and is safe to retry using a caller-supplied idempotency key. | must-have |
| FR-70 | Portfolio hierarchy | Support optional parent/child nesting so a portfolio can roll up sub-portfolios. Depth is bounded, parent references must be acyclic, and a portfolio has at most one parent. Roll-up metrics of a parent include the contributions of all descendant portfolios exactly once. | should-have |
| FR-71 | Cross-project aggregate roll-up | Compute and serve an aggregate view across the portfolio's member projects (and descendants, when nesting is used): total projects, projects by lifecycle state, run counts grouped by run status, gate backlog count, failure count over a rolling window, capacity utilisation, and last activity timestamp. Aggregates are derived from authoritative project and run records — never from client-supplied or manually edited values. | must-have |
| FR-72 | Derived portfolio health state | Derive a single, documented health indicator per portfolio (`healthy` / `attention` / `degraded` / `unknown`) from transparent, published thresholds over failures, gate backlog age, stalled runs, and capacity saturation. The indicator exposes the contributing factors that produced it so the operator can see *why* a portfolio is not healthy. | must-have |
| FR-73 | Portfolio dashboard view | Present a single-screen portfolio overview: header with identity and health, roll-up counters, a member-project table with per-project status and last activity, an attention queue (failed runs, aged gates, stalled projects), and drill-through links into the project and run detail of F-1/F-3. | must-have |
| FR-74 | Portfolio-scoped run initiation | Launch runs across selected member projects in one action, subject to each project's own readiness checks. Projects that fail pre-flight are reported per-item and are not started; the operation is never all-or-nothing unless the caller explicitly requests atomic behaviour and every project is ready. | should-have |
| FR-75 | Portfolio-scoped run control | Apply pause, resume, cancel, and retry to the running work of selected member projects. Each command is scoped to visible, permitted runs, is recorded as an auditable command against every affected run, and returns a per-project/per-run outcome. | must-have |
| FR-76 | Aggregated human-in-the-loop gate backlog | Provide a unified queue of pending human-in-the-loop gates across all member projects, ordered by age by default, showing gate type, pipeline stage, originating project, waiting duration, and assigned lead where known. The queue deep-links into the gate decision surface owned by the run experience. | must-have |
| FR-77 | Filter, sort, and search across member projects | Filter the member-project view by lifecycle state, run status, health, tags, owner, model tier, and last-activity window; sort by any displayed column; and free-text search over project name, description, and tags. Filter state is encodeable in the view state so it can be shared or saved. | must-have |
| FR-78 | Saved views | Save a named combination of filters, sorting, visible columns, and grouping per portfolio, scoped to the saving user (and optionally shared to the portfolio's members). Saved views are re-evaluated on load against current data; a view never stores a frozen copy of results. | should-have |
| FR-79 | Portfolio metrics and trends | Serve time-bucketed metrics for the portfolio: runs started/completed/failed per bucket, average stage duration, gate wait time, throughput, and failure rate, with a caller-selectable time range and bucket granularity within documented retention limits. | should-have |
| FR-80 | Portfolio concurrency and capacity budget | Allow an optional concurrency budget per portfolio limiting how many member-project runs may execute simultaneously. When the budget is exhausted, newly requested runs are queued or rejected according to the documented policy, and the dashboard surfaces the saturation state. | nice-to-have |
| FR-81 | Portfolio membership roles and authorization scope | Support roles on a portfolio (`owner`, `maintainer`, `viewer`) that determine who may mutate membership/configuration, who may issue scoped run commands, and who may only read. Portfolio role checks are enforced on every portfolio endpoint, and the authorization scope of a portfolio command is exactly its member projects and their runs. | must-have |
| FR-82 | Portfolio subscriptions and digests | Allow users to subscribe to a portfolio and choose notification channels and cadence (immediate for critical events, daily or weekly digest). Digest content is a roll-up summary plus the attention queue, and every notification links to the originating entity. | should-have |
| FR-83 | Snapshot export and reporting | Export a portfolio snapshot as a structured, machine-readable document and as a flat tabular form, including portfolio metadata, member-project rows, roll-up counters, and the attention queue as of the export timestamp. Every export carries the generation timestamp and the data-freshness watermark. | should-have |
| FR-84 | Portfolio audit history | Record every portfolio mutation — creation, metadata change, membership change, archive/restore, delete, role change, configuration change, and every scoped bulk command — with actor, timestamp, prior and new value, reason note when supplied, and the resulting per-item outcome for bulk operations. History is append-only and queryable by time range, actor, and action type. | must-have |
| FR-85 | Portfolio templates and defaults | Allow a portfolio to define defaults applied to projects created into it: default pipeline definition and pinned version, default model tier, default tags, and default gate policy. Defaults are advisory-plus-applied, meaning they pre-populate creation flows and are recorded on the project at creation. | nice-to-have |
| FR-86 | Default inheritance without retroactive mutation | Applying or changing portfolio defaults affects only projects created afterwards, or existing projects explicitly opted in by an operator. Changing a portfolio default must never silently mutate the pinned pipeline version or model tier of an existing project. | must-have |
| FR-87 | Archive semantics and cascade | Archiving a portfolio marks it read-only for membership and configuration, removes it from default active listings, and leaves member projects and their in-flight runs untouched and fully operational. Archiving a parent does not archive its children; each portfolio's lifecycle state is independent. | must-have |
| FR-88 | Delete semantics and referential integrity | Permanently delete a portfolio only when it has no member projects and no child portfolios, or when the caller supplies an explicit resolution (reassign members to another portfolio, or detach them to unassigned). Deletion is rejected while any such reference remains unresolved; the rejection enumerates the blocking references. | must-have |
| FR-89 | Portfolio event stream | Emit a durable, ordered event stream for portfolio lifecycle, membership, health-transition, budget-saturation, and gate-backlog-threshold events, with at-least-once delivery and a documented event envelope. Consumers can subscribe with a delivery endpoint or poll the stream from a stored cursor. | nice-to-have |
| FR-90 | Roll-up freshness, caching, and staleness signalling | Every aggregated response carries a data-freshness watermark and a staleness flag. Aggregates may be served from a cache that is invalidated by the underlying project/run events; when the cache is stale beyond the documented window, the response must say so rather than present stale numbers as current. | must-have |

#### Non-Functional Requirements

| ID | Category | Target and measurement |
|---|---|---|
| NFR-38 | Performance — read latency | Portfolio roll-up and dashboard reads: p95 < 500 ms and p99 < 1.5 s for a portfolio of up to 500 member projects, measured server-side at the API boundary under nominal load. |
| NFR-39 | Scalability | The system supports at least 5,000 portfolios, 50,000 projects, 100 members per portfolio, and 1,000 child portfolios per parent without functional degradation; verified by load test at documented scale with p95 read latency within NFR-38. |
| NFR-40 | Availability | Portfolio read endpoints achieve 99.9 % monthly availability; portfolio mutating endpoints achieve 99.5 %. Measured from external synthetic probes. |
| NFR-41 | Consistency | Roll-up convergence latency ≤ 5 s after an underlying project/run state change, measured from the change event to the served aggregate reflecting it; enforced by an automated convergence test. |
| NFR-42 | Security | Every portfolio endpoint enforces authentication and portfolio-scoped authorization (FR-81). No endpoint returns data for a project outside the caller's authorized scope. Verified by an authorization test matrix covering all roles × all endpoints, plus negative tests for cross-portfolio access. |
| NFR-43 | Auditability and retention | Audit records (FR-84) are append-only, tamper-evident, and retained ≥ 400 days; deletion of a portfolio does not delete its audit history. Verified by attempting an update/delete of an audit record and by retention policy inspection. |
| NFR-44 | Data residency | Portfolio records and their derived aggregates are stored and processed in the region configured for the owning tenant; no cross-region replication of portfolio data unless explicitly configured. Verified by configuration inspection and residency test in a second region. |
| NFR-45 | Concurrency control | Concurrent mutations to the same portfolio are serialized or rejected via optimistic concurrency; a mutation against a stale configuration revision returns a conflict rather than silently overwriting. Verified by parallel-write test. |
| NFR-46 | Pagination and result bounds | All list endpoints are cursor-paginated with a default page size of 50 and a hard maximum of 200; unbounded list responses are not permitted. Roll-up endpoints return counters, not unbounded row sets. Verified by requesting > maximum page size and asserting truncation plus continuation cursor. |
| NFR-47 | Idempotency | Bulk membership and bulk run-control operations accept a caller-supplied idempotency key; replaying the same key with the same payload returns the original outcome without re-applying effects. Verified by duplicate-submission test. |
| NFR-48 | Rate limiting and backpressure | Bulk operations are rate-limited per principal with a documented limit; exceeding it returns a retry-after hint. Bulk operations over large selectors are processed in bounded chunks and never hold a request open beyond the documented synchronous timeout. Verified by burst test. |
| NFR-49 | Accessibility | All portfolio views meet WCAG 2.1 AA: 4.5:1 contrast for text and 3:1 for UI components, full keyboard operability including the member table and gate queue, visible 2 px focus indicators, semantic table headers, and status conveyed by text as well as colour. Verified by automated audit plus manual keyboard/screen-reader pass. |
| NFR-50 | Frontend responsiveness | Portfolio dashboard Largest Contentful Paint < 2.5 s and Interaction to Next Paint < 200 ms on a mid-tier device over a throttled connection; the member table virtualizes or paginates so first paint does not wait on the full roster. Verified by lab performance run. |
| NFR-51 | Observability | Portfolio operations emit structured logs, counters, and traces covering request outcome, roll-up computation time, cache hit/miss, staleness served, bulk operation item counts, and authorization denials. Dashboards and alerts exist for NFR-38/48/49 thresholds. Verified by inspecting telemetry during a load test. |
| NFR-52 | Deployment and environment | All portfolio behaviour is configurable through environment-scoped configuration (health thresholds, cache TTLs, rate limits, retention windows) with no secrets in client-side assets; schema changes ship with forward and backward migrations and a documented backfill for existing projects that have no portfolio membership. Verified by deploying to a clean environment and by migration dry-run. |

#### User Stories

| ID | Story |
|---|---|
| US-31 | As a Product Forge Operator, I want to create a portfolio with a name and description, so that I have a durable container for a group of related projects. |
| US-32 | As a Product Forge Operator, I want to assign existing projects to a portfolio, so that related work is grouped and tracked together. |
| US-33 | As a Product Forge Operator, I want to move a project from one portfolio to another, so that grouping stays correct as priorities change. |
| US-34 | As a Product Forge Operator, I want to onboard many projects into a portfolio in one action, so that setting up a new programme does not require dozens of individual edits. |
| US-35 | As a Product Forge Operator, I want a roll-up dashboard for a portfolio, so that I can see the state of all member projects without opening each one. |
| US-36 | As a Product Forge Operator, I want a single health indicator with visible contributing factors, so that I can tell at a glance whether a portfolio needs attention and why. |
| US-37 | As a Product Forge Operator, I want a unified queue of pending human-in-the-loop gates across the portfolio, so that I can clear decisions that are blocking multiple projects. |
| US-38 | As a Product Forge Operator, I want to start runs for several member projects at once, so that I can kick off a programme-wide cycle efficiently while still being told which projects were not ready. |
| US-39 | As a Product Forge Operator, I want to pause or cancel runs across a portfolio in one action, so that I can stop work quickly during an incident or a budget freeze. |
| US-40 | As a Product Forge Operator, I want to filter and search the member-project list by status, health, tag, and recency, so that I can find the projects that need me right now. |
| US-41 | As a Product Forge Operator, I want to save a filtered view of a portfolio, so that my recurring triage is one click instead of a repeated filter exercise. |
| US-42 | As a Product Forge Operator, I want to see trend metrics for a portfolio, so that I can tell whether throughput and failure rates are improving. |
| US-43 | As a Product Forge Operator, I want to export a portfolio snapshot, so that I can share an accurate status report with stakeholders. |
| US-44 | As a Portfolio Owner, I want to grant a teammate viewer or maintainer access to a portfolio, so that they can see or act on exactly the projects that belong to it and nothing more. |
| US-45 | As a Product Forge Operator, I want to subscribe to a portfolio digest, so that I learn about failures and aged gates without watching the dashboard. |

---

### Behaviour

**Creation and metadata (FR-66, FR-67, FR-85).** A portfolio is created with a name, optional description, owner identity, tags, and visibility. Creation may optionally declare a parent portfolio (FR-70) and defaults for member projects (FR-85). On success the response returns the portfolio with its immutable identifier and initial configuration revision `1`. Subsequent metadata edits increment the revision. Every create and edit is captured as an audit record (FR-84).

**Membership (FR-68, FR-69).** Assigning a project writes a membership record linking the project to the portfolio. Because a project has at most one portfolio (BR-1), assigning a project already held by another portfolio either fails with a conflict naming the current portfolio, or, when the caller supplies an explicit reassignment intent, performs a single atomic move recorded as two audit entries (detach from source, attach to destination) sharing a correlation id. Removing a project detaches it to the unassigned state and never deletes the project or its runs. Bulk operations (FR-69) evaluate the selector at execution time, process members in bounded chunks, and return a per-item result list with a summary count of applied, skipped, and failed items.

**Roll-up computation (FR-71, FR-72, FR-90).** Roll-ups are derived views. For each member project the aggregation reads its current lifecycle state, its run counts grouped by run status, its pending gate count and the age of its oldest pending gate, its failure count within the configured rolling window, its concurrency utilisation, and its last activity timestamp. Counters are summed; the "last activity" is the maximum across members; gate backlog age is the maximum age observed. When nesting is enabled, a parent's aggregate adds each descendant's own aggregate exactly once (BR: no double counting when a project is reachable by one path only, which is guaranteed by the single-parent rule). Health is computed from the published thresholds and the response includes the contributing factors. Responses carry a freshness watermark; if the aggregate was served from a cache whose watermark is older than the configured staleness window, `stale: true` is set and the UI displays a freshness note.

**Dashboard interaction (FR-73, FR-77, FR-78).** The dashboard issues one aggregate read plus one paginated member-list read. Selecting a member row navigates into the project detail owned by F-1. Applying a filter re-requests the member page with the filter state; the aggregate counters reflect the whole portfolio, not the filtered subset, and the UI labels them accordingly so filtered views cannot be mistaken for portfolio totals. A saved view stores only the query state plus a name and sharing scope, never a materialised result set.

**Scoped commands (FR-74, FR-75, FR-76, FR-80).** Portfolio-scoped commands resolve their target set at execution time and then delegate to the underlying capability: run initiation delegates to the run initiation and pre-flight rules of F-3 per project, run control delegates to run control of F-3 per run, and gate decisions remain on the run-experience surface — F-4 only aggregates and links. For non-atomic bulk commands, partial success is a normal outcome and is reported per item; the operator is never told "failed" when part of the work succeeded. When a concurrency budget is configured, run initiation first reserves budget, then starts what fits, and reports the remainder as queued or rejected per the configured policy.

**Authorization (FR-81).** Every portfolio request resolves the caller's role on that portfolio. Viewers may read dashboards, roll-ups, metrics, exports, and audit history for their portfolio. Maintainers may additionally mutate membership, apply run control, and start runs. Owners may additionally edit metadata, manage roles, configure defaults and budget, and archive, restore, or delete. Commands never reach projects outside the portfolio; a target identifier that resolves outside the caller's portfolio scope is rejected as not found rather than as forbidden, so existence is not leaked.

**Lifecycle (FR-87, FR-88).** Archive is reversible and non-destructive: membership and configuration freeze, the portfolio leaves default active listings, and member projects and their runs continue unaffected. Restore returns the portfolio to active with its prior configuration revision preserved and a new revision noting the restore. Delete is permanent and requires that no membership or child references remain; otherwise the request is rejected with the enumerated blocking references and a suggested resolution. Deleting a portfolio never deletes member projects, never deletes runs, and never deletes audit history.

**Events and reporting (FR-79, FR-82, FR-83, FR-89).** Threshold crossings (health transition, gate backlog over limit, budget saturation) and lifecycle/membership changes are published to the portfolio event stream. Subscribers receive notifications or digests whose content is generated from the same aggregate computation as the dashboard, so numbers never disagree between channels. Exports are generated as of a stated timestamp and include the freshness watermark that applied to the data.

---

### Business Rules

- **BR-1:** A project belongs to at most one portfolio at any time. Unassigned is a valid, first-class state.
- **BR-2:** Portfolio names are unique among non-deleted portfolios within the same owning tenant scope, compared case-insensitively after trimming.
- **BR-3:** A portfolio has at most one parent, and the ancestor chain must be acyclic and no deeper than 5 levels.
- **BR-4:** Roll-ups include only non-deleted projects; archived portfolios' roll-ups remain readable but are frozen to read-only presentation, and their aggregates continue to reflect live member state.
- **BR-5:** Aggregates are always derived from authoritative project and run records. Manual counter overrides are not permitted.
- **BR-6:** Only the portfolio owner may archive, restore, delete, change roles, change defaults, change the concurrency budget, or change visibility.
- **BR-7:** Role inheritance applies: a user's role on a parent portfolio grants that role on parent-owned aggregates, but not mutation rights over a child portfolio's own configuration unless granted there.
- **BR-8:** Bulk commands are non-atomic by default. Atomic mode is permitted only for run initiation, only when every selected project passes readiness, and is rejected otherwise without side effects.
- **BR-9:** Every scoped command is recorded against each affected entity (run or project) as an auditable command, attributed to the portfolio it was issued from.
- **BR-10:** Changing portfolio defaults never retroactively mutates an existing project's pinned pipeline version, model tier, or gate policy (see FR-86).
- **BR-11:** Deleting a project (from F-1) automatically removes its membership; the removal is recorded as an audit entry attributed to the project deletion, not to a user portfolio action.
- **BR-12:** Metric buckets are computed in UTC and returned with the bucket boundary timestamps; retention is 90 days for fine-grained buckets and 400 days for daily buckets unless configured otherwise.
- **BR-13:** A portfolio identifier is immutable and is never reused after deletion.
- **BR-14:** Stale aggregates must be labelled as stale in both API responses and UI presentation; stale data must never be presented as current without the label (see FR-90).

---

### Validation

- **V-1:** `name` is required, trimmed, 1–120 characters, and unique per BR-2.
- **V-2:** `description` is optional, ≤ 2,000 characters after trimming.
- **V-3:** `tags` is optional, ≤ 20 entries, each 1–40 characters, each matching the allowed tag character set, case-insensitively deduplicated.
- **V-4:** `owner` is required at creation, must resolve to an existing principal, and may be transferred only by the current owner or an authorised administrator.
- **V-5:** `parentPortfolioId`, when supplied, must reference an existing non-deleted portfolio, must not equal the portfolio itself, and must not create a cycle or exceed depth 5 (BR-3).
- **V-6:** `visibility` must be one of the enumerated values; unrecognised values are rejected rather than defaulted.
- **V-7:** `concurrencyBudget`, when supplied, must be an integer ≥ 1 and ≤ the platform maximum; `0` is rejected and must be expressed as disabling the budget instead.
- **V-8:** Health thresholds supplied as configuration must be non-negative, ordered (attention threshold < degraded threshold), and complete; partial threshold sets are rejected.
- **V-9:** Membership assignment requires a valid, non-deleted project identifier; a deleted or unknown project is rejected (see EH-2).
- **V-10:** Bulk selector payloads must specify exactly one of: an explicit identifier list (≤ 500 entries) or a selector expression; supplying both or neither is rejected.
- **V-11:** Bulk identifier lists are deduplicated before processing; duplicates are reported as skipped rather than applied twice.
- **V-12:** Run-control bulk payloads must specify exactly one action from the permitted set and must include a reason note for `cancel` actions.
- **V-13:** `idempotencyKey`, when supplied, must be a bounded-length opaque string; the same key with a different payload is rejected as a conflict.
- **V-14:** Pagination cursors must be opaque and issued by the service; arbitrary offset values are rejected.
- **V-15:** Time ranges for metrics must be within retention (BR-12) and must specify `from` < `to`; bucket granularity must be one of the enumerated values and must not produce more than the maximum permitted bucket count for the range.
- **V-16:** Export format must be one of the enumerated formats; an unsupported format is rejected rather than silently defaulted.
- **V-17:** Role assignment payloads must reference existing principals and one of the enumerated roles; self-demotion of the last remaining owner is rejected.

---

### Edge Cases

- **EC-1:** **Empty portfolio.** A portfolio with zero members renders a first-run empty state that invites the operator to assign existing projects or create a new one, and roll-up counters read as zero rather than as blank or as an error. Health is `unknown`, not `healthy`.
- **EC-2:** **Project already in another portfolio.** Assignment returns a conflict naming the current portfolio; the caller must opt into reassignment explicitly. No state changes on the conflict path.
- **EC-3:** **Concurrent assignment of the same project.** Two simultaneous assigns to different portfolios resolve to exactly one winner; the loser receives a conflict. The project is never left in two portfolios or in none.
- **EC-4:** **Concurrent metadata edits.** Two editors submitting different descriptions against the same configuration revision: the first succeeds, the second receives a conflict carrying the current revision and value so the edit can be re-applied.
- **EC-5:** **Membership change while runs are in flight.** Detaching a project never cancels, pauses, or interrupts its runs. Aggregates immediately stop counting that project; historical audit entries retain the prior membership context.
- **EC-6:** **Project deleted while assigned.** The membership is removed automatically and an audit entry records the cause; the portfolio roll-up converges within the consistency window.
- **EC-7:** **Parent archived, child active.** The child remains fully operational and mutable; the parent is read-only but continues to present an aggregate of its active descendants.
- **EC-8:** **Reparenting creates a deep chain.** Attempting to set a parent that would exceed depth 5 or create a cycle is rejected with the offending ancestry path named in the error.
- **EC-9:** **Deleting a parent with children.** Rejected with the child identifiers enumerated; the caller may reparent or delete the children first.
- **EC-10:** **Very large portfolio.** A portfolio at or beyond the documented scale limit (NFR-39) still returns paged member lists within NFR-38 latency; the dashboard virtualizes the roster so first paint does not wait on the full set (NFR-50).
- **EC-11:** **Bulk selector matches nothing.** The operation succeeds with zero applied and a summary that says so, rather than erroring.
- **EC-12:** **Bulk operation partially fails.** The response lists each failed item with its reason; retrying with the same idempotency key does not reapply already-applied items.
- **EC-13:** **Bulk selector matches items the caller cannot see.** Out-of-scope items are excluded from the target set silently for count purposes but the response's applied count reflects only permitted items; no existence information about out-of-scope projects is disclosed (see FR-81).
- **EC-14:** **Run initiation across a mixed-readiness set.** Ready projects start; unready projects are reported with their itemized readiness failures. In atomic mode the whole request is rejected with the same itemized report and nothing starts.
- **EC-15:** **Concurrency budget exhausted.** New run requests are queued or rejected per the configured policy; the dashboard surfaces saturation and the event stream emits a saturation event on crossing.
- **EC-16:** **Gate backlog contains gates from a project later detached.** Pending gates remain actionable through the run-experience surface but drop out of the portfolio's aggregated queue on the next roll-up refresh.
- **EC-17:** **Stale cache after an outage.** If aggregate invalidation events were missed, the first read after recovery either recomputes or serves the value flagged `stale: true` with the old watermark — never a stale value presented as fresh.
- **EC-18:** **Clock skew across members.** Last-activity and gate-age computation uses server-recorded timestamps, not client-supplied ones, so skew on a member's machine cannot make a portfolio appear more or less recent than it is.
- **EC-19:** **Metrics range crossing a retention boundary.** A requested range that partially predates retention returns the available buckets with an explicit note that earlier data is unavailable, rather than extrapolating or silently truncating the range.
- **EC-20:** **Export of a portfolio mid-mutation.** The export is internally consistent as of its stated timestamp; concurrent mutations either appear fully or not at all within that snapshot.
- **EC-21:** **Last owner attempts to leave.** Rejected: a portfolio must always have at least one owner (V-17).
- **EC-22:** **Duplicate portfolio name differing only by case or surrounding whitespace.** Rejected by BR-2 after normalisation.
- **EC-23:** **Notification storm.** A cascade of failures across many members must be coalesced into a single digest-style notification per subscription per window rather than one notification per event.

---

### Error Handling

- **EH-1 — Validation failure (400-class).** Returns a machine-readable list of field-level violations, each naming the field, the violated rule, and the rejected value's shape. No partial writes occur.
- **EH-2 — Unknown or deleted entity (404-class).** Unknown portfolio, project, child portfolio, or membership returns not-found. Entities outside the caller's authorized scope also return not-found, never forbidden (existence non-disclosure, FR-81).
- **EH-3 — Authorization failure (403-class).** Returned only when the caller is known to be authorized to know the portfolio exists but lacks the required role. The response names the required role and the caller's current role.
- **EH-4 — Conflict (409-class).** Covers duplicate name (BR-2), project already assigned (EC-2), concurrent modification against a stale configuration revision (EC-4), and idempotency-key reuse with a differing payload (V-13). The body carries the current server state needed to resolve the conflict.
- **EH-5 — Unprocessable semantics (422-class).** Covers hierarchy cycle or depth violation (V-5), delete blocked by unresolved references (FR-88), atomic bulk rejected by readiness (BR-8), and metrics range outside retention (EC-19). The body enumerates the offending references or items.
- **EH-6 — Rate limit (429-class).** Returned for bulk operations exceeding NFR-48; includes a retry-after hint and the remaining budget.
- **EH-7 — Degraded aggregate (503-class or 200-with-flag).** If the aggregation backend is unavailable, read endpoints may serve a cached aggregate flagged `stale: true` with the watermark, or return a degraded-service error with a retry hint. Serving a stale aggregate *without* the flag is forbidden (BR-14).
- **EH-8 — Downstream bulk command failure.** When a scoped run command fails because the run-experience surface is unavailable, the operation reports per-item transport failures distinctly from per-item business failures, and the portfolio state is left unchanged for the failed items.
- **EH-9 — Unexpected server error (500-class).** Returns an opaque correlation identifier included in logs and traces (NFR-51); no internal detail or stack content is exposed to the caller.
- **EH-10 — Notification delivery failure.** A failed email or webhook delivery for a digest or event is retried with bounded backoff; persistent failure marks the subscription as degraded and surfaces that state to the subscriber without silently dropping events.

---

### Acceptance Criteria

- **AC-1:** Creating a portfolio with a valid name and owner returns a portfolio with an immutable identifier, lifecycle state `active`, and configuration revision `1`; the create appears in audit history with actor and timestamp.
- **AC-2:** Creating two portfolios with names differing only by case or surrounding whitespace in the same tenant fails the second with a conflict naming the existing portfolio.
- **AC-3:** Assigning an unassigned project to a portfolio succeeds; the project appears in the member list within the consistency window and the roll-up's project count increments by exactly one.
- **AC-4:** Assigning a project already held by another portfolio fails with a conflict naming the current portfolio, and the project's membership is unchanged.
- **AC-5:** Repeating an assignment for an already-member project (same portfolio) succeeds idempotently and does not create a duplicate membership row.
- **AC-6:** A bulk assign of 100 explicit project identifiers returns 100 per-item outcomes, with counts of applied, skipped, and failed that sum to 100.
- **AC-7:** Replaying a bulk operation with the same idempotency key and payload returns the original outcome and applies nothing twice.
- **AC-8:** Selecting a portfolio with three members whose states are known produces counters matching those states exactly for project count, run counts by status, gate backlog, and failure count in the window.
- **AC-9:** Every roll-up response includes a freshness watermark, and a response served from a cache older than the configured window carries `stale: true`.
- **AC-10:** After a member project's run changes status, the portfolio roll-up reflects the change within 5 s (NFR-41) in an automated convergence test.
- **AC-11:** A portfolio whose failure count crosses the degraded threshold reports health `degraded` and lists the contributing factors that produced the rating.
- **AC-12:** A portfolio with zero members reports health `unknown` and renders the first-run empty state rather than an error.
- **AC-13:** Setting a parent that would create a cycle or exceed depth 5 is rejected with the offending ancestry path in the error body, and no parent is written.
- **AC-14:** Archiving a portfolio makes membership and configuration mutations fail while leaving member projects and their in-flight runs unaffected and fully operable.
- **AC-15:** Deleting a portfolio with members or children is rejected and the error enumerates the blocking references; after detaching all members and children, the delete succeeds.
- **AC-16:** A viewer on a portfolio can read the dashboard, roll-up, metrics, and audit history, and every mutating portfolio endpoint returns an authorization failure for that caller.
- **AC-17:** A maintainer can assign and remove members and issue scoped run control, but a metadata edit or role change returns an authorization failure.
- **AC-18:** A portfolio-scoped run initiation over five projects where two fail readiness starts exactly three runs and returns an itemized report naming the two failures; in atomic mode all five are rejected and none start.
- **AC-19:** A portfolio-scoped pause applies to every running member-project run the caller is permitted to control and yields a per-run outcome; runs outside the portfolio are untouched.
- **AC-20:** The aggregated gate queue lists pending gates from all member projects ordered oldest-first, each row showing gate type, stage, project, and waiting duration, and each linking to the corresponding gate decision surface.
- **AC-21:** Filtering the member list by `health = degraded` returns only matching projects, while the portfolio-level counters continue to reflect the whole portfolio and are labelled as such.
- **AC-22:** Saving a named view and reopening it after membership changes re-evaluates against current data and never returns a frozen result set.
- **AC-23:** Exporting a portfolio produces a document containing metadata, member rows, counters, attention items, a generation timestamp, and the freshness watermark.
- **AC-24:** Changing a portfolio's default model tier does not alter the model tier of any existing member project; a project created afterwards into that portfolio inherits the new default and records it at creation.
- **AC-25:** Audit history for a portfolio returns every mutation with actor, timestamp, prior and new value, and for bulk operations the per-item outcome, and contains no entries that can be edited or deleted through any API.
- **AC-26:** Two parallel edits to the same portfolio metadata against the same configuration revision produce exactly one success and one conflict carrying the current revision.
- **AC-27:** All list endpoints honour cursor pagination with a 200-item hard maximum, returning a continuation cursor when more results exist.
- **AC-28:** The portfolio dashboard meets LCP < 2.5 s and INP < 200 ms under the lab performance profile (NFR-50).
- **AC-29:** All portfolio views pass an automated WCAG 2.1 AA audit (contrast, keyboard reachability, focus visibility, semantic table headers) and a manual keyboard-only triage of the member list and gate queue succeeds end to end (NFR-49).
- **AC-30:** Configuring a concurrency budget of N and requesting N+2 simultaneous run starts results in exactly N starts and a per-item queued-or-rejected outcome for the remaining two, plus a budget-saturation indication on the dashboard.

---

### API Behaviour

Conventions below are illustrative of resource semantics; the Architect agent finalises protocol, transport, and naming. All endpoints require authentication and are enforced by the portfolio-scoped authorization of FR-81. All list endpoints are cursor-paginated (NFR-46). All mutating endpoints accept an optional idempotency key (NFR-47) and emit audit records (FR-84). All reads are scoped to the caller's authorized portfolios.

| ID | Operation | Method / Resource | Request essentials | Response essentials | Notes |
|---|---|---|---|---|---|
| API-1 | Create portfolio | `POST /portfolios` | name, description?, owner, tags?, visibility?, parentPortfolioId?, defaults?, concurrencyBudget? | 201 with portfolio object incl. id, lifecycle state, configuration revision | Validates V-1…V-7; 409 on duplicate name |
| API-2 | List portfolios | `GET /portfolios` | filters: lifecycle state, owner, tag, parent, search; cursor; limit | Page of portfolio summaries + continuation cursor | Excludes archived by default; `includeArchived` opt-in |
| API-3 | Read portfolio | `GET /portfolios/{portfolioId}` | — | Portfolio object + configuration revision | 404 for unknown or out-of-scope |
| API-4 | Update portfolio metadata | `PATCH /portfolios/{portfolioId}` | partial metadata + expected configuration revision | Updated portfolio object, incremented revision | 409 on stale revision (EC-4) |
| API-5 | Archive portfolio | `POST /portfolios/{portfolioId}/archive` | optional reason note | Portfolio with lifecycle state `archived` | Read-only afterwards; members unaffected |
| API-6 | Restore portfolio | `POST /portfolios/{portfolioId}/restore` | optional reason note | Portfolio with lifecycle state `active` | Preserves prior configuration revision and records the restore |
| API-7 | Delete portfolio | `DELETE /portfolios/{portfolioId}` | optional resolution: reassignTo or detachMembers | 204 on success | 422 with enumerated blocking references while members/children remain (FR-88) |
| API-8 | Assign project | `PUT /portfolios/{portfolioId}/projects/{projectId}` | optional reason, optional `reassign: true` | Membership record + resulting roll-up delta | 409 when held by another portfolio and reassignment not requested (EC-2) |
| API-9 | Remove project | `DELETE /portfolios/{portfolioId}/projects/{projectId}` | optional reason | 204 | Project and its runs untouched |
| API-10 | Bulk assign members | `POST /portfolios/{portfolioId}/projects/bulk` | one of: identifiers[] (≤500) or selector; action: assign/remove/reassign; idempotency key | Summary counts + per-item outcome list | Non-atomic; partial success reported (FR-69) |
| API-11 | List members | `GET /portfolios/{portfolioId}/projects` | filters (state, run status, health, tag, owner, model tier, last-activity window), sort, search, cursor, limit | Page of member rows + continuation cursor | Filtered list never changes portfolio-level counters (AC-21) |
| API-12 | Portfolio roll-up | `GET /portfolios/{portfolioId}/rollup` | optional `includeDescendants` | Counters (projects by state, runs by status, gate backlog, failures in window, capacity utilisation), last activity, health + contributing factors, freshness watermark, stale flag | Derived only (BR-5); carries watermark (FR-90) |
| API-13 | Portfolio metrics | `GET /portfolios/{portfolioId}/metrics` | from, to, bucket, metrics[] | Bucketed series with bucket boundaries + availability note | Validates V-15; retention per BR-12 |
| API-14 | Aggregated gate backlog | `GET /portfolios/{portfolioId}/gates` | sort (default age), filters, cursor, limit | Page of gate rows: type, stage, project, waiting duration, assignee, deep link | Read-only aggregation; decisions live on the run surface (FR-76) |
| API-15 | Scoped run control | `POST /portfolios/{portfolioId}/runs/bulk` | action (pause/resume/cancel/retry), target identifiers or selector, reason (required for cancel), idempotency key | Summary counts + per-run/per-project outcome list | Delegates to run control of F-3; records auditable commands (BR-9) |
| API-16 | Scoped run initiation | `POST /portfolios/{portfolioId}/runs` | project identifiers or selector, run label?, starting stage override?, atomic? | Started run identifiers + itemized readiness failures | Delegates to run initiation and pre-flight of F-3; atomic mode is all-or-nothing (BR-8) |
| API-17 | Saved views | `GET|POST /portfolios/{portfolioId}/views`, `PATCH|DELETE /portfolios/{portfolioId}/views/{viewId}` | name, query state, sharing scope | Saved view objects | Stores query state only, never results (FR-78) |
| API-18 | Export snapshot | `POST /portfolios/{portfolioId}/exports` | format, include[] sections | Export document with generation timestamp + freshness watermark | Validates V-16; internally consistent snapshot (EC-20) |
| API-19 | Audit history | `GET /portfolios/{portfolioId}/audit` | time range, actor, action type, cursor | Append-only audit entries (actor, timestamp, prior/new value, per-item outcomes) | Never mutable or deletable via API (NFR-43) |
| API-20 | Members and roles | `GET /portfolios/{portfolioId}/members`, `PUT|DELETE /portfolios/{portfolioId}/members/{principalId}` | role from enumerated set | Member-role list / updated membership | Owner-only; rejects removing the last owner (V-17, EC-21) |
| API-21 | Subscription | `GET|PUT /portfolios/{portfolioId}/subscription` | channels[], cadence, thresholds | Subscription configuration | Digest content derives from the same aggregate as the dashboard (FR-82) |
| API-22 | Event stream | `GET /portfolios/{portfolioId}/events` | cursor, event types, since | Ordered event envelope batch + next cursor | At-least-once delivery (FR-89) |
| API-23 | Hierarchy | `GET /portfolios/{portfolioId}/children`, `PUT /portfolios/{portfolioId}/parent` | parentPortfolioId or null | Updated hierarchy relationships | Validates V-5; 422 on cycle or depth violation (EC-8) |

**Cross-cutting API behaviour.** Mutating endpoints return the resulting resource representation so clients can reconcile without a follow-up read. Bulk endpoints return HTTP 200 with per-item outcomes even when some items failed, reserving 4xx/5xx for request-level failures (malformed payload, unauthorized, rate-limited, backend unavailable). Reads that can be served stale return 200 with `stale: true` and a watermark rather than failing; reads that cannot be served at all return a degraded-service error with a retry hint (EH-7). Every response that includes an aggregate carries the watermark so downstream consumers can reason about freshness without guessing.

---

### Priority Summary

**Must-have (blocking for release):** FR-66, FR-67, FR-68, FR-71, FR-72, FR-73, FR-75, FR-76, FR-77, FR-81, FR-84, FR-86, FR-87, FR-88, FR-90.

**Should-have (high value, planned in the first portfolio release):** FR-69, FR-70, FR-74, FR-78, FR-79, FR-82, FR-83.

**Nice-to-have (valuable, schedulable after the core portfolio surface is solid):** FR-80, FR-85, FR-89.

---

### Open Questions (for the USER — not resolved by this spec)

- **OQ-1:** Should a project be allowed to belong to more than one portfolio? This spec implements the conservative rule implied by F-2 (project assigned to zero or one portfolio) as BR-1. If multi-membership is intended, BR-1, FR-68, API-8, and AC-3/AC-4 must be revised before implementation.
- **OQ-2:** Should archiving a portfolio optionally cascade to its child portfolios? FR-87 currently makes each portfolio's lifecycle state independent. A cascade option would need its own confirmation semantics and audit entries.
- **OQ-3:** Are portfolio-level concurrency budgets (FR-80) a hard governance limit that must block run initiation, or an advisory signal shown on the dashboard only? The current spec supports both via configuration; the default policy must be chosen before release.
