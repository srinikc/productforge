# Requirements — MyWorld MVP

## Project Overview
MyWorld is a central personal portal/dashboard hub. MVP includes: Core Bento Grid, Universal Search, ToDo (with voice), Calendar (Google sync). Full E2E working, not prototype. Zero budget, multi-user (Google OAuth), cross-platform (Web PWA + Android).

## Functional Requirements

### FR-1: Authentication
- Users sign in via Google OAuth2
- JWT tokens for session management
- Row-level data isolation per user
- Multi-profile support (family members)

### FR-2: Core Bento Grid Dashboard
- 12-column responsive layout
- Frosted-glass card tiles (backdrop-filter blur)
- Each module is a standalone micro-app tile
- Focused layout: fewer tiles per row, larger tap targets, generous whitespace
- Smooth hover micro-interactions (scale-102)

### FR-3: Universal Search
- Cross-module search across all user data
- Real-time search results as user types
- Search across todos, calendar events, and module content

### FR-4: ToDo Task Engine
- Create, read, update, delete tasks
- Sort by: Day, Week, Month, Year
- Set reminders with notifications
- Cross-link tasks to Calendar events
- Voice input for creating tasks (open-source: Whisper/Vosk)
- Offline support: view and edit tasks without internet

### FR-5: Calendar / Events
- Bidirectional Google Calendar sync (read + write back)
- Create, edit, delete events
- Color-coded event types
- Birthday/anniversary reminders (manual entry + contact import)
- Google People API integration for contact import — scope: `https://www.googleapis.com/auth/contacts.readonly` (read-only, requested via incremental consent only when the user triggers the import)
- Festival and scheduled event display
- Push notifications for upcoming events
- Offline support: view cached events

### FR-6: Reminders / Notifications
- Time-based reminders for todos and events
- Push notifications (web + mobile)
- WebSocket for real-time reminder delivery

## Non-Functional Requirements

### NFR-1: Performance
- Initial page load under 3 seconds on 4G mobile
- Module tiles render within 1 second
- Search results within 500ms

### NFR-2: Security
- Google OAuth2 authentication
- JWT with short expiry + refresh tokens
- Row-level encryption for sensitive data
- HTTPS everywhere
- No sensitive data in logs

### NFR-3: Accessibility
- WCAG 2.1 AA compliance
- Keyboard navigation for all features
- Screen reader support (TalkBack/VoiceOver)
- Sufficient contrast ratios on dark theme

### NFR-4: Offline
- ToDo: full CRUD offline, sync when online
- Calendar: read cached events offline
- Graceful degradation for all modules

### NFR-5: Cross-Platform
- Web PWA (Next.js) + Android (React Native) for MVP; iOS in Phase 2
- Full feature parity across platforms
- Responsive design: mobile 375px, tablet 768px, desktop 1024px+

## Data Models

### User
- id, email, name, avatar, provider (google), createdAt, updatedAt

### Todo
- id, userId, title, description, priority, dueDate, recurrence (daily/weekly/monthly/yearly), status, linkedEventId, linkedGoalId, createdAt, updatedAt

### Event
- id, userId, title, description, startDate, endDate, allDay, color, source (manual/google), googleEventId, reminders[], createdAt, updatedAt

### Reminder
- id, userId, todoId?, eventId?, message, triggerAt, type (push/in-app), sent, createdAt

## API Endpoints (MVP)
- POST /api/auth/google (OAuth login)
- GET /api/auth/me (current user)
- GET/POST/PUT/DELETE /api/todos
- POST /api/todos/voice (voice-to-text)
- GET/POST/PUT/DELETE /api/calendar/events
- POST /api/calendar/sync/google
- GET /api/dashboard
- GET /api/search
- GET/POST /api/reminders

## Constraints
- Zero budget (all free tiers)
- Module-by-module development (each fully E2E before next)
- DPDP compliance deferred to Phase 2
- Open-source voice recognition only
- Monorepo with Turborepo

---

## User Stories (MVP)

> Stories are written from the user's perspective and trace back to one or more FRs above. Each story is sized to fit a single iteration of the module-by-module plan (product plan §Phased Execution).

### US-1: Sign in
**As a** user (primary or family member), **I want to** sign in with my Gmail account **so that** I see only my own data and never anyone else's.
- **Covers:** FR-1, NFR-2, NFR-3
- **Acceptance:**
  - Tapping "Sign in with Google" launches the Google OAuth flow and returns me to the dashboard signed in.
  - After sign-in, my dashboard is empty on first run; my data is fetched only for my user id.
  - I cannot see another user's todos, calendar, or any future module data even if I know their id.
  - Sign-in works on mobile browsers and inside the installed PWA / native app.
  - Session survives an app reload; signing out clears the session and routes me back to the sign-in screen.

### US-2: Recognize a familiar dashboard
**As a** returning user, **I want to** see a calm, dark, low-density home screen **so that** I can find the right module quickly without feeling overwhelmed.
- **Covers:** FR-2, NFR-1, NFR-3, NFR-5
- **Acceptance:**
  - Home is a Bento Grid with one tile per active module (MVP: Search, ToDo, Calendar).
  - Tiles are large enough to tap comfortably on a 375px-wide phone.
  - The grid reflows: 2 cols on phone, 3 on tablet, 4 on desktop.
  - All text meets WCAG 2.1 AA contrast against the dark background.

### US-3: Find anything via one search box
**As a** user, **I want to** type a single query **so that** I can jump from "I remember something happened in October" to the specific todo or event without opening each module.
- **Covers:** FR-3, NFR-1
- **Acceptance:**
  - Search box is reachable from the dashboard in one tap and from a global keyboard shortcut.
  - Results appear while I type, with at most ~500ms perceived latency on 4G.
  - Results are grouped by module (ToDo, Calendar) with a deep-link to the item.
  - If no results, I see a clear empty state — not a blank panel.

### US-4: Capture a thought as a todo — by typing or by voice
**As a** user, **I want to** say "remind me to call Mom tomorrow at 6" **so that** the todo lands in my list without me typing.
- **Covers:** FR-4, FR-6, NFR-1, NFR-4, NFR-5
- **Acceptance:**
  - I tap the floating mic; speak; the todo appears in my list with title, date, and time filled in.
  - I can also type the todo and get the same result.
  - I can create, edit, complete, and delete a todo while offline; changes sync when I'm back online.
  - Recurring todos (daily / weekly / monthly / yearly / specific date) generate the next instance after completion.
  - I can link a todo to a calendar event; the link is visible on both sides.

### US-5: Never miss a birthday or anniversary
**As a** user, **I want to** add birthdays and anniversaries once **so that** I get reminded every year without re-entering them.
- **Covers:** FR-5, FR-6
- **Acceptance:**
  - I can add a birthday manually (name + date) or pull contacts from Google.
  - The event appears on my calendar on the right day, color-coded, and recurs yearly.
  - I get a reminder ahead of the day (configurable lead time).
  - I can create new events in Myworld that sync to my Google Calendar (not just read from it).
  - If I've already opened Myworld offline, today's events still appear from cache.

### US-6: Get reminded at the right moment
**As a** user, **I want to** be notified when a todo or event is due **so that** I don't have to keep checking the app.
- **Covers:** FR-6
- **Acceptance:**
  - Push notifications arrive on web PWA and Android for due todos and upcoming events.
  - If a notification is missed, the next app open surfaces an "overdue" badge on the dashboard tile.
  - Notification permission is requested with a plain-language prompt, not on first launch.

---

## Acceptance Criteria (per module)

> Criteria are testable. Each maps back to one or more FRs / NFRs. Used by Validate (Stage 6) as the checklist.

### AC-Auth
- AC-A1: OAuth round-trip completes on a fresh install with no console errors.
- AC-A2: Two different Google accounts on the same device show disjoint data sets (verified by attempting cross-user fetch with the other user's id).
- AC-A3: JWT expires; refresh extends the session without forcing re-login until the refresh token itself expires.
- AC-A4: Sign-out clears tokens from local storage, IndexedDB (PWA), and the native keychain (mobile).

### AC-Bento Grid
- AC-G1: At 375px viewport, tiles stack into a single column with no horizontal scroll.
- AC-G2: At 768px, tiles render in 2 columns; at 1280px, in 4 columns.
- AC-G3: All interactive tiles have a visible focus ring that meets 3:1 contrast.
- AC-G4: Tile content reflows gracefully when text length varies (no truncation of critical info).
- AC-G5: Dashboard route loads in under 3s on a simulated 4G profile.

### AC-Search
- AC-S1: Query of length ≥ 2 characters returns results in ≤ 500ms perceived latency.
- AC-S2: Empty query shows recent activity (last 5 todos / events).
- AC-S3: A result tap navigates to the item's detail view with the item in context (not just opened at the top).
- AC-S4: No-match shows an explicit empty state with a suggested action (e.g., "Create todo '<query>'").

### AC-ToDo
- AC-T1: CRUD operations on a todo succeed while offline; queued changes flush on reconnect without duplicates.
- AC-T2: Recurring todos generate the next instance at the configured interval, not all at once.
- AC-T3: Voice-created todos show the transcribed text, the detected date/time (if any), and let me edit before saving.
- AC-T4: A todo linked to a calendar event shows the link badge on both sides and unlinking removes it cleanly from both.

### AC-Calendar
- AC-C1: Events fetched from Google Calendar appear in Myworld within 1 sync cycle after auth.
- AC-C2: An event created in Myworld appears in Google Calendar within 1 sync cycle.
- AC-C3: Manual deletion in Google Calendar is reflected in Myworld on next sync; no ghost events linger.
- AC-C4: Birthday/anniversary events recur yearly without manual re-entry.
- AC-C5: Color coding is consistent across list and detail views (legend visible somewhere in the module).

### AC-Reminders / Notifications
- AC-R1: A reminder set for "now + 1 min" fires within 60s on a connected device.
- AC-R2: If permission is denied, the app shows an in-app banner instead of a system prompt storm.
- AC-R3: Reminders fire on PWA background (where supported) and on locked-screen mobile.

### AC-NFR (cross-cutting)
- AC-N1: Axe-core scan on the dashboard route returns 0 critical or serious violations.
- AC-N2: Lighthouse mobile performance score ≥ 80 on the dashboard route.
- AC-N3: All API errors return a typed error object (code + message); the UI shows a human-readable message and a retry affordance.
- AC-N4: All voice transcripts and journal-style content are stored encrypted at rest (per NFR-2 — applies to future phases, recorded here for traceability).

---

## Success Criteria (recap from product plan §Success Criteria)

> These are the launch gates, restated from the product plan for traceability. Used by Validate to declare MVP done.

- **SC-1:** MVP modules (Bento Grid + Search + ToDo + Calendar) are fully E2E working on web PWA and Android.
- **SC-2:** User can sign in with Gmail and see a personalized, empty-by-default dashboard on first run.
- **SC-3:** ToDo supports voice input and works offline.
- **SC-4:** Calendar syncs bidirectionally with Google Calendar.
- **SC-5:** Dashboard loads in under 3s on a simulated 4G mobile profile.
- **SC-6:** Zero hosting costs across all used services (verified via free-tier usage dashboards).
- **SC-7:** Each subsequent phase (Phase 2 Financial, Phase 3 News + Wellness, Phase 4 Spiritual, Phase 5 Documents + Info Lake) lands without breaking MVP modules.

---

## Traceability Matrix (FR ↔ US ↔ AC)

| FR | User Story | Acceptance Criteria |
|---|---|---|
| FR-1 | US-1 | AC-A1..A4 |
| FR-2 | US-2 | AC-G1..G5 |
| FR-3 | US-3 | AC-S1..S4 |
| FR-4 | US-4 | AC-T1..T4 |
| FR-5 | US-5 | AC-C1..C5 |
| FR-6 | US-6, US-4, US-5 | AC-R1..R3 |
| NFR-1 | US-2, US-3 | AC-G5, AC-S1, AC-N2 |
| NFR-2 | US-1 | AC-A1..A4, AC-N4 |
| NFR-3 | US-2 | AC-G3, AC-N1 |
| NFR-4 | US-4, US-5 | AC-T1, AC-C5 (cached) |
| NFR-5 | US-2, US-4 | AC-G1, AC-G2, AC-T1..T4 |

---

## Change Log

- 2026-08-23 — Review fixes: H-1 added Google People API for contact import. H-2 deferred iOS App Store to Phase 2, Android only for native MVP.
- 2026-08-23 (Design) — Implemented review fixes H-1 & H-2 in requirements.md: added Google People API scope to FR-5; updated NFR-5 to "Web PWA + Android for MVP, iOS in Phase 2"; removed iOS from SC-1.
- 2026-08-23 (Design) — Removed residual iOS mentions: Project Overview now says "Web PWA + Android"; US-6 acceptance now says "web PWA and Android".
