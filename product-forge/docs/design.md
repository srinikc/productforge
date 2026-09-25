# Design Spec — MyWorld MVP

> Stage 1 — Design. Source of truth: `docs/product-plan.md`. Companion: `docs/requirements.md`.

## 1. Design Direction (one-paragraph brief)

A **luxury dark-themed** personal command center rendered as a **focused, low-density Bento Grid**. Calm charcoal canvas, restrained emerald and blue accents, generous whitespace, and oversized tap targets. Every module reads as a single, intentional tile — never a wall of widgets. The interface should feel like a private console: precise, premium, and quiet, never busy. Visually inspired by high-end fintech dashboards and Apple-system app surfaces — not by generic SaaS templates.

Anchor phrases used through this document: **dark, calm, focused, premium, tactile**. If a design choice violates one of these, it is wrong.

---

## 2. Color Tokens

> All colors below are sourced from the product plan §Design Specification and the existing color stub. The six tokens in **bold** are the canonical palette confirmed by the user (2026-08-22). The remaining tokens are **derived** semantic or surface tokens required to actually use that palette in a real UI. Architect / Implement must consume these as design tokens; no ad-hoc hex values in code.

### 2.1 Core palette (user-confirmed)

| Token | Hex | Role |
|---|---|---|
| **bg** | **#0B0B0C** | **App background — Deep Charcoal.** Page-level canvas. |
| **surface** | **#141416** | **Card / tile background.** |
| **border** | **#27272A** | **Hairline dividers, tile borders, input borders.** |
| **emerald** | **#10B981** | **Primary accent for Health & Finance domains.** |
| **blue** | **#3B82F6** | **Primary accent for Productivity (Calendar, ToDo).** |
| **text** | **#FAFAFA** | **Primary text on dark surfaces.** |

### 2.2 Derived surface tokens

| Token | Hex | Used for |
|---|---|---|
| `surface-hover` | #1C1C1F | Tile hover state, selected list rows |
| `surface-sunken` | #08080A | Inset wells, code/text-input backgrounds |
| `overlay-scrim` | rgba(11,11,12,0.72) | Modal scrim, drawer backdrop |

### 2.3 Derived accent tokens

| Token | Hex | Used for |
|---|---|---|
| `purple` | #8B5CF6 | Spiritual module accent (Phase 4 — reserved) |
| `amber` | #F59E0B | Warning states, "due soon" badges |
| `red` | #EF4444 | Error states, destructive actions, overdue |
| `emerald-soft` | rgba(16,185,129,0.12) | Tinted backgrounds behind emerald text/icons |
| `blue-soft` | rgba(59,130,246,0.12) | Tinted backgrounds behind blue text/icons |

### 2.4 Text tokens

| Token | Hex | Used for |
|---|---|---|
| `text` (text-primary) | #FAFAFA | Headings, primary content |
| `text-secondary` | #A1A1AA | Metadata, timestamps, helper text |
| `text-muted` | #52525B | Disabled controls, placeholder text |
| `text-on-accent` | #0B0B0C | Text placed on emerald/blue fills |

### 2.5 Contrast (WCAG 2.1 AA — mandatory)

- `text` (#FAFAFA) on `bg` (#0B0B0C) → contrast ratio **~17.6:1** (AAA).
- `text-secondary` (#A1A1AA) on `bg` (#0B0B0C) → **~8.3:1** (AAA).
- `text-muted` (#52525B) on `bg` (#0B0B0C) → **~3.0:1** — **decoration only**, never used for required information.
- `text-on-accent` (#0B0B0C) on `emerald` (#10B981) → **~6.4:1** (AA Large + AA Normal).
- `text-on-accent` (#0B0B0C) on `blue` (#3B82F6) → **~5.1:1** (AA Normal).

**Rule:** if any component shows required information, it must use `text` or `text-secondary`. `text-muted` is reserved for non-essential labels.

---

## 3. Typography

> System-font stack only — zero font-network cost, full offline support, native feel on every platform. Product plan specifies luxury feel, not custom typography.

### 3.1 Font stack

- **Web:** `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- **iOS:** San Francisco (system)
- **Android:** Roboto (system)

### 3.2 Scale (rem-based; 1rem = 16px)

| Token | Size / Line | Weight | Use |
|---|---|---|---|
| `text-display` | 2.25rem / 2.5rem | 600 | Dashboard greeting (one per session, optional) |
| `text-h1` | 1.5rem / 2rem | 600 | Module detail titles |
| `text-h2` | 1.25rem / 1.75rem | 600 | Section headers within a module |
| `text-body` | 1rem / 1.5rem | 400 | Default content |
| `text-body-strong` | 1rem / 1.5rem | 600 | Emphasized body, list-item titles |
| `text-meta` | 0.875rem / 1.25rem | 500 | Timestamps, secondary metadata |
| `text-caption` | 0.75rem / 1rem | 500 | Tile labels, badges |
| `text-numeric` | 1.125rem / 1.5rem | 600, tabular-nums | Counts, dates, financial figures (when those modules land) |

### 3.3 Numeric alignment

All numbers (todo counts, dates, future financial figures) use `font-variant-numeric: tabular-nums` so columns line up cleanly across cards.

---

## 4. Spacing, Radius, Elevation

### 4.1 Spacing scale (4px base)

`4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 64`

Generous spacing is a luxury signal. Tile internal padding is **20px** minimum; module detail pages use **24–32px** between sections.

### 4.2 Radius

| Token | Value | Use |
|---|---|---|
| `radius-sm` | 6px | Tags, badges, small chips |
| `radius-md` | 10px | Inputs, buttons, list rows |
| `radius-lg` | 16px | Tiles, cards |
| `radius-xl` | 24px | Modal sheets, detail pages on mobile |
| `radius-pill` | 999px | Avatars, status pills |

### 4.3 Elevation (shadows on dark surfaces)

Dark UIs fail when they overuse shadow. Two soft elevation tokens only:

| Token | Value |
|---|---|
| `elev-0` | none — flush on `bg` |
| `elev-1` | `0 1px 0 0 #27272A` (hairline border only) |
| `elev-2` | `0 1px 0 0 #27272A, 0 8px 24px -12px rgba(0,0,0,0.6)` (modals, popovers) |

No drop shadows on tiles — tiles are separated by `border` and whitespace.

### 4.4 Borders

Use `1px solid border` on tiles, inputs, and dividers. Never thicker — thickness reads cheap on dark UI.

---

## 5. Motion

Restrained. No bouncy springs. Every interaction is **150–250ms, ease-out**, with the only exception being the page-level route transition which is **200ms cross-fade**.

| Motion | Duration | Curve | Use |
|---|---|---|---|
| `hover` | 150ms | ease-out | Tile scale 1.0 → 1.015, surface → surface-hover |
| `press` | 80ms | ease-in | Tile scale 1.0 → 0.99 |
| `modal-in` | 200ms | ease-out | fade + 8px slide-up |
| `modal-out` | 150ms | ease-in | fade + 4px slide-down |
| `route` | 200ms | ease-out | cross-fade between dashboard and module detail |
| `skeleton` | 1200ms loop | linear | placeholder shimmer (kept subtle) |

**`prefers-reduced-motion: reduce`** disables all of the above and replaces with instant transitions.

---

## 6. Iconography

- **Library:** Lucide React (web) / system icon set on mobile (architecture will decide native binding).
- **Stroke width:** 1.5px for 24px icons, 1.75px for 20px icons.
- **Color:** inherits `currentColor` — never hard-coded.
- **Sizing:** 16px (inline), 20px (control), 24px (tile-leading), 32px (empty-state).

The floating mic button (ToDo voice capture) uses a **filled** icon variant; everything else is outline. Outline icons read calmer.

---

## 7. Component Breakdown (MVP)

> Component names below are **design-system names** (what they are called in the spec). Implementer chooses file/folder names. No code in this document.

### 7.1 Primitives (single-responsibility, styled once)

| Component | Purpose | Notes |
|---|---|---|
| `Button` | Primary / secondary / ghost / destructive variants | Sizes: sm (32px), md (40px), lg (48px). Min tap target 44×44 on mobile per WCAG 2.5.5. |
| `IconButton` | Square icon-only button | Same tap-target rule. Always has `aria-label`. |
| `Input` | Single-line text field | Surface-sunken background, border on focus, never blue glow. |
| `Textarea` | Multi-line text | Same as Input; auto-grows to content. |
| `Select` | Dropdown | Native-feeling, keyboard navigable. |
| `Switch` | Boolean toggle | Emerald when on, surface-sunken when off. |
| `Checkbox` | Multi-select | Used in todo filters. |
| `Tag` | Small status / category pill | radius-pill. |
| `Avatar` | User / contact photo | Initials fallback when no photo. |
| `Divider` | Hairline | 1px `border`. |
| `Tooltip` | Hover/focus hint | Only on desktop; never on touch. |
| `Toast` | Transient feedback | Auto-dismiss in 4s; respects motion preference. |
| `Modal` | Centered dialog | Uses `elev-2`. Trap focus, ESC closes. |
| `Sheet` | Bottom sheet (mobile) / side panel (desktop) | For module detail views. |
| `Skeleton` | Loading placeholder | Matches final layout dimensions. |
| `EmptyState` | Zero-data illustration + CTA | Used everywhere there's no data yet. |

### 7.2 Composed (built from primitives)

| Component | Purpose | Built from |
|---|---|---|
| `Tile` | Bento-grid module card | `surface` + `border` + 20px padding + `radius-lg`; leading icon (24px), title (`text-h2`), 1–2 meta lines (`text-meta`), optional badge. |
| `TileGrid` | Responsive Bento container | CSS grid; reflow logic in §9. |
| `SearchBar` | Global search input | `Input` + leading search icon + trailing clear icon; 48px tall. |
| `TodoRow` | One todo in a list | Checkbox + title + meta line + optional link badge. |
| `EventChip` | One event on a day | Color dot + title + time. |
| `CalendarMonthView` | Month grid | Composed of `EventChip` per day cell. |
| `VoiceCaptureButton` | Floating mic (FAB) | `IconButton` with pulse-on-listening state; sits bottom-right on mobile, top-right inside ToDo detail on desktop. |
| `CommandPalette` | `Cmd/Ctrl-K` quick switcher | Modal containing `SearchBar` + recent items. |
| `OfflineBadge` | "You're offline" pill | `Tag` in `amber`. Top-of-screen, dismissible per session. |
| `NotificationPermissionPrompt` | In-app rationale | Banner above dashboard grid, dismissible per session. |

---

## 8. Information Architecture

### 8.1 Top-level routes (MVP)

```
/                     → Dashboard (Bento Grid)
/auth/signin          → Google OAuth entry
/auth/callback        → OAuth redirect target
/search               → Full-screen search (also reachable from Command Palette)
/todo                 → ToDo list
/todo/:id             → ToDo detail
/calendar             → Calendar month view
/calendar/event/:id   → Event detail
/settings             → Profile, notifications, account
/settings/voice       → Voice input model selection (per Q-7)
```

Future (Phase 2+, not designed here): `/news`, `/health`, `/finance`, `/spiritual`, `/documents`.

### 8.2 Navigation model

- **No persistent left sidebar.** Sidebars feel cluttered; the Bento tiles already provide primary navigation.
- **Bottom tab bar on mobile** with up to 5 destinations: Home, Search, ToDo, Calendar, Settings.
- **Top bar on desktop** with logo (text mark "MyWorld" in `text`), `SearchBar`, and Avatar.
- **Module detail** opens as a `Sheet` (mobile bottom sheet) or a centered modal (desktop) — never as a full page transition that loses dashboard context, except `/settings/*`.

### 8.3 Dashboard tile composition (MVP)

The dashboard always shows, in this order:

1. **Greeting tile** (`text-display`, optional — disabled by default to avoid noise; setting to enable in Phase 2).
2. **Universal Search tile** — `SearchBar` inside a tile; tap opens `/search`.
3. **ToDo tile** — shows today's open count, next 3 items previewed, "+" quick-add. Tap → `/todo`.
4. **Calendar tile** — today's events, "next upcoming" line, mini month strip. Tap → `/calendar`.
5. **Upcoming / Reminders tile** — chronological list of next 5 reminders across modules. Tap → opens detail.

For the MVP, that's the entire grid. Empty-state tiles (e.g., no todos yet) show an `EmptyState` with a single CTA ("Add your first todo") — never a blank panel.

### 8.4 Sign-in flow (before dashboard exists)

`/auth/signin` is a single centered card on `bg` containing:

- Logo + tagline.
- "Continue with Google" primary button (blue).
- A muted one-liner about data isolation per product plan Q-3.

There is no other content on this screen.

---

## 9. Layout & Responsive Behavior

### 9.1 Breakpoints

| Name | min-width | Tile columns |
|---|---|---|
| `phone` | 0–639px | 1 |
| `tablet-portrait` | 640–1023px | 2 |
| `tablet-landscape` | 1024–1279px | 3 |
| `desktop` | 1280px+ | 4 |

### 9.2 Bento Grid reflow

- **Phone:** single column, tiles full-width, 16px gap between tiles.
- **Tablet portrait:** 2 columns; first row can be a wide tile (Search spans both cols) for a hero feel.
- **Tablet landscape / desktop:** 3–4 columns; Search tile always spans 2 cols in the top row; tile aspect ratio between 4:3 and 16:9, never taller than 1:1 to avoid endless scrolling.
- **Gaps:** 16px on phone, 20px on tablet, 24px on desktop.

### 9.3 Tile sizes

Three size classes — used asymmetrically, never all the same:

| Class | Spans | Use (MVP) |
|---|---|---|
| `tile-md` | 1 col × 1 row | Upcoming / Reminders |
| `tile-lg` | 1 col × 1 row, taller content | ToDo, Calendar |
| `tile-wide` | 2 cols × 1 row | Search |

The grid intentionally has one wide tile (Search) to break monotony — a "luxury Bento" signature.

### 9.4 Touch targets

Every actionable element has a **44×44 px** minimum hit area on mobile (WCAG 2.5.5). Visual size may be smaller; padding extends the hit area.

### 9.5 Grid system (added 2026-08-23)

> Underlying CSS grid that the Bento tiles in §9.2 snap into. This is the **scaffolding** the tile spans in §9.3 are expressed in; the 1/2/3/4 column reflow in §9.2 is the resulting *visible* column count derived from this scaffold.

Grid update: 12-column layout on desktop (1280px+), 8-column on tablet (1024-1279px), 4-column on phone (0-639px).

- **Desktop (1280px+):** 12-column scaffold. Page max-width is constrained so columns don't stretch to infinity on ultrawide — at >= 1440px, the grid is capped and centered with the same 24px gutter; columns beyond the cap remain in the scaffold as off-canvas whitespace, not as additional tile room.
- **Tablet (1024–1279px):** 8-column scaffold. All tile sizes in §9.3 re-express in 8-column units (e.g., `tile-wide` = 8 cols, `tile-md`/`tile-lg` = 4 cols).
- **Phone (0–639px):** 4-column scaffold. `tile-wide` spans all 4 cols; `tile-md` / `tile-lg` span all 4 cols full-width (effectively the 1-column reflow in §9.2, but expressed against the 4-col scaffold for consistency).
- **Gutter:** 16px on phone, 20px on tablet, 24px on desktop (unchanged from §9.2).
- **Why 12/8/4 and not 12/6/4:** 8 columns on tablet gives `tile-wide` a clean 1:1 (full row) and `tile-md` a clean 1:2 (half row), which matches the 2-column reflow in §9.2 without fractional spans. 6 columns would force odd fractions on half-width tiles.
- **Architect's responsibility:** translate this scaffold into the implementation's actual grid container (CSS Grid `grid-template-columns`, Tailwind config, etc.). The design only specifies column counts and breakpoints.

---

## 10. UX Direction by Module (MVP)

### 10.1 ToDo

- **Default view:** today's open todos, sorted by due time, then priority.
- **Tabs above list:** Today · Week · Month · Year · All.
- **Quick-add row** always visible at top of list: `Input` + leading mic + send button.
- **Voice capture:** tapping mic enters listening state (pulse on mic icon, faint emerald ring around FAB). Transcript appears inline; on stop, the parsed title + detected date/time appear with edit affordance before save.
- **Recurring indicator:** tiny loop icon next to title; expanded detail shows schedule.
- **Linking:** from a todo detail, "Link to event" opens event picker filtered to current week.
- **Empty state:** "Nothing on your plate. Add a task or try voice." + mic CTA.

### 10.2 Calendar

- **Default view:** month grid with 3 events visible per day cell; "+N more" link opens a day drawer.
- **Color coding:** birthdays/anniversaries = `emerald`, work events = `blue`, holidays (from Google) = neutral `text-secondary`, custom = user-chosen from a fixed palette (matches the design tokens, never free-form picker).
- **Create:** tap a day → bottom sheet (mobile) or side panel (desktop) with title, time, recurrence, color, reminder lead.
- **Sync indicator:** subtle `text-meta` line at top of view: "Synced with Google · 2 min ago". On sync failure, switches to amber pill "Sync failed · retry".
- **Offline:** "Last synced: X ago" appears in place of "Synced" with amber accent.

### 10.3 Universal Search

- **Input** on dashboard is the same component as `/search` page.
- **Results grouped:** Todos · Events · (future: News, etc.).
- **Empty state:** recent activity (last 5 items) plus a one-line hint ("Type to search across your world").
- **Keyboard:** `Cmd/Ctrl-K` opens the command palette from anywhere in the app.

### 10.4 Notifications

- First notification is triggered after the user creates their first todo with a reminder — *not* on first launch (per acceptance criterion US-6).
- Rationale copy: "We'll remind you about todos and events. You can change this anytime in Settings."
- If denied, an `OfflineBadge`-style banner appears on dashboard with a "Turn on in Settings" link.

---

## 11. Data Concepts (UX-level)

> These are the user-facing concepts, not the database schema. Architect owns the schema; this section ensures the design doesn't promise what the data can't support.

| Concept | User meaning | Notes |
|---|---|---|
| **Todo** | A task with optional due date, recurrence, and links. | One todo has at most one linked event. |
| **Event** | A calendar entry, either user-created or synced from Google. | Has color, start/end, optional recurrence. |
| **Reminder** | A "fire at time T" instruction bound to a Todo or Event. | UX treats this as a property of the bound item, not a standalone object. |
| **Search Result** | A pointer to a Todo or Event. | Never duplicates the source data; tapping opens the source. |
| **Profile** | A signed-in user's data scope. | Multiple Google accounts on one device show disjoint Profiles (per product plan Q-3). |
| **Offline Cache** | The locally-readable copy of recently-viewed data. | Used by ToDo and Calendar when offline; surfaced via "Last synced" labels. |

---

## 12. User Flows (MVP)

### 12.1 First-time sign-in

```
User opens app
  → lands on /auth/signin (cold-start, no token)
  → taps "Continue with Google"
  → OAuth popup → consent → redirect to /auth/callback
  → backend exchanges code for tokens, issues JWT
  → redirect to /
  → dashboard renders with empty-state tiles
  → Notification permission is NOT requested here
  → user taps ToDo tile → sees empty state → adds first todo with reminder
  → at that moment, app requests notification permission with rationale
```

### 12.2 Create a todo by voice

```
User on dashboard or /todo
  → taps VoiceCaptureButton (FAB)
  → button enters listening state (pulse + emerald ring)
  → speaks: "Call Mom tomorrow at 6pm"
  → app streams audio to voice backend
  → transcript returned; local parser extracts:
       title: "Call Mom"
       dueDate: tomorrow
       dueTime: 18:00
  → preview sheet appears: editable title + date + time + Save
  → user confirms → todo saved → list refreshes
  → on failure (see §13) → preview sheet shows raw transcript + warning + manual save
```

### 12.3 Sync Google Calendar

```
User on /calendar
  → on first visit, app requests Google Calendar scope (separate consent from sign-in)
  → backend performs initial sync; UI shows skeleton state
  → events render; "Synced · just now" appears
  → background worker re-syncs every N minutes (architect decides N; UX requires a visible status)
  → user creates event in Myworld → app POSTs to backend → backend writes to Google
  → "Synced · 2 min ago" updates
  → if write fails: toast appears, event is still saved locally with a "Sync pending" badge
```

### 12.4 Search → navigate to item

```
User presses Cmd/Ctrl-K (or taps Search tile)
  → CommandPalette opens
  → types "mom"
  → results show: 2 todos + 1 event, grouped
  → user taps "Call Mom" todo
  → palette closes, app routes to /todo/:id with that item in focus
```

### 12.5 Offline todo creation

```
User on /todo, network drops
  → OfflineBadge appears at top
  → user creates a todo via input
  → todo saves locally with "pending sync" tag (red dot)
  → network returns
  → app flushes queue, tags clear, "Synced" status updates
  → if sync fails after 3 retries: todo gets an "Sync failed" badge with a manual retry action
```

---

## 13. Edge Cases

> Each case names the situation, the design's response, and why. These are design-side resolutions; architect owns the implementation strategy.

| # | Situation | Design response |
|---|---|---|
| E-1 | User signs in for the first time; no data exists. | All tiles show `EmptyState` with one CTA each. No "Add your first X" gate that blocks the dashboard. |
| E-2 | User denies notification permission. | Dashboard shows persistent but dismissible amber banner linking to Settings. App remains fully usable without notifications. |
| E-3 | User revokes Google Calendar permission later. | `/calendar` shows an empty state with "Reconnect Google Calendar" CTA. Existing local events remain visible. |
| E-4 | Two devices edit the same todo. | Last-write-wins by `updatedAt`, with a toast on the losing device: "Updated from another device" + undo (re-fetches remote). |
| E-5 | Voice transcript is unintelligible. | Preview sheet shows raw transcript, no extracted date/time, and an amber warning "We couldn't catch that — save anyway?" |
| E-6 | Voice backend is unreachable. | FAB shows transient failure state; toast "Voice unavailable right now"; input still works. |
| E-7 | Network drops mid-sync. | OfflineBadge appears; last-known data remains visible; queued writes flush on reconnect. |
| E-8 | Google Calendar returns rate-limit / 503. | Sync indicator turns amber with "Retry in a moment"; reads still work via cache. |
| E-9 | User opens app with very large todo list (1000+). | ToDo view paginates (UX requires 50/page); Search handles full set. No infinite scroll on lists. |
| E-10 | User opens app on a device with no microphone (desktop without mic). | FAB is hidden; quick-add row is `Input` only. |
| E-11 | User's screen reader is active. | All tiles announce themselves with role + name; the FAB exposes "Add todo by voice"; motion is suppressed; tile focus rings visible. |
| E-12 | User on slow 3G connection. | Skeleton state appears within 100ms; tiles render progressively; the Search tile appears first (it can render with zero data). |
| E-13 | User with system dark mode disabled. | This app is dark-only; system preference is ignored. (Documented because the product plan specifies luxury dark theme.) |
| E-14 | Date/time interpretation across timezones. | All UI shows the user's local timezone; recurring events anchor to local midnight. (Architecture owns the storage representation.) |
| E-15 | OAuth callback with stale code. | App shows sign-in screen with error toast "Sign-in expired — please try again." No infinite spinner. |

---

## 14. Error Handling (UX)

Every recoverable error in the app resolves to one of three patterns. Every screen must pick exactly one; mixed patterns confuse users.

| Pattern | When to use | Visual |
|---|---|---|
| **Inline error** | Field-level validation, form submit failure. | `text-meta` in `red`, directly under the field; field border switches to `red`. |
| **Empty state with action** | Module-level failure where user can retry or take an alternate action (reconnect Google, retry voice). | `EmptyState` with red icon, descriptive copy, one CTA. |
| **Toast** | Transient failure where the user can continue (sync delayed, voice failed). | Bottom-positioned toast, `surface` + `border`, auto-dismiss 4s; action button if applicable. |

**Never** show a full-screen red error overlay for recoverable errors. **Always** log the technical detail (architect decides where) but show a human-readable message.

### 14.1 Required error copy (UX strings)

These are the canonical error messages. Implementer may add specifics but must not change tone.

- "Something went wrong. Try again."
- "You're offline. We'll sync when you're back."
- "We couldn't reach the server. Try again in a moment."
- "Sign-in expired. Please sign in again."
- "Voice isn't available right now. You can still type your task."
- "We couldn't catch that. Save anyway or try again."

### 14.2 Accessibility on errors

- Toasts use `role="status"` for info, `role="alert"` for blocking issues.
- Inline errors are tied to the field via `aria-describedby`.
- Focus is moved to the first error on form submission failure.

---

## 15. Motion & Micro-interactions (per module)

| Trigger | Effect |
|---|---|
| Hover tile | Tile background → `surface-hover`, scale 1.015, 150ms ease-out. |
| Press tile | Scale 0.99, 80ms ease-in; haptic feedback on supported mobile devices. |
| Open module detail | Sheet slides up 8px with fade-in, 200ms ease-out. |
| Complete a todo | Checkbox fills emerald; row strikes through and fades to `text-secondary` over 200ms. |
| Voice listening | FAB pulse: outer ring scales 1.0 → 1.4, opacity 0.6 → 0, looping at 1200ms. |
| Receive notification toast | Slide in from bottom 16px, 200ms ease-out. |
| Sync success | "Synced X ago" text fade-update only — no icon animation. |
| Reduced-motion | All of the above replaced with instant state changes; FAB pulse removed. |

---

## 16. Accessibility (WCAG 2.1 AA — binding)

| Requirement | Implementation |
|---|---|
| Color contrast | Enforced by token table §2.5. |
| Keyboard nav | All interactive elements reachable; visible focus ring (`2px solid blue` + 2px offset). |
| Tap targets | ≥ 44×44 px on mobile (WCAG 2.5.5). |
| Screen reader | Semantic landmarks (`<main>`, `<nav>`), `aria-label` on icon buttons, live regions for toasts. |
| Motion | `prefers-reduced-motion: reduce` honored globally. |
| Text spacing | No fixed heights on text containers — content reflows under user-applied spacing. |
| Language | `lang="en"` at root (architect may add `lang` switching in Phase 2+). |
| Forms | Labels above fields; errors via `aria-describedby`. |

---

## 17. Open Questions

> Items the product plan did not specify or specified ambiguously. These are **flagged for the user** — do not silently resolve. Each must be answered before Implement can begin, or accepted as "decide later" by the user.

| # | Question | Why it matters | Default if user defers |
|---|---|---|---|
| OQ-1 | **Tile ordering on first run** — fixed (Search → ToDo → Calendar → Upcoming) or personalized? | Affects whether we ship a personalization layer in MVP. | Fixed order. |
| OQ-2 | **Calendar default tab on mobile** — month, week, or list? | Affects primary mobile interaction. | Month (matches desktop). |
| OQ-3 | **Quick-add entry point on mobile** — FAB only, or also inline above list? | Affects discoverability vs. cleanliness. | FAB only on mobile, inline on desktop. |
| OQ-4 | **Voice model selection** — Whisper or Vosk (product plan leaves this open)? | Affects offline capability, accuracy, and bundle size. | Vosk on-device for MVP (better offline); Whisper as Phase 2 upgrade path. Architect confirms. |
| OQ-5 | **Recurring todo editing** — does editing one instance affect all, or only future? | Standard calendar UX expects "only this / this and future / all". | "Only this / This and future / All" — same as Google Calendar. |
| OQ-6 | **Birthday/anniversary lead time default** — 1 day, 3 days, 1 week? | Affects notification volume. | 1 day at 9am local. User can change per event. |
| OQ-7 | **Multi-profile switching** — switcher in avatar menu, or separate sign-out? | Product plan Q-3 says multi-profile but doesn't say how switching works. | Avatar menu → "Switch profile" signs out and re-runs OAuth (acceptable for MVP). |
| OQ-8 | **Greeting tile** — include in MVP or defer? | Adds personality but reduces tile density. | Deferred — not in MVP grid. |
| OQ-9 | **Calendar color palette size** — how many fixed colors are user-selectable? | Affects event UX and code complexity. | 6 fixed colors mapped to design tokens; no custom color picker. |
| OQ-10 | **Empty-state illustration style** — abstract shapes, simple line icons, or none? | Affects whether we need an illustration set. | None — text + icon only. Keeps dependency surface small for MVP. |

---

## 18. Out of Scope (design — for traceability)

Per the product plan §Non-Goals and §Goals, the following are **explicitly not designed** in this document:

- Financial dashboard visuals (Phase 2).
- News module layouts and feed density (Phase 3).
- Wellness / diet-planner UI (Phase 3).
- Spiritual journal and library UI (Phase 4).
- Documents explorer / Info Lake link-outs (Phase 5).
- DPDP consent flows (Phase 2, per product plan Q-9).
- Custom theming / light mode (product plan specifies luxury dark).
- Native desktop apps (PWA covers desktop).
- Real-time multi-user collaboration (non-goal).

---

## 19. Cross-references

- **Source plan:** `docs/product-plan.md` §Design Specification, §Module Specifications, §Stakeholder Questions & Answers.
- **Requirements:** `docs/requirements.md` (FR-2, FR-3, FR-4, FR-5, FR-6, NFR-1, NFR-3, NFR-5).
- **Open items forwarded:** `docs/todo.md` (design reference scraping, RSS feed finalization).
- **Inputs needed:** `docs/input_needed.md` (mymoney API — not used in MVP per product plan Q-8).
- **Next stage:** Architect — read this file + `requirements.md`; produce `docs/architecture.md`.

---

## 20. Festival Data Source (added 2026-08-23)

> Stage 2 revision. Source of truth remains `docs/product-plan.md`. Flagged for Architect and Implement.

**Festival data source:** Indian public holidays from Google Calendar API (Indian Holidays calendar), plus manual entry for regional festivals.

- **Indian public holidays** — sourced via Google Calendar API from the public `Indian Holidays` calendar (Google's `en.indian#holiday@group.v.calendar.google.com` feed). Read-only; no write-back. Available to any signed-in user without an additional consent scope beyond the existing Google sign-in.
- **Regional / local festivals** — user-entered. Entry surface: Calendar → "Add festival" with name, date, recurrence (None / Yearly), optional color (from the fixed palette per OQ-9), and optional reminder lead (per OQ-6).
- **Rendering:** festivals render on the Calendar month grid using the neutral `text-secondary` color per §10.2 (same treatment as Google-sourced holidays), so they are visually distinguishable from personal/work events (emerald / blue).
- **Sync behavior:** the Indian Holidays feed refreshes on the same cadence as the user's personal Google Calendar sync (architect decides N); regional festivals are stored locally and sync like any other user-created event.
- **Edge cases:**
  - If Google sign-in is unavailable or revoked (per E-3), Indian Holidays do not render, but user-entered regional festivals remain visible.
  - Duplicate detection: if a user enters a regional festival on the same date as an Indian public holiday from Google, both render — the design does not auto-merge. Hide-via-context-action is deferred to a later iteration.
  - Offline (per E-7): the most recent Indian Holidays snapshot remains visible via the same offline cache that serves the Calendar; user-entered regional festivals are always available locally.
- **Open questions forwarded:** none new — this addition does not introduce design ambiguities beyond those already captured in §17.
