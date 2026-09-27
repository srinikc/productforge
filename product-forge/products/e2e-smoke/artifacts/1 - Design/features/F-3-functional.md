## F-3: Focus Mode

> **Feature id:** F-3 · **Owned global id ranges:** FR-51..FR-75, NFR-31..NFR-45, US-31..US-45 · **Local ids** (BR-, V-, EC-, EH-, AC-, API-, DM-, T-, OQ-) are scoped to this feature and numbered sequentially from 1. References to F-1 / F-2 ids are plain text only; this section never re-defines them.

### Requirements

**Functional Requirements (global ids — owned range FR-51..FR-75)**

| ID | Name | Description |
|---|---|---|
| FR-51 | Enter focus on a task | The user can start a focus session bound to a single existing task from the task detail view, the "Today" queue (F-1), or a quick-add result (F-2). |
| FR-52 | Default session length | Sessions run for a configurable default duration (built-in default 25 minutes) expressed in whole minutes. |
| FR-53 | Custom session length | Before or during a session the user can set a custom duration within the supported range (see V-1). |
| FR-54 | Timer controls | The user can start, pause, resume, extend, and end a session. Every state change is reflected immediately in the UI. |
| FR-55 | Single active session | At most one focus session may be active at a time; starting a new one while another is active requires an explicit decision (see BR-3). |
| FR-56 | Pomodoro cycles | The user can run repeating work/break cycles: a work block, a short break, and after a configurable number of work blocks a long break. |
| FR-57 | Break handling | During a break the task context is preserved; ending a break early is allowed and immediately starts the next work block. |
| FR-58 | Focus time logging | All elapsed focus time (excluding paused intervals) is recorded against the linked task with a start timestamp, end timestamp, and duration. |
| FR-59 | Session completion prompt | When the timer reaches zero the system notifies the user and prompts to mark the task complete, extend, or take a break. |
| FR-60 | Interruption record | If the user pauses, leaves the app, or ends a session before completion, the session is recorded as an interruption with a user-selectable reason (optional). |
| FR-61 | Focus queue | The user can queue a sequence of tasks for consecutive focus sessions; when one session ends the next queued task is offered. |
| FR-62 | Distraction suppression | While a session runs, the app suppresses its own non-critical notifications and any in-app content not related to the focused task. |
| FR-63 | Do-not-disturb indicator | A persistent, dismissible indicator shows that focus is active, and its state is exposed to the operating system's DND mechanism where available. |
| FR-64 | Ambient sound | The user can optionally play a provided ambient/white-noise loop during a session, with an independent volume control. |
| FR-65 | Focus statistics | The user can view focus time per day/week and per task, plus session counts and completion rate. |
| FR-66 | Daily focus goal | The user can set a daily focus-time goal and see progress toward it. |
| FR-67 | Session persistence | An active session survives app backgrounding, navigation, and restart; on relaunch the timer resumes with correct remaining time. |
| FR-68 | Auto-start option | The user can opt in to automatically start breaks and the next work block without a manual confirm step. |
| FR-69 | Keyboard and shortcut control | Every timer control has a keyboard shortcut and, where available, a global shortcut or widget entry point. |
| FR-70 | Manual time correction | The user can add or subtract elapsed focus time on a recorded session to correct for time spent away. |
| FR-71 | Focus mode theming | Focus mode renders in a reduced, low-distraction layout showing only the timer, the task title, and controls. |
| FR-72 | Exit focus mode | Exiting focus mode returns the user to their previous location and, if a session was active, records/handles it per FR-58 and FR-60. |
| FR-73 | Multi-task attribution | Focus time can be split across two tasks when the user switches the linked task mid-session; each segment is recorded against its task. |
| FR-74 | Focus reminders | The user can schedule optional reminders to start a focus session at configured times. |
| FR-75 | Session notes | After a session the user can attach a short free-text note to the recorded session. |

**Non-Functional Requirements (global ids — owned range NFR-31..NFR-45)**

| ID | Category | Target |
|---|---|---|
| NFR-31 | Performance | Entering focus mode and rendering the first frame completes in < 150 ms on the reference device and < 400 ms on a low-end device. |
| NFR-32 | Performance | The countdown timer drifts by no more than ±250 ms over a 60-minute continuous session. |
| NFR-33 | Scalability / availability | Focus sessions run fully offline; locally recorded time is retained and reconciled when connectivity returns. |
| NFR-34 | Security | Focus session data and notes are accessible only to the owning authenticated user; no cross-user leakage in logs or telemetry. |
| NFR-35 | Data / residency | Session records (timestamps, duration, task id, note) are retained for at least 24 months and are exportable/deletable by the user. |
| NFR-36 | Deployment / environment | Works on desktop and mobile web plus the packaged desktop/mobile shells; no feature requires hardware not present in the baseline environment. |
| NFR-37 | Accessibility | All timer controls are keyboard reachable, the remaining time is exposed via an ARIA live region (polite), and the countdown is not conveyed by color alone. |
| NFR-38 | Power | Ambient sound and the running timer must not prevent device sleep beyond what the platform requires for an actively running timer. |
| NFR-39 | Cross-device | Starting/ending a session on one device propagates state to the user's other signed-in devices within 10 s when online. |
| NFR-40 | Notification reliability | End-of-session and break notifications are delivered on time (±2 s) when the app is backgrounded and notifications are permitted. |
| NFR-41 | Internationalization | Durations, dates, and times respect the user's locale and 12/24-hour preference; all copy is externalized for translation. |
| NFR-42 | Reliability | No recorded session is lost on crash/restart; at most 5 s of elapsed time may be lost in the worst case. |
| NFR-43 | Concurrency | Concurrent session starts from two devices resolve deterministically to a single active session (see BR-3). |
| NFR-44 | Observability | Session start/pause/end and timer-drift anomalies emit structured, PII-free telemetry. |
| NFR-45 | Usability | A first-time user can start a focus session in ≤ 2 interactions from the task view; controls remain operable with one hand on mobile. |

**User Stories (global ids — owned range US-31..US-45)**

- **US-31:** As a busy professional, I want to start a focus session on a task so that I work on it without distraction.
- **US-32:** As a busy professional, I want to choose how long a session lasts so that it fits my available time.
- **US-33:** As a busy professional, I want to pause and resume so that short interruptions do not break my session.
- **US-34:** As a busy professional, I want repeating work/break cycles so that I maintain sustainable attention.
- **US-35:** As a busy professional, I want the app to stop distracting me during focus so that I stay on task.
- **US-36:** As a busy professional, I want my focus time recorded against the task so that my history reflects real effort.
- **US-37:** As a busy professional, I want a prompt when the timer ends so that I know to stop or continue.
- **US-38:** As a busy professional, I want to queue the next task so that I flow from one session to the next.
- **US-39:** As a busy professional, I want optional ambient sound so that I can mask background noise.
- **US-40:** As a busy professional, I want to see my focus statistics so that I can understand my habits.
- **US-41:** As a busy professional, I want a daily focus goal so that I stay accountable.
- **US-42:** As a busy professional, I want my session to survive a restart so that I do not lose my progress.
- **US-43:** As a busy professional, I want to correct recorded time so that the history is accurate.
- **US-44:** As a busy professional, I want to switch the task mid-session so that unplanned work is still tracked.
- **US-45:** As a keyboard-first user, I want shortcuts for all timer controls so that I never leave the keyboard.

### Behaviour

1. **Entry.** Focus mode can be entered from the task detail view, from a "Today" queue item, or from the result of a quick add. Entry requires a linked task; the UI offers task selection if none is supplied (see EH-2).
2. **Session lifecycle.** A session moves through `idle → running → (paused ⇄ running) → completed | ended-early | abandoned`. Transitions are user-triggered except `running → completed` (timer reaches zero) and `running → abandoned` (see EC-6).
3. **Countdown.** While `running` the remaining time decreases in real time; while `paused` it is frozen. The displayed value derives from an absolute end timestamp so that backgrounding cannot desynchronize it.
4. **Cycles.** In cycle mode a work block is followed by a short break; after N completed work blocks (default 4, configurable) a long break replaces the short one. Cycle count and phase are shown in the UI.
5. **Completion.** At zero the app fires an end-of-session notification (NFR-40) and presents the completion prompt (FR-59). If auto-start (FR-68) is enabled, the next phase begins after a short grace period unless the user intervenes.
6. **Logging.** On every terminal transition the elapsed *running* time (pauses excluded) is written as one or more session records, attributed to the linked task(s) per FR-73, and optionally annotated with a note (FR-75).
7. **Suppression.** For the duration of `running`, non-critical in-app notifications are queued rather than shown and are released when the session ends.
8. **Restoration.** On relaunch the app reads persisted session state; a session whose end time has already passed is completed retroactively with the elapsed time capped at the configured duration.

### Business rules

- **BR-1:** A focus session must always reference exactly one linked task at any instant; task reassignment is recorded as a segment boundary.
- **BR-2:** Only time in the `running` state counts toward focus totals and statistics; `paused` and break intervals are excluded from focus totals but breaks are recorded separately.
- **BR-3:** If a session is already active, starting another is blocked until the user chooses one of: *end current and start new*, *queue new task*, or *cancel*.
- **BR-4:** Aggregate focus time per session may not exceed the configured duration by more than the user-approved extension amount.
- **BR-5:** Break minutes are recorded but never counted toward the daily focus goal (FR-66).
- **BR-6:** A session record is immutable once written, except for the note and the manual correction permitted by FR-70, which is stored as an adjustment rather than an overwrite.
- **BR-7:** Focus statistics are computed from session records, never from derived counters, so that corrections and splits are always reflected.
- **BR-8:** Long-break eligibility resets when the cycle count resets (new day or explicit reset by the user).
- **BR-9:** Distraction suppression never blocks safety-critical, security, or system-level notifications.
- **BR-10:** Default durations are user-scoped settings; changing them does not alter sessions already recorded.

### Validation

- **V-1:** Session duration must be a whole number of minutes within the inclusive range 1–180. Values outside the range are rejected inline with the allowed range shown.
- **V-2:** Break duration must be a whole number of minutes within the inclusive range 1–60.
- **V-3:** Work-block count before a long break must be an integer in the inclusive range 1–12.
- **V-4:** Manual time correction (FR-70) must keep total net focus time for the session ≥ 0 and ≤ 24 hours; empty or non-numeric input is rejected.
- **V-5:** A session note is at most 500 characters; leading/trailing whitespace is trimmed; an empty note is treated as "no note".
- **V-6:** Focus reminders (FR-74) require a valid time-of-day in the user's locale and at least one selected weekday.
- **V-7:** Daily focus goal must be a whole number of minutes in the inclusive range 1–1440.
- **V-8:** A segment produced by mid-session task switching (FR-73) must have a positive duration; zero-length segments are discarded silently.

### Edge cases

- **EC-1:** Timer reaches zero while the app is backgrounded or closed → on resume, the completion prompt is shown and the session is finalized (see Behaviour 8).
- **EC-2:** Device clock changes or is manually altered while a session runs → remaining time is recomputed from the persisted absolute end timestamp using monotonic elapsed time; a negative remaining time clamps to zero and finalizes the session.
- **EC-3:** A session spans midnight → the record keeps its true start/end timestamps; statistics attribute focus time to the calendar day in which the time was actually spent.
- **EC-4:** Daylight-saving transition during a session → elapsed time is computed from monotonic duration, not wall-clock subtraction.
- **EC-5:** User pauses and resumes repeatedly → each interval is tracked; total paused time is reported separately and excluded from focus totals (BR-2).
- **EC-6:** User ends a session with less than 1 minute elapsed → the session is discarded and not stored, to avoid noise records.
- **EC-7:** Linked task is deleted mid-session → the session continues; the recorded segment is attributed to a "deleted task" placeholder that preserves the historical duration.
- **EC-8:** Linked task is completed mid-session → a non-blocking prompt offers to end the session or continue; continuing keeps attribution.
- **EC-9:** Task switched mid-session and switched back → two segments for the same task are created and summed in statistics (BR-7).
- **EC-10:** Ambient sound interrupted by an incoming call or another app's audio focus → sound pauses and resumes automatically when focus returns; the timer keeps running.
- **EC-11:** Two devices start sessions concurrently (NFR-43) → the earlier start wins; the later device shows the active session and offers *join* or *end-and-restart*.
- **EC-12:** User is in the middle of a break when the daily goal is reached → the goal indicator updates but the break is not truncated.
- **EC-13:** Free/busy calendar integration is unavailable (no data source configured) → no focus-time suggestion is shown; the manual picker remains fully functional. No mock data is substituted.

### Error handling

- **EH-1:** Timer state fails to persist locally → the session continues in memory, a non-blocking warning is shown, and a retry is scheduled; if persistence still fails at session end, the record is held in memory for the remainder of the app run and the user is warned that it may be lost.
- **EH-2:** Session entered without a linked task → the app shows a task picker; dismissing it returns to the previous screen without starting a session.
- **EH-3:** End-of-session notification permission denied → the app falls back to an in-app alert shown on next app focus, and offers a link to notification settings.
- **EH-4:** Ambient sound asset fails to load or decode → sound is disabled, an inline message is shown, and the timer is unaffected (no silent failure).
- **EH-5:** Manual time correction rejected by validation (V-4) → inline error under the field, correction not applied, session unchanged.
- **EH-6:** Session sync to the server fails → the local record is retained and queued for retry (NFR-33); the user sees a "will sync" indicator rather than an error.
- **EH-7:** Statistics cannot be computed because records are still syncing → partial totals are shown with a "some sessions pending sync" label; no fabricated numbers are displayed.
- **EH-8:** Unhandled failure during focus mode → the app exits focus mode, restores the previous screen, preserves any locally written session record, and reports the failure without exposing internal detail.

### Acceptance criteria

- **AC-1:** Given a task, when the user starts focus mode, then a session begins with the configured default duration and the task title is visible in the reduced layout. (FR-51, FR-52, FR-71)
- **AC-2:** Given an active session, when the user pauses and resumes, then the countdown stops and restarts and paused intervals are excluded from recorded focus time. (FR-54, BR-2)
- **AC-3:** Given a session running for 60 minutes, when measured against a reference clock, then drift is ≤ ±250 ms. (NFR-32)
- **AC-4:** Given an active session, when the timer reaches zero, then a notification is delivered and a prompt offering complete / extend / break is shown. (FR-59, NFR-40)
- **AC-5:** Given cycle mode with 4 work blocks, when the 4th work block completes, then a long break starts instead of a short break. (FR-56, BR-8)
- **AC-6:** Given an active session, when a non-critical in-app notification is generated, then it is queued and released only after the session ends. (FR-62, BR-9)
- **AC-7:** Given a session ends after 20 minutes, when the user views the task, then 20 minutes of focus time is attributed to that task. (FR-58)
- **AC-8:** Given a running session, when the app is killed and relaunched, then the session resumes with the correct remaining time. (FR-67, NFR-42)
- **AC-9:** Given a session in progress, when the user switches the linked task, then two segments are recorded and each is attributed to its task. (FR-73, EC-9)
- **AC-10:** Given an active session, when the user starts a second session, then a blocking choice of end-and-start / queue / cancel is presented and only one session remains active. (FR-55, BR-3)
- **AC-11:** Given an ended session, when the user applies a −5 minute correction, then focus totals reflect the adjustment and the original record is unchanged. (FR-70, BR-6)
- **AC-12:** Given a session started from the task view, when the user operates entirely by keyboard, then all controls are reachable and the remaining time is announced via a polite live region. (NFR-37, FR-69)
- **AC-13:** Given a session under 1 minute, when the user ends it, then no session record is stored. (EC-6)
- **AC-14:** Given a daily goal of 120 minutes and 90 recorded focus minutes, when the user views the goal, then progress shows 90/120 and break minutes are excluded. (FR-66, BR-5)
- **AC-15:** Given no connectivity, when a session is run and completed, then the record is stored locally and syncs when the connection returns. (NFR-33, EH-6)

### API behaviour

- **API-1 — Start session.** `POST /focus-sessions` with `{ taskId, plannedDurationMinutes, cycleConfig? }` → `201` returning `{ id, taskId, state: "running", startedAt, endsAt, plannedDurationMinutes }`. `409` if an active session already exists (BR-3); `422` if `taskId` is missing/unknown or duration violates V-1.
- **API-2 — Read current session.** `GET /focus-sessions/active` → `200` with the active session and its segments, or `204` when none is active. Must be safe and idempotent.
- **API-3 — Transition state.** `PATCH /focus-sessions/{id}` with `{ action: "pause" | "resume" | "end" | "extend", extendMinutes?, reason? }` → `200` with the updated session. Invalid transitions (e.g. resume while running) return `409` with the current state.
- **API-4 — Switch linked task.** `POST /focus-sessions/{id}/segments` with `{ taskId }` → `201` closing the current segment and opening a new one; `422` for a zero-length segment (V-8).
- **API-5 — Correct recorded time.** `POST /focus-sessions/{id}/adjustments` with `{ deltaMinutes, note? }` → `201`; `422` if the resulting net time violates V-4.
- **API-6 — Attach note.** `PATCH /focus-sessions/{id}` with `{ note }` → `200`; `422` if the note exceeds 500 characters (V-5).
- **API-7 — List history.** `GET /focus-sessions?from=&to=&taskId=&cursor=` → `200` with a cursor-paginated list of session records, excluding sub-minute discarded sessions (EC-6).
- **API-8 — Statistics.** `GET /focus-stats?granularity=day|week&from=&to=` → `200` with `{ focusMinutes, breakMinutes, sessionCount, completionRate }`; must be recomputed from records (BR-7). While records are pending sync the response includes `pendingSync: true` (EH-7).
- **API-9 — Settings.** `GET/PUT /focus-settings` for default duration, break durations, cycle count, auto-start, goal, reminders, ambient-sound preference; `422` on any value failing V-1, V-2, V-3, V-6, or V-7.
- **API-10 — Offline queue.** All mutating calls above accept a client-generated idempotency key; retries with the same key must not create duplicate sessions or segments. Conflict resolution follows BR-3 and NFR-43 (earliest start wins).
- **API-11 — Errors.** All endpoints return a stable machine-readable `code`, a human-readable `message`, and no PII in `code`. Auth failures return `401`; authorization failures `403`; unknown session `404`.

### Priority

- **Must-have:** FR-51, FR-52, FR-54, FR-55, FR-58, FR-59, FR-62, FR-67, FR-71, FR-72, NFR-31, NFR-32, NFR-33, NFR-34, NFR-40, NFR-42.
- **Should-have:** FR-53, FR-56, FR-57, FR-60, FR-63, FR-65, FR-68, FR-70, FR-73, FR-75, NFR-35, NFR-37, NFR-39, NFR-41, NFR-43, NFR-45.
- **Nice-to-have:** FR-61, FR-64, FR-66, FR-69, FR-74, NFR-36, NFR-38, NFR-44.
