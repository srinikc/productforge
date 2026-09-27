# 1 design — brief summary

> status: completed · generated 2026-09-26T22:30:28

# DESIGN Output - Stage 1
## Token Usage
  - **Input Tokens:** 114440
## Output
## F-1: Intelligent Task Prioritization
### Requirements
### Behaviour
  - Event-driven: task create/update/complete/delete, due-date change, dependency link change, override change, profile change, feedback signal.
### Business rules
### Validation
  - Weights: each factor weight must be a finite number in the inclusive range 0–100; at least one weight must be greater than 0. Non-numeric, negative, or out-of-range values are rejected.
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
  - Read endpoints never fail solely because scoring is unavailable; they degrade per EH-5 and set `meta.stale = true`.
### Tests
### Open questions
### Priority
## F-2: Quick Add
### Requirements
### Behaviour
### Business rules
### Validation
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
### Priority
## F-3: Focus Mode
### Requirements
  - **US-31:** As a busy professional, I want to start a focus session on a task so that I work on it without distraction.
### Behaviour
### Business rules
  - **BR-1:** A focus session must always reference exactly one linked task at any instant; task reassignment is recorded as a segment boundary.
### Validation
  - **V-1:** Session duration must be a whole number of minutes within the inclusive range 1–180. Values outside the range are rejected inline with the allowed range shown.
### Edge cases
  - **EC-1:** Timer reaches zero while the app is backgrounded or closed → on resume, the completion prompt is shown and the session is finalized (see Behaviour 8).
### Error handling
  - **EH-1:** Timer state fails to persist locally → the session continues in memory, a non-blocking warning is shown, and a retry is scheduled; if persistence still fails at session end, the record is held in memory for the remainder of the app run and the user is warned that it may be lost.
### Acceptance criteria
  - **AC-1:** Given a task, when the user starts focus mode, then a session begins with the configured default duration and the task title is visible in the reduced layout. (FR-51, FR-52, FR-71)
### API behaviour
  - **API-1 — Start session.** `POST /focus-sessions` with `{ taskId, plannedDurationMinutes, cycleConfig? }` → `201` returning `{ id, taskId, state: "running", startedAt, endsAt, plannedDurationMinutes }`. `409` if an active session already exists (BR-3); `422` if `taskId` is missing/unknown or duration violates V-1.
### Priority
  - **Must-have:** FR-51, FR-52, FR-54, FR-55, FR-58, FR-59, FR-62, FR-67, FR-71, FR-72, NFR-31, NFR-32, NFR-33, NFR-34, NFR-40, NFR-42.
## F-4: Progress Analytics
### Requirements
### Behaviour
  - On open, the Progress view loads the metric set for the default period (configurable; default "this week"), honoring persisted filters and layout from FR-99.
### Business rules
  - **BR-1** — A task counts as "completed in period P" if and only if its completion timestamp falls within P, regardless of its creation date.
### Validation
  - **V-1** — Custom date range: both start and end are required, start ≤ end, and neither may be later than "now"; the maximum span is the configured retention window (default 365 days).
### Edge cases
  - **EC-1** — Zero tasks created in the period but tasks completed (backlog burn-down): completion rate is undefined (BR-2) and shown as "—" with an explanation, while throughput (FR-79) still displays.
### Error handling
  - **EH-1** — Aggregation backend unavailable: the view renders the last successfully cached dashboard with a persistent stale-data banner; a retry action is offered; export is disabled (NFR-54).
### Acceptance criteria
  - **AC-1** — Given a period with 10 tasks created and 7 completed locally, when the user opens the Progress view for that period, then completed shows 7, created shows 10, and completion rate shows 70.0%.
### API behaviour
  - **API-1** — `GET /analytics/summary` — params: `from`, `to`, `filters`, `groupBy`. Returns the scalar metrics (completed, created, net, completionRate, streaks, focus totals, overdue count, deferral count) for the scope. `completionRate` is `null` when undefined (BR-2).
### Priority
### Open questions
  - **OQ-1** — Default analytics history window and retention boundary are unspecified in the product plan; a default of 365 days is assumed (FR-100, NFR-59). Confirm the intended retention window.
## F-5: Integration Hub
### Requirements
  - **US-61** — As a busy professional, I want to connect my calendar so that deadline-bearing events appear as tasks automatically.
### Behaviour
### Business Rules
  - **BR-1** — A connection becomes active only after authorization succeeds, at least one scope is selected, and a field mapping is valid; partial configurations persist as drafts and never sync.
### Edge Cases
  - **EC-1** — The external item's title is empty or whitespace only; the task title falls back to the declared title-default rule rather than creating an untitled task.
### Error Handling
  - **User-visible errors** name the connection, the affected item count, the reason in plain language, and a single primary recovery action (Reconnect, Adjust scope, Fix mapping, Retry, Open conflict).
### Acceptance Criteria
  - **AC-1** — Given a valid provider account, when the user completes authorization and sets scope, direction, mapping, and conflict policy, then the connection appears as `connected` and the first sync starts within 60 s. (FR-101, FR-102, FR-103)
### API Behaviour
### Data Model (concepts; storage is the Architect's decision)
  - **DM-1 Connection** — owner, source type, label, account identity, state, direction, cadence, deletion rule, timestamps.
### Priority
### Traceability
### Open Questions (for the USER — not decided by this agent)
  - **OQ-1** — Which source types must be in the launch catalogue (FR-101), and in what order? The catalogue content is a scope decision for the user; this section assumes calendar, email/issue tracker, messaging, and generic webhook bridge are all in scope.
## F-6: Dark Mode
### Requirements
### Behaviour
### Business rules
  - **BR-1 — One preference.** Exactly one preference value is active per device: `light`, `dark`, or `system`. Custom colour pickers, per-screen themes, and per-project themes are out of scope for this feature.
### Validation
  - **Preference value.** Must be one of the allow-listed enums (`light`, `dark`, `system`). Any other value is rejected in whole, logged, and the effective theme falls back to the last known-good value, then to `system`.
### Edge cases
  - **EC-1 — OS theme changes while backgrounded.** On resume, the effective theme matches the OS with no visible flash or intermediate light frame.
### Error handling
  - **Token set failure.** Fall back to the last known-good set, record the failure in diagnostics, and show a passive notice. Never render unstyled content and never block the app.
### Acceptance criteria
  - **AC-1.** Given any screen or state within F-1..F-5, when the preference is set to dark, then every visible element including empty, loading, error, and modal states renders from the dark token set, with no light-coloured surface or unstyled region remaining.
### API behaviour
  - **API-1 — Read theme state.** Returns the effective theme, the stored preference, the resolution source (`user`, `system`, `schedule`, `override`, `default`), the active token-set version, and the schedule definition. Readable entirely from local state with no network dependency.
### Priority
### Open Questions
  - **OQ-1.** Is the theme preference intended to sync across a user's devices by default, or remain device-local unless the user opts in? This affects FR-128, FR-132, NFR-84, NFR-85, and API-4. This section assumes device-local by default with opt-in sync, and does not reduce scope either way — the answer only changes the default.
## Functional Requirements
### F-1 — Intelligent Task Prioritization (FR-1 .. FR-25)
### F-2 — Quick Add (FR-26 .. FR-50)
### F-3 — Focus Mode (FR-51 .. FR-75)
### F-4 — Progress Analytics (FR-76 .. FR-100)
### F-5 — Integration Hub (FR-101 .. FR-125)
### F-6 — Dark Mode (FR-126 .. FR-150)
## Non-Functional Requirements
### Performance
### Scalability & Availability
### Security
### Data & Residency
### Deployment & Environment
## User Stories
### F-1 — Intelligent Task Prioritization
#### US-1: See my work in priority order
  - As a busy professional, I want my active tasks ranked for me automatically, so that I always know what to do next without manually sorting.
#### US-2: Have multiple factors feed the ranking
  - As a user with mixed deadlines, I want ranking to consider due dates, importance, effort, age, and dependencies, so that the order reflects real-world urgency.
#### US-3: Understand why a task is ranked where it is
  - As a skeptical user, I want a plain-language explanation per task, so that I can trust the automatic ordering.
#### US-4: Tune the ranking to my style
  - As a user who values deadlines over effort, I want to adjust factor weights, so that ranking matches how I actually work.
#### US-5: Override the ranking when I disagree
  - As a user, I want to pin a task to the top, so that the system does not hide something I must do now.
#### US-6: Time-box my override
  - As a user, I want an override to expire, so that I do not leave stale pins that distort my queue forever.
#### US-7: Escalate genuine deadlines
  - As a user with a hard deadline, I want urgent tasks to rise as the deadline approaches, so that I don't miss commitments.
#### US-8: Respect dependency order
  - As a user, I want a task blocked by an unfinished dependency to rank below its blocker, so that I don't start work I can't finish.
#### US-9: See an empty queue gracefully
  - As a new user, I want a helpful prompt when nothing is active, so that I am not confused by a blank screen.
#### US-10: Stay responsive with a large backlog
  - As a heavy user, I want the queue to load and reorder quickly, so that prioritization never slows me down.
#### US-11: Operate the queue by keyboard
  - As a keyboard user, I want to navigate and pin/unpin without a mouse, so that I can work efficiently.
### F-2 — Quick Add
#### US-12: Capture a task in one line
  - As a user with a fleeting thought, I want to add a task by typing one line and pressing Enter, so that capture never interrupts my flow.
#### US-13: Use natural language for due dates
  - As a user, I want to type "tomorrow 5pm" and have it understood, so that I don't open a date picker.
#### US-14: Mark importance inline
  - As a user, I want to type "!!" or "urgent" to flag importance, so that the task feeds prioritization correctly.
#### US-15: Tag and contextualize inline
  - As a user, I want to type "#work" and "@home", so that tasks are organized as I capture them.
#### US-16: Preview what will be parsed
  - As a cautious user, I want to see how my line will be interpreted before I commit, so that I can catch mistakes.
#### US-17: Correct a misparse
  - As a user, I want to edit a parsed field in place, so that a wrong interpretation does not become a wrong task.
#### US-18: Fall back safely on unparseable input
  - As a user typing something unusual, I want the whole line kept as the title if nothing parses, so that I never lose input.
#### US-19: Resolve ambiguity predictably
  - As a user, I want ambiguous phrases handled consistently, so that behavior is learnable.
#### US-20: Undo an accidental add
  - As a user, I want to undo a just-created task, so that a slip does not clutter my list.
#### US-21: Respect my timezone
  - As a traveler, I want parsed times interpreted in my current timezone, so that "5pm" means 5pm where I am.
#### US-22: Capture while offline
  - As a user on a flaky connection, I want quick add to work offline, so that capture is never blocked.
#### US-23: Avoid accidental duplicates
  - As a user, I want a warning when I add a near-identical open task, so that I don't create clutter.
#### US-24: Complete the flow by keyboard only
  - As a keyboard user, I want to open, preview, and confirm quick add without a mouse, so that capture stays fast.
### F-3 — Focus Mode
#### US-25: Start focusing on a task
  - As a user, I want to begin a focus session from a task, so that I commit a block of time to it.
#### US-26: Use my preferred session length
  - As a user, I want a default session length I can rely on, so that starting focus requires no setup.
#### US-27: Set a custom duration
  - As a user with a longer task, I want to set a custom length, so that the timer matches my work.
#### US-28: Control the timer
  - As a user, I want to pause, resume, extend, and end, so that the session fits reality.
#### US-29: Never run two sessions at once
  - As a user, I want clear handling when a session is already active, so that my time records stay accurate.
#### US-30: See my session at a glance
  - As a user, I want an unambiguous on-screen timer, so that I know how long remains.
#### US-31: Work without distraction
  - As a user, I want a distraction-free surface during focus, so that I stay on one task.
#### US-32: Be reminded when time is up
  - As a user, I want a clear end-of-session signal, so that I can transition deliberately.
#### US-33: Know focused time was recorded
  - As a user, I want focus time attributed to the task, so that my history reflects the effort.
#### US-34: End a session early
  - As a user, I want to stop before time is up, so that an interrupted block is not lost.
#### US-35: Keep the timer accurate in the background
  - As a user, I want the timer to stay correct if I switch tabs, so that the app doesn't drift.
#### US-36: Recover from an interrupted session
  - As a user whose app closed mid-session, I want a sane recovery, so that nothing is silently lost.
#### US-37: Review my focus history
  - As a user, I want to see past sessions, so that I can understand my patterns.
#### US-38: Operate focus mode accessibly
  - As a user relying on assistive tech, I want the timer and controls accessible, so that I can use focus mode fully.
### F-4 — Progress Analytics
#### US-39: Reach my progress view
  - As a user, I want a dedicated Progress view, so that I can review how I am doing in one place.
#### US-40: See completion at a glance
  - As a user, I want to see completed, created, and net change, so that I understand my throughput.
#### US-41: Track completion rate over time
  - As a user, I want completion rate plotted over time, so that I can spot trends.
#### US-42: See my throughput
  - As a user, I want to see tasks completed per day/week/month, so that I can gauge capacity.
#### US-43: Keep my streak visible
  - As a user motivated by streaks, I want current and longest streak shown, so that I stay consistent.
#### US-44: Choose the period
  - As a user, I want to change the time window, so that I can look at a week, month, or year.
#### US-45: Inspect a data point
  - As a user, I want exact values on demand, so that a chart is not the only source of truth.
#### US-46: See a helpful empty state
  - As a new user, I want guidance when there is no data yet, so that I don't think analytics are broken.
#### US-47: Access analytics non-visually
  - As a screen-reader user, I want the metrics available as text, so that charts are not a barrier.
#### US-48: Keep day boundaries correct
  - As a user, I want my analytics to respect my timezone, so that "today" means my today.
#### US-49: Keep analytics fresh
  - As a user, I want metrics to reflect recent activity, so that the view is trustworthy.
#### US-50: Export my data
  - As a user, I want to export my metrics, so that I can keep or share a record.
#### US-51: Keep analytics private
  - As an individual user, I want my progress to be visible only to me, so that personal data stays personal.
### F-5 — Integration Hub
#### US-52: Browse what I can connect
  - As a user, I want a catalogue of source types, so that I know what is possible before committing.
#### US-53: Connect an account safely
  - As a user, I want to authorize a provider without typing my password into the app, so that my credentials stay safe.
#### US-54: Manage existing connections
  - As a user, I want to see and control my connections, so that I stay in charge of what is linked.
#### US-55: Label my connections
  - As a user with several accounts, I want to rename them, so that I can tell them apart.
#### US-56: Pause and resume syncing
  - As a user, I want to pause a connection, so that I can stop data flow without disconnecting.
#### US-57: Recover an expired connection
  - As a user whose token expired, I want a clear reconnect path, so that syncing resumes with minimal effort.
#### US-58: Disconnect completely
  - As a user, I want to disconnect, so that no further data is read or written.
#### US-59: Know sync status
  - As a user, I want last-sync time and state visible, so that I can tell whether data is current.
#### US-60: Understand a degraded integration
  - As a user, I want plain-language errors, so that I know whether to retry or reconnect.
#### US-61: Import work from a source
  - As a user, I want items from a connected source to become tasks, so that my external work appears in one place.
#### US-62: Write back to a source
  - As a user, I want supported changes to sync outward, so that I don't maintain two systems.
#### US-63: Resolve sync conflicts predictably
  - As a user with two-way sync, I want conflicts handled by a clear rule, so that data doesn't silently diverge.
#### US-64: Protect my credentials
  - As a security-conscious user, I want tokens stored and handled securely, so that a breach doesn't expose my accounts.
#### US-65: Use an accessible connector UI
  - As a user with assistive tech, I want the connection list and its actions accessible, so that I can manage integrations.
### F-6 — Dark Mode
#### US-66: Pick my theme
  - As a user, I want to choose light, dark, or system, so that the app suits my environment.
#### US-67: Follow my system setting
  - As a user, I want the app to follow my OS theme, so that it matches everything else on my device.
#### US-68: Keep my choice next time
  - As a user, I want my preference remembered, so that I don't re-select it every session.
#### US-69: Switch instantly
  - As a user, I want switching to be immediate, so that nothing looks half-updated.
#### US-70: Avoid a flash of the wrong theme
  - As a user, I want no bright flash on load in dark mode, so that the app doesn't dazzle me.
#### US-71: Read comfortably in both themes
  - As a user, I want sufficient contrast in either theme, so that content stays legible.
#### US-72: Keep imagery and charts consistent
  - As a user, I want visuals tuned per theme, so that nothing becomes unreadable or jarring.
#### US-73: Print and export sensibly
  - As a user printing a page, I want legible output regardless of theme, so that documents are usable.
#### US-74: Keep my theme across devices
  - As a signed-in user, I want my theme to follow me, so that each device feels consistent.
#### US-75: Theme every state
  - As a user, I want error, empty, and loading states themed too, so that nothing breaks the look.
## API Contracts
### 0. Scope map
### 1. Cross-cutting API conventions
### 2. F-1 — Intelligent Task Prioritization — API Contracts
### 3. F-2 — Quick Add — API Contracts
### 4. F-3 — Focus Mode — API Contracts
### 5. F-4 — Progress Analytics — API Contracts
### 6. F-5 — Integration Hub — API Contracts
  - **No credentials in the product's own fields (FR-102).** API-27 rejects any body containing a provider credential field (`422 credentials_not_accepted`). Credentials exist only inside the handshake completed at API-28 and are never returned by API-29, API-30, API-31, API-34, or any error envelope.
### 7. F-6 — Dark Mode — API Contracts
  - **Exactly one preference, product-wide (FR-126).** `preference` is a closed enum of three values and is stored per principal. There is deliberately **no** contract that sets a theme for a single screen, route, or widget — per-surface theming is not expressible in this API.
### 8. Cross-contract guarantees
### 9. API-level open questions
## Design Direction
## Components
### 1. Primitives
#### 1.1 Design tokens
#### 1.2 Atoms (product-agnostic)
### 2. Composed components
### 3. Feature components
#### 3.1 F-1 — Intelligent Task Prioritization
#### 3.2 F-2 — Quick Add
#### 3.3 F-3 — Focus Mode
#### 3.4 F-4 — Progress Analytics
#### 3.5 F-5 — Integration Hub
#### 3.6 F-6 — Dark Mode
### 4. Cross-feature composition rules
  - **One dominant thing per surface.** `TodayQueue` (F-1) is the spine of the home surface; `QuickAddInput` (F-2) floats above it as the only overlay line; `FocusShell` (F-3) temporarily *replaces* the spine entirely.
### 5. Component → feature traceability
## Data Models
### 0. Modelling conventions
### 1. Entity map
### 2. Core entities
#### DM-1 — Task
#### DM-2 — Tag
#### DM-3 — TaskTagLink
#### DM-4 — Project
#### DM-5 — TaskDependency
### 3. F-1 — Prioritization entities
#### DM-6 — PriorityProfile
#### DM-7 — PriorityScore (derived)
#### DM-8 — RankOverride
### 4. F-2 — Quick Add entities
#### DM-9 — CaptureAttempt
### 5. F-3 — Focus Mode entities
#### DM-10 — FocusSession
#### DM-11 — FocusSessionEvent
### 6. F-4 — Progress Analytics entities
#### DM-12 — ProgressPreference
#### DM-13 — DailyActivityRollup (derived)
#### DM-14 — StreakRecord (derived)
### 7. F-5 — Integration Hub entities
#### DM-15 — Connection
#### DM-16 — ConnectionSecretRef
#### DM-17 — SyncRun
#### DM-18 — ExternalItemLink
#### DM-19 — IntegrationAction
#### DM-20 — WebhookDelivery
### 8. F-6 — Dark Mode entity
#### DM-21 — ThemePreference
### 9. Platform entities
#### DM-22 — UserProfile
#### DM-23 — Device
#### DM-24 — AuditEvent
### 10. Cross-entity integrity
#### 10.1 Reference and deletion matrix
#### 10.2 Consistency units
### 11. Derived-data lifecycle
### 12. Retention and purge
### 13. Data-flow map (feature ↔ models ↔ API ranges)
### 14. Modelling constraints and non-goals
### Open Questions
