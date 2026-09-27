## F-4: Progress Analytics

> **Feature id:** F-4 · **Owned global id ranges:** FR-76..FR-100, NFR-46..NFR-60, US-46..US-60 · **Local ids** (BR-, V-, EC-, EH-, AC-, API-, DM-, T-, OQ-) are scoped to this feature and numbered sequentially from 1. References to F-1 / F-2 / F-3 ids are plain text only; this section never re-defines them.

### Requirements

**Functional Requirements (global ids — owned range FR-76..FR-100)**

| ID | Name | Description |
|----|------|-------------|
| FR-76 | Analytics dashboard access | A dedicated "Progress" view is reachable from primary navigation and presents the user's personal productivity metrics on one scrollable surface. |
| FR-77 | Completion metrics | The dashboard shows total tasks completed, total tasks created, and net change (created − completed) for the selected period. |
| FR-78 | Completion rate over time | Completion rate (completed ÷ created, expressed as a percentage) is shown for the selected period and plotted as a time series at a granularity implied by the period length. |
| FR-79 | Task throughput | Tasks completed per day / week / month are computed and displayed as bar or line series for the selected period. |
| FR-80 | Completion streak | A current streak and a longest streak of consecutive active days (days with ≥1 completed task) are tracked and displayed, with the streak definition visible to the user. |
| FR-81 | Focus-time analytics | Total focused minutes, session count, and completed-vs-interrupted session ratio are derived from focus sessions (F-3) and displayed for the selected period. |
| FR-82 | Focus distribution | Focused minutes are broken down by associated task, tag/project, and time of day, so the user can see where their focus time went. |
| FR-83 | Prioritization effectiveness | The dashboard reports whether tasks that F-1 ranked high were completed sooner than tasks it ranked low (e.g. average rank-to-completion lag, top-of-queue completion share). |
| FR-84 | Deferral & reschedule analysis | Count and proportion of tasks whose due date was postponed (rescheduled), and average postponement count per task, are reported for the period. |
| FR-85 | Overdue analysis | Overdue tasks (past due, not completed) are counted and shown as a trend and as a current snapshot, grouped by age bucket. |
| FR-86 | Productivity heatmap | A day-of-week × hour-of-day heatmap shows completion density, derived from completion timestamps, so the user can identify their most productive windows. |
| FR-87 | Weekly review summary | A one-screen weekly digest summarizes the week's completions, focus time, streak status, top completed tag/project, and outstanding overdue count. |
| FR-88 | Date-range selection | The user can select the analytics time window via presets (today, this week, this month, last 7/30/90 days, this year) and a custom start/end date range. |
| FR-89 | Analytics filtering | Analytics can be scoped by tag, project/context, priority band (F-1 importance), completion status, and task origin (manual vs. quick-add per F-2). |
| FR-90 | Grouping / segmentation | The user can group analytics by tag, project/context, priority band, or origin, and see per-group breakdowns of the core metrics. |
| FR-91 | Goal definition | The user can define personal goals such as "complete N tasks per day/week" or "focus M minutes per day/week". |
| FR-92 | Goal progress tracking | Each defined goal shows current progress toward its target for the current interval, with an on-track / at-risk / achieved state. |
| FR-93 | Period-over-period comparison | The user can compare the selected period against the immediately preceding equal-length period, with deltas shown per metric (absolute and %). |
| FR-94 | Chart visualization | Each metric is rendered as a chart appropriate to its type (time series for trends, bar for throughput, heatmap for the productivity grid); charts show axis labels, units, and hover/tap values. |
| FR-95 | Data export | The user can export the currently selected metrics and period to a machine-readable file (CSV) and a printable view, respecting the active filters. |
| FR-96 | Data freshness indicator | The dashboard displays the timestamp of the last successful data refresh and auto-refreshes on view load, or offers a manual refresh action. |
| FR-97 | No-data / first-run guidance | When there is insufficient data for a metric, the surface shows an explanatory empty state and the minimum input needed to populate it, rather than a misleading zero. |
| FR-98 | Insight callouts | The dashboard surfaces plain-language, deterministic callouts derived from the data (e.g. "You completed 30% more tasks than last week") with the underlying numbers shown. |
| FR-99 | Customizable dashboard | The user can choose which metric widgets appear and in what order, and the layout persists per user across sessions and devices. |
| FR-100 | Historical window & retention | Analytics are computed over a bounded historical window; the dashboard states the window covered and does not present metrics as if complete when data is partial or truncated. |

**Non-Functional Requirements (global ids — owned range NFR-46..NFR-60)**

| ID | Area | Target / description |
|----|------|----------------------|
| NFR-46 | Performance (page) | The Progress dashboard reaches first meaningful render in <2.5s on a mid-range mobile device over 3G with a 12-month dataset. |
| NFR-47 | Performance (aggregation) | Any single metric aggregation responds in <800ms p95 and <1.5s p99 for the maximum supported window; the UI shows a loading state beyond 300ms. |
| NFR-48 | Scalability (data volume) | Analytics remain responsive for accounts with up to 50,000 tasks and 20,000 focus sessions; longer histories are aggregated server-side rather than shipped raw to the client. |
| NFR-49 | Availability | The Progress view degrades gracefully and returns a usable shell when the aggregation backend is unavailable; the rest of the app remains fully functional. |
| NFR-50 | Security / access control | Analytics data is private to the authenticated owner; every request is authorized against the requesting user and never returns another user's data. |
| NFR-51 | Privacy | Analytics are computed from the user's own data only; no cross-user or third-party profiling is performed and no task content is sent to external analytics providers. |
| NFR-52 | Data residency | Analytics storage and computation respect the project's configured data-residency region; derived aggregates inherit the residency of their source data. |
| NFR-53 | Data accuracy / freshness | Derived metrics reconcile with source records within the documented freshness window (default ≤5 minutes after a mutation), and the freshness timestamp is user-visible. |
| NFR-54 | Degraded / offline | When the network is unavailable the last cached dashboard remains viewable with a stale-data indicator and export is disabled until connectivity returns. |
| NFR-55 | Internationalization | Dates, week start day, numbers, and percentages are formatted in the user's locale; durations use the user's 12/24-hour preference; RTL layout is supported. |
| NFR-56 | Accessibility | Charts provide an accessible text/table alternative; metrics are conveyed without relying on color alone; the view is fully keyboard navigable and satisfies WCAG 2.1 AA contrast. |
| NFR-57 | Cross-device consistency | The same metric definitions and dashboard layout yield consistent values across devices; layout customization (FR-99) syncs per user. |
| NFR-58 | Export integrity | Exported files match the on-screen values for the same filters/period within rounding tolerances, use a documented schema, and are valid/unopenable-free. |
| NFR-59 | Deployment / environment | Metric definitions, default history window, and aggregation cadence are environment-configurable and consistent across dev/staging/prod. |
| NFR-60 | Observability | Aggregation failures, latency, and cache hit rates are logged/metriced; anomalies (e.g. sudden zero-metric regressions) are alertable. |

**User Stories (global ids — owned range US-46..US-60)**

| ID | Story |
|----|-------|
| US-46 | As a busy professional, I want to see how many tasks I completed this week, so that I know whether I am keeping up with my workload. |
| US-47 | As a user, I want to see my completion rate over time, so that I can tell whether I am becoming more or less consistent. |
| US-48 | As a user, I want to see my current and longest streak, so that I stay motivated to keep a daily habit. |
| US-49 | As a user, I want to see how much focused time I accumulated, so that I understand the quality of my work, not just the quantity. |
| US-50 | As a user, I want to see where my focus time went, so that I can rebalance my effort between projects. |
| US-51 | As a user, I want to know whether prioritizing my tasks actually helped me finish the important ones first, so that I can trust or adjust my prioritization. |
| US-52 | As a user, I want to see how often I postpone tasks, so that I can spot chronic procrastination patterns. |
| US-53 | As a user, I want to see my overdue tasks trend, so that I can intervene before a backlog builds up. |
| US-54 | As a user, I want a heatmap of when I complete the most work, so that I can schedule demanding tasks at my peak hours. |
| US-55 | As a user, I want a concise weekly review, so that I can reflect in under a minute. |
| US-56 | As a user, I want to filter analytics by tag or project, so that I can evaluate one area of my life at a time. |
| US-57 | As a user, I want to set and track goals, so that I have a concrete target to aim for. |
| US-58 | As a user, I want to compare this period to the last, so that I can see whether things are improving. |
| US-59 | As a user, I want to export my metrics, so that I can keep a personal record or share it. |
| US-60 | As a user, I want to choose which metrics I see, so that my dashboard reflects what matters to me. |

### Behaviour

- On open, the Progress view loads the metric set for the default period (configurable; default "this week"), honoring persisted filters and layout from FR-99.
- Every metric is computed from the same underlying event records: task creation, completion, due-date mutation (reschedule), and focus-session start/end (F-3). Metrics are read-only views; this feature never mutates task or session data.
- Changing the date range (FR-88) or filters (FR-89) recomputes all visible metrics atomically against the new scope; widgets enter a loading state and do not display mixed-scope values.
- Period comparison (FR-93) requires an equal-length preceding window; when the preceding window predates the retention window, the delta is shown as "insufficient history" rather than a fabricated value.
- Goal progress (FR-92) is evaluated against the current interval boundary (day/week) using the same completion/focus events as the base metrics; state derives from projected pace vs. elapsed fraction of the interval.
- Insight callouts (FR-98) are deterministic functions of displayed metrics — no generative or speculative content — and always cite the numbers they are based on.

### Business rules

- **BR-1** — A task counts as "completed in period P" if and only if its completion timestamp falls within P, regardless of its creation date.
- **BR-2** — A task counts as "created in period P" if and only if its creation timestamp falls within P. Completion rate (FR-78) = completed-in-P ÷ created-in-P; when created-in-P is 0 the rate is undefined and shown as "—", never as 0% or 100%.
- **BR-3** — Streak (FR-80): consecutive calendar days (in the user's locale and week-start convention) with ≥1 completed task. A gap of one or more zero-completion days resets the current streak; the longest streak is the maximum run ever recorded within the retention window.
- **BR-4** — Overdue (FR-85): a task is overdue when its due timestamp is in the past, it has no completion timestamp, and it is not explicitly marked cancelled. Overdue age buckets are defined by whole days past due.
- **BR-5** — Focus time (FR-81) counts only completed or interrupted session time actually elapsed, not the planned duration; a session paused and resumed is counted once with net elapsed time. Cancelled sessions with zero elapsed time are excluded.
- **BR-6** — Prioritization effectiveness (FR-83) compares the F-1 rank a task held at the start of the selected period against its completion lag; tasks with no F-1 rank (unscored/inactive) are excluded from this metric and the excluded count is disclosed.
- **BR-7** — Deferral (FR-84) counts each change to a task's due date that moves it later as one postponement; moving a due date earlier is not counted. Multiple postponements of the same task count separately.
- **BR-8** — Deleted tasks are excluded from all current-period totals going forward but are retained in already-materialized historical aggregates per the retention policy (FR-100) so past reports do not silently change.
- **BR-9** — All percentages are rounded for display (one decimal) but computed from unrounded counts; totals in a grouped breakdown (FR-90) must sum to the ungrouped total within rounding tolerance.
- **BR-10** — The "top completed tag/project" in the weekly review (FR-87) is chosen by completed-task count; ties are broken alphabetically for determinism.

### Validation

- **V-1** — Custom date range: both start and end are required, start ≤ end, and neither may be later than "now"; the maximum span is the configured retention window (default 365 days).
- **V-2** — Goal definition (FR-91): target value is a positive integer; focus-minute goals must be a multiple of 1 minute and within the retention-bounded weekly maximum; a task-count goal of 0 is rejected.
- **V-3** — Filters: an empty filter selection is treated as "all"; an explicitly selected tutorial that yields no matching tasks produces the no-data state (FR-97), not an error.
- **V-4** — Export (FR-95) requires a non-empty result set for the current scope; exporting an empty scope is disabled with an explanatory message.
- **V-5** — Date inputs are validated in the user's locale format and normalized to UTC internally; invalid or unparseable dates are rejected inline.
- **V-6** — Dashboard layout (FR-99) must contain at least one widget; a layout with all widgets removed is rejected with guidance to add at least one.

### Edge cases

- **EC-1** — Zero tasks created in the period but tasks completed (backlog burn-down): completion rate is undefined (BR-2) and shown as "—" with an explanation, while throughput (FR-79) still displays.
- **EC-2** — Time-zone boundary: a task completed at 23:30 local that falls on the next UTC day is attributed to the user's local day for streak and heatmap purposes (FR-80, FR-86).
- **EC-3** — First-ever use / brand-new account: all widgets render FR-97 empty states with the minimum number of completed tasks needed to populate each metric.
- **EC-4** — A focus session spanning midnight splits elapsed time across the two local days proportionally for the heatmap and daily focus metrics.
- **EC-5** — Tasks with no due date are included in completion/throughput/streak metrics but excluded from overdue (FR-85) and never counted as deferrals (FR-84).
- **EC-6** — User changes locale or week-start convention mid-window: the view recomputes with the new convention and the change is reflected in the streak definition display (BR-3).
- **EC-7** — Very long history: when the requested window exceeds the retention boundary, the dashboard clamps to the boundary and clearly labels the truncated coverage (FR-100).
- **EC-8** — A goal target exceeds any achievable value within the interval (e.g. 100 completions/day): the goal is stored but permanently shown "at-risk"; no error.
- **EC-9** — Comparison window partially outside retention: deltas are suppressed and labeled "insufficient history" rather than computed from partial data (FR-93).
- **EC-10** — Concurrent edit during load: if a task is completed while the dashboard is open, the freshness indicator updates and the user is offered a refresh (FR-96) rather than the view silently mutating mid-read.

### Error handling

- **EH-1** — Aggregation backend unavailable: the view renders the last successfully cached dashboard with a persistent stale-data banner; a retry action is offered; export is disabled (NFR-54).
- **EH-2** — Partial aggregation failure (one widget's data fails while others succeed): the failing widget shows an inline error with retry, and the rest of the dashboard remains usable.
- **EH-3** — Request timeout: the widget shows a timeout state with retry; no partial/inconsistent numbers are displayed for that widget.
- **EH-4** — Unauthorized request: the user is returned to authentication; no analytics data is rendered or cached for an unauthenticated session.
- **EH-5** — Export generation failure: an error toast is shown, the on-screen view is unaffected, and the user can retry; partial files are never offered for download.
- **EH-6** — Invalid persisted layout (e.g. from an older version): the layout is validated, invalid widgets are dropped with a non-blocking notice, and the user is returned to a valid dashboard rather than an error page.

### Acceptance criteria

- **AC-1** — Given a period with 10 tasks created and 7 completed locally, when the user opens the Progress view for that period, then completed shows 7, created shows 10, and completion rate shows 70.0%.
- **AC-2** — Given a period in which zero tasks were created, when the dashboard renders, then completion rate displays "—" with an explanation and never shows 0% or 100%.
- **AC-3** — Given completions on 5 consecutive days followed by a zero-completion day, when streaks render, then the current streak shows 0 and the longest streak shows 5.
- **AC-4** — Given focus sessions totaling 130 elapsed minutes in the period, when the focus metrics render, then total focused minutes shows 130 and the session count matches the number of counted sessions per BR-5.
- **AC-5** — Given a custom range of 30 days, when the user changes a filter to a single tag, then all widgets recompute to that tag's scope and every widget reflects the same scope (no mixed values).
- **AC-6** — Given the user compares this week to last week, when both windows have data, then each metric shows an absolute and percentage delta consistent with the underlying values.
- **AC-7** — Given a goal of 5 completions/day and 3 completed at midday, when the goal widget renders, then it shows progress 3/5 and an "at-risk" or "on-track" state derived from elapsed interval fraction.
- **AC-8** — Given the currently selected metrics and filters, when the user exports, then the CSV contains exactly those metrics/rows and its values match the screen within rounding tolerance (BR-9).
- **AC-9** — Given insufficient data for a metric, when the widget renders, then it shows an FR-97 empty state naming the inputs needed, not a zero value.
- **AC-10** — Given a screen-reader user, when the dashboard renders, then every chart exposes an accessible text/table alternative and all controls are keyboard operable (NFR-56).
- **AC-11** — Given the aggregation backend is unreachable, when the user opens the view, then the last cached dashboard renders with a stale indicator and export is disabled (NFR-54, EH-1).
- **AC-12** — Given the user removes all widgets, when the layout is saved, then the change is rejected with guidance to keep at least one widget (V-6).

### API behaviour

> Endpoints describe observable behaviour only; transport, storage, and framework choice belong to the Architect agent. All endpoints are owner-scoped and reject requests for other users' data.

- **API-1** — `GET /analytics/summary` — params: `from`, `to`, `filters`, `groupBy`. Returns the scalar metrics (completed, created, net, completionRate, streaks, focus totals, overdue count, deferral count) for the scope. `completionRate` is `null` when undefined (BR-2).
- **API-2** — `GET /analytics/timeseries` — params: `metric`, `from`, `to`, `granularity` (day/week/month), `filters`. Returns an ordered series of `{bucket, value}`; buckets align to the user's week-start convention and local day boundaries (EC-2).
- **API-3** — `GET /analytics/heatmap` — params: `from`, `to`, `filters`. Returns a 7×24 matrix of completion density with local-day/hour attribution (FR-86, EC-2, EC-4).
- **API-4** — `GET /analytics/breakdown` — params: `groupBy` (tag|project|priorityBand|origin), `from`, `to`, `filters`. Returns per-group values plus an `excluded` count for records lacking the grouping attribute; group values reconcile to the ungrouped total (BR-9).
- **API-5** — `GET /analytics/insights` — params: `from`, `to`, `filters`. Returns deterministic callouts (FR-98), each with `text` and the `metricValues` it cites; never returns generative content.
- **API-6** — `GET /analytics/goals` / `PUT /analytics/goals/{id}` — read and define personal goals; write validates per V-2 and returns the persisted goal.
- **API-7** — `GET /analytics/export` — params: `from`, `to`, `filters`, `metrics`. Returns a CSV with a documented schema (FR-95); responds `409`/disabled state when the scope is empty (V-4) or the view is in degraded mode (EH-1).
- **API-8** — `GET /analytics/preferences` / `PUT /analytics/preferences` — read/write the persisted dashboard layout and default period (FR-99); payload validated against V-6 and the supported widget set.

**Response conventions:** successful responses include `asOf` (freshness timestamp, FR-96) and `coverage` (`{from, to, truncated}` per FR-100). Scope-invalid requests (V-1, V-3) return a validation error identifying the offending parameter; authorization failures return a non-disclosing error and never leak metric values (NFR-50).

### Priority

**Must-have:** FR-76, FR-77, FR-78, FR-79, FR-80, FR-81, FR-88, FR-94, FR-96, FR-97, FR-100 — the core dashboard, completion/streak/focus metrics, range selection, charting, freshness, and honest no-data/coverage handling.

**Should-have:** FR-82, FR-83, FR-84, FR-85, FR-87, FR-89, FR-90, FR-92, FR-93, FR-98 — segmentation, prioritization/deferral/overdue insight, weekly review, filtering, goal tracking, comparison, and callouts.

**Nice-to-have:** FR-86, FR-91 (goal definition UI beyond defaults), FR-95, FR-99 — heatmap, custom goal authoring, export, and dashboard customization.

### Open questions

- **OQ-1** — Default analytics history window and retention boundary are unspecified in the product plan; a default of 365 days is assumed (FR-100, NFR-59). Confirm the intended retention window.
- **OQ-2** — Whether the streak should follow calendar days or "active days with logged activity" is ambiguous; BR-3 assumes calendar days. Confirm.
- **OQ-3** — Should analytics include tasks completed via any route only, or also count quick-add-created tasks separately (F-2 origin grouping, FR-90)? Confirm whether origin segmentation is required at launch.
- **OQ-4** — Export format scope: is CSV + printable view sufficient, or is a second machine-readable format expected? Assumption recorded in FR-95.
