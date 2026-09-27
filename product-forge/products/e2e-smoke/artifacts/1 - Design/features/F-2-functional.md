## F-2: Quick Add

> **Feature id:** F-2 · **Owned global id ranges:** FR-26..FR-50, NFR-16..NFR-30, US-16..US-30 · **Local ids** (BR-, EC-, AC-, API-) are scoped to this feature and numbered sequentially from 1.

### Requirements

**Functional Requirements (global ids — owned range FR-26..FR-50)**

| ID | Name | Description |
|---|---|---|
| FR-26 | Single-input capture | A single free-text line is the only mandatory input; one confirm action (Enter or "Add") creates a task. Reachable from every primary screen without opening a multi-field form. |
| FR-27 | Natural-language date/time parsing | The parser recognizes natural-language date/time expressions ("tomorrow 5pm", "next Monday", "in 2 hours", "2026-01-05 14:00") and binds the resolved value to the task's due date/time. |
| FR-28 | Priority & importance parsing | Recognizes inline priority markers (`!!`, `!`, "high", "urgent", "p1") and maps them to the task's explicit-importance field consumed by F-1 prioritization. |
| FR-29 | Tag / project / context parsing | Recognizes `#tag` and `@context` tokens and attaches them to the task as tags/project; unrecognized tokens remain part of the title. |
| FR-30 | Parsed-field preview | Interpreted fields (title, due date/time, importance, tags, project) are rendered as distinct chips before/at save, so the user sees what the parser decided. |
| FR-31 | Inline correction of parsed fields | Any parsed chip can be edited or removed before saving without leaving the Quick Add input. |
| FR-32 | Defaults application | Fields not supplied or parsed inherit the user's configured defaults (default project, default due = none, default priority = none). |
| FR-33 | Rapid capture mode | After a successful save the input clears and stays focused so tasks can be added consecutively; Escape exits the mode. |
| FR-34 | Undo last capture | The most recent capture can be undone within a defined window, deleting the created task and restoring the original input text. |
| FR-35 | Offline capture & deferred sync | With no network, captures persist locally and queue; a pending-count badge is shown; queued items sync exactly once on reconnect with no data loss. |
| FR-36 | Duplicate detection | On save, a near-duplicate of an open task's title triggers a non-blocking warning offering "Add anyway" or "Open existing". |
| FR-37 | Keyboard-first & accessible operation | Fully operable by keyboard alone; screen readers announce parsed fields, save confirmation, and errors. |
| FR-38 | Save confirmation | A brief toast confirms creation with an inline "Undo" action and an "Open task" link. |

**Non-Functional Requirements (global ids — owned range NFR-16..NFR-30)**

| ID | Category | Target |
|---|---|---|
| NFR-16 | Performance — invocation | Input becomes visible and focused in <100 ms from shortcut/click. |
| NFR-17 | Performance — parsing | Preview returned in <50 ms for inputs ≤200 characters. |
| NFR-18 | Performance — save | Local task creation reflected in UI in <100 ms (optimistic); server ack must never block the input. |
| NFR-19 | Scalability / availability | Sustains ≥20 captures/min per user without UI degradation; capture remains usable while offline. |
| NFR-20 | Security | Input sanitized; task text is not sent to third-party parsers; parsing stays inside the app trust boundary; transport is TLS. |
| NFR-21 | Data / residency | Captured text and parsed fields are stored in the user's configured data region; the on-device offline queue is encrypted at rest. |
| NFR-22 | Deployment / environment | Works across supported browsers/OSes with no native-only APIs; degrades gracefully where notifications are unavailable. |

**User Stories (global ids — owned range US-16..US-30)**

| ID | Story |
|---|---|
| US-16 | As a busy professional, I want to capture a task in one line, so that I don't lose the thought while switching contexts. |
| US-17 | As a frequent typist, I want natural-language dates and priorities recognized, so that I can capture without filling a form. |
| US-18 | As a mobile user, I want to capture tasks offline, so that a flaky connection never costs me a task. |
| US-19 | As a careful user, I want to review and correct what the app parsed, so that a misread date never silently mis-schedules my work. |
| US-20 | As a user, I want to undo a mistaken capture, so that a typo or wrong keystroke is recoverable instantly. |

### Behaviour

1. **Invocation** (FR-26): the user opens Quick Add via a global shortcut, a persistent "+" affordance, or the empty-state CTA. The field is focused and ready for input on open.
2. **Typing** (FR-27, FR-28, FR-29): as text is entered, the parser resolves date/time, importance markers, `#tags`, and `@contexts`. The title is the residual text after consumed tokens are removed.
3. **Preview** (FR-30): resolved fields appear as editable chips next to the input. Chips update live as the text changes.
4. **Correction** (FR-31): the user may click/backspace a chip to edit or remove it; corrections are reflected in the saved task and never mutate the visible title.
5. **Confirm** (FR-26): Enter or "Add" persists the task. Defaults fill any gaps (FR-32). A duplicate check runs before persistence (FR-36).
6. **Feedback** (FR-38): a toast confirms creation with "Undo" and "Open". The input clears and refocuses for the next task (FR-33).
7. **Offline** (FR-35): when disconnected, the task is created locally, marked pending, and flushed on reconnect via an idempotent queue.
8. **Undo** (FR-34): within the undo window, "Undo" or the shortcut removes the created task and restores the prior input text.

### Business rules

| ID | Rule |
|---|---|
| BR-1 | A task is created only on explicit confirmation (Enter / "Add"); typed-but-unconfirmed text is never persisted. |
| BR-2 | The task title is the input text minus tokens consumed by parsing (dates, importance markers, `#tags`, `@contexts`). |
| BR-3 | If parsing would consume the entire input leaving no title, the raw text becomes the title and no field is parsed (no empty tasks). |
| BR-4 | A parsed due date in the past is not auto-applied; it is surfaced for confirmation instead of silently scheduling in the past. |
| BR-5 | Explicitly parsed values override configured defaults; defaults apply only when nothing is parsed or supplied. |
| BR-6 | The importance marker maps to the explicit-importance input consumed by F-1; Quick Add must not set the pin/override state owned by F-1. |

### Validation

| ID | Rule |
|---|---|
| BR-7 | Title length is 1–500 characters after trimming; leading/trailing whitespace is trimmed. |
| BR-8 | Line breaks are disallowed (single-line field); non-printable/control characters are stripped. |
| BR-9 | Tags must match `#[\p{L}\p{N}_-]+`, ≤50 chars each, ≤20 tags per task. |
| BR-10 | `@context` tokens must resolve to an existing project; a new project is created only with explicit user confirmation. |
| BR-11 | Due date/time must be within the supported range (≥1970, ≤100 years ahead). |
| BR-12 | Input longer than 500 characters is rejected inline before save and never silently truncated. |

### Edge cases

| ID | Case & handling |
|---|---|
| EC-1 | Ambiguous date ("next Friday" on a Friday): nearest future occurrence is chosen and shown as a chip for confirmation. |
| EC-2 | Multiple date expressions: only the first is parsed; the remainder stays in the title. |
| EC-3 | Time zone / DST boundary or user travel: due time is stored in the user's configured zone at capture time and displayed locally. |
| EC-4 | Empty input + Enter: no-op, no error, no task. |
| EC-5 | Metadata-only input (e.g., `#urgent`): falls back per BR-3. |
| EC-6 | Repeated Enter presses: debounced to create exactly one task per confirmation. |
| EC-7 | Offline queue at storage cap: new captures still accepted; user warned when local storage is exhausted. |
| EC-8 | Intentionally identical captures: allowed after the duplicate warning (FR-36). |

### Error handling

| ID | Failure & handling |
|---|---|
| EC-9 | Parse engine/service failure: fall back to raw-text title + defaults; the task is still creatable and never blocked. |
| EC-10 | Save/network failure: task is retained in the offline queue and shown as "will sync"; it is never lost or double-created. |
| EC-11 | Sync conflict (task edited/deleted elsewhere): keep the captured copy and flag it for user resolution; never silently drop. |
| EC-12 | Undo after sync: undo issues a delete; if the task was modified post-sync, prompt before deleting. |
| EC-13 | Validation failure (BR-7..BR-12): inline error near the field, input preserved, save blocked until corrected. |

### Acceptance criteria

| ID | Given / When / Then |
|---|---|
| AC-1 | **Given** the Quick Add field is focused, **when** the user types `Call Sam tomorrow 4pm` and presses Enter, **then** a task titled "Call Sam" with due date = tomorrow 16:00 (user zone) is created. |
| AC-2 | **Given** the user types a date expression, **when** parsing completes, **then** a due-date chip appears showing the resolved date/time. |
| AC-3 | **Given** the input contains `!!`, **when** saved, **then** the task's explicit importance is set to high and the chip reflects it. |
| AC-4 | **Given** the input contains `#billing`, **when** saved, **then** the tag "billing" is attached and shown as a chip. |
| AC-5 | **Given** a parsed chip is shown, **when** the user edits it, **then** the saved task reflects the corrected value and the title is unchanged. |
| AC-6 | **Given** no due date is supplied, **when** the task is saved, **then** the configured default due value is applied. |
| AC-7 | **Given** a task was just saved, **when** the toast appears, **then** the input is empty and focused for the next entry. |
| AC-8 | **Given** a task was just saved, **when** the user triggers Undo within the window, **then** the task is removed and the original input text is restored. |
| AC-9 | **Given** the device is offline, **when** the user captures a task, **then** it appears immediately with a pending-sync badge and is created exactly once after reconnect. |
| AC-10 | **Given** an open task with the same normalized title exists, **when** the user saves, **then** a non-blocking duplicate warning offers "Add anyway"/"Open existing" and no task is created until a choice is made. |
| AC-11 | **Given** keyboard-only use, **when** the user invokes Quick Add and saves, **then** every step is operable without a pointer and focus order is logical. |
| AC-12 | **Given** a task is created, **when** save succeeds, **then** a toast confirms creation and offers Undo and "Open". |

### API behaviour

| ID | Endpoint / behaviour |
|---|---|
| API-1 | `POST /tasks` — creates a task from a Quick Add capture. Body: `{ rawText, title, dueAt?, importance?, tags[], projectId?, clientKey }`. Returns the created task (id, normalized fields). |
| API-2 | `POST /tasks/parse` (optional; may be client-side) — resolves free text to `{ title, dueAt, importance, tags[], projectId, confidence }` without persisting. |
| API-3 | `POST /tasks/sync` — flushes the offline queue as a batch with per-item idempotency keys; response reports accepted/duplicate/rejected per item. |
| API-4 | `DELETE /tasks/{id}` — used by Undo; supports an `If-Unmodified-Since` guard to avoid deleting a post-sync-modified task (EC-12). |
| API-5 | Idempotency — every create carries a client-generated `clientKey`; on a duplicate key the server returns the already-created task (HTTP 200) instead of a second task. |
| API-6 | Status codes — `400` validation (BR-7..BR-12), `409` near-duplicate/conflict, `422` unparseable-but-storable (falls back per EC-9), `429` rate limit, `5xx` with offline-queue fallback (EC-10). |

### Priority

**Must-have.** Quick Add is the primary low-friction capture path that feeds the F-1 prioritization queue; without it the product's core loop (capture → prioritize → act) cannot function, and NFR-16..NFR-22 all gate on invocability and offline durability.
