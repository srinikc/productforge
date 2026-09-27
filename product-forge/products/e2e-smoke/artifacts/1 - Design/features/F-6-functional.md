## F-6: Dark Mode

> **Feature id:** F-6 · **Owned global id ranges:** FR-126..FR-150, NFR-76..NFR-90, US-76..US-90 · **Local ids** (BR-, EC-, AC-, API-, DM-, OQ-) are scoped to this feature and numbered sequentially from 1. References to F-1 / F-2 / F-3 / F-4 / F-5 ids are plain text only; this section never re-defines them.

### Requirements

**Functional Requirements (global ids — owned range FR-126..FR-150)**

| ID | Name | Requirement |
|---|---|---|
| FR-126 | Theme preference selection | The user can choose exactly one of `light`, `dark`, or `system` as the active theme preference. The preference governs the whole product — no per-screen or per-widget themes. |
| FR-127 | System preference following | While the preference is `system`, the product resolves the effective theme from the host OS/browser colour-scheme signal and re-resolves live when that signal changes, with no reload and no user action. |
| FR-128 | Preference persistence | The chosen preference is persisted and re-applied on the next session on the same device, including after sign-out/sign-in, hard reload, and full app restart. |
| FR-129 | Immediate application | Changing the preference or the system signal re-themes every already-rendered surface by the next paint. A manual reload is never required and never prompted for. |
| FR-130 | Full-surface coverage | Every screen and every state (empty, loading, error, success, partial) of F-1 through F-5 — including modals, sheets, toasts, tooltips, menus, skeletons, and overlays — renders from theme tokens. No shipped surface retains a hard-coded light-only colour. |
| FR-131 | No flash of incorrect theme | The effective theme is resolved and applied before first paint. A user whose stored preference is `dark` never sees a light frame on cold load or hard reload. |
| FR-132 | Per-device override | A user may hold a different theme preference on different devices; `system` is evaluated independently per device. |
| FR-133 | Scheduled switching | The user can define a dark window — explicit start/end local times, or "follow sunset/sunrise" for the device's location — that overrides the base preference while the window is active. The schedule can be enabled, disabled, and edited at any time. |
| FR-134 | Theme-aware assets | Illustrations, empty-state art, iconography, avatar fallbacks, and any raster art ship a dark variant or are specified as themeable vectors. No light-baked art is placed on a dark surface. |
| FR-135 | Data-visualisation adaptation | Charts in F-4 Progress Analytics use a dark-safe categorical palette with theme-appropriate gridline, axis, and label colours; series remain distinguishable in both themes and never rely on colour alone. |
| FR-136 | Rich and third-party content | User-authored and embedded content (notes, links, code blocks, webhook payload previews, F-5 integration previews, third-party frames) is legible in both themes, with a documented fallback for content that supplies its own light colours. |
| FR-137 | Accessible toggle affordance | A theme control is reachable from settings and from the global quick-access/command surface on every primary screen. The control always reflects the current *effective* theme, not merely the stored preference. |
| FR-138 | Keyboard and shortcut parity | The theme can be changed without a pointer; the shortcut is discoverable in the product's shortcut/help listing alongside the actions of F-2 and F-3. |
| FR-139 | High-contrast and reduced-transparency variants | Dark mode offers a high-contrast dark variant that raises contrast beyond the base dark palette, and honours OS "reduce transparency" and "reduce motion" signals for any theme-transition animation. |
| FR-140 | Print and export | Printing and non-interactive export of any view produce a legible light output regardless of the on-screen theme, unless the user explicitly requests a themed export. |
| FR-141 | Theme-aware notifications | In-app notifications, banners, and badge colours are theme-aware; outbound email and push notification rendering uses a fixed light-safe palette that stays legible in dark mail clients and OS notification centres. |
| FR-142 | Native chrome synchronisation | Where the host platform allows it, surrounding chrome (browser `theme-color`, status bar, splash background) is set to the current effective theme and updated on every change. |
| FR-143 | Reset to default | The user can reset the theme preference to the shipped default (`system`) in one action; the reset takes effect immediately and clears any session-scoped override. |

**Non-Functional Requirements (global ids — owned range NFR-76..NFR-90)**

| ID | Area | Target / Measurement |
|---|---|---|
| NFR-76 | Performance — switch latency | Theme change is visible within 100 ms of the triggering input on the reference device class (mid-range mobile, 4× CPU throttle). Measured with a recorded input-to-paint trace. |
| NFR-77 | Performance — first paint | 100% of cold loads and hard reloads paint the correct effective theme. Wrong-theme frames = 0, verified by frame-by-frame screenshot capture of the load sequence. |
| NFR-78 | Accessibility — contrast | WCAG 2.1 AA in dark mode: text ≥ 4.5:1 (normal) / ≥ 3:1 (large), non-text UI ≥ 3:1 against adjacent colours. High-contrast dark variant targets ≥ 7:1 for body text. Verified by automated contrast audit plus manual spot checks. |
| NFR-79 | Performance — rendering cost | Entering or leaving dark mode produces no long task > 50 ms and contributes ≤ 0.01 to Cumulative Layout Shift. Steady-state dark mode shows no continuous repaint and no idle CPU above the light-mode baseline. |
| NFR-80 | Performance — startup and payload | Theme resolution adds no blocking network round-trip before first paint; the resolved theme and its token set are available from local assets/state. |
| NFR-81 | Availability — offline and degraded | Selection, persistence, scheduling, and switching all work with zero network connectivity. No theme state is lost or reverted when connectivity returns. |
| NFR-82 | Scalability — coverage | Theming propagates exclusively through tokens: adding a new screen or component requires no per-theme branch. Unthemed-surface count is measurable and driven to zero. |
| NFR-83 | Security | Theme preference is treated as an untrusted enum. No preference value, schedule expression, location input, or custom colour reaches the DOM/CSS without allow-list validation. Theming introduces no new injection sink and no new script-execution path. |
| NFR-84 | Data and residency | Theme preference and schedule are device-local user settings. If synced, only the enum and schedule are stored — never content — in the region required by the product's data-residency policy. |
| NFR-85 | Consistency — cross-device | When preference sync is enabled, convergence across a user's devices is eventual within one foreground sync cycle, with last-write-wins per device and no silent loss of any device's local override. |
| NFR-86 | Deployment and environment | Light and dark token sets are identical across local, staging, and production. No environment may ship a partial or stale token set; token-set version is reported in diagnostics. |
| NFR-87 | Auditability of coverage | A build-time check reports themed-token coverage for every shipped component. The release gate fails when any component references a raw colour literal. |
| NFR-88 | Assistive technology | Effective theme and theme changes are exposed with correct semantics; a change is announced to screen readers without moving focus. |
| NFR-89 | Internationalisation | Dark-mode assets and palettes do not break RTL layouts, and no asset contains baked-in text. Locale-specific date/time formatting in the schedule follows the user's locale. |
| NFR-90 | Observability | The distribution of resolved themes and the count of detected wrong-theme frames are measurable in aggregate. Telemetry captures no user content, only theme state, resolution source, and app version. |

**User Stories (global ids — owned range US-76..US-90)**

| ID | Story |
|---|---|
| US-76 | As a late-night worker, I want a dark theme so that the screen does not glare and my eyes stay comfortable in a dim room. |
| US-77 | As a user whose OS already follows my routine, I want the app to follow my system theme so that I do not manage the same setting twice. |
| US-78 | As a returning user, I want my theme choice remembered so that I do not re-set it every session. |
| US-79 | As a keyboard-first user, I want to toggle the theme without leaving the keyboard so that I stay in flow. |
| US-80 | As a low-vision user, I want a high-contrast dark option so that I can read comfortably without switching to light. |
| US-81 | As a user opening the app at night, I want the theme applied instantly with no white flash so that launch is not painful. |
| US-82 | As a user with a fixed evening routine, I want the app to switch to dark automatically at a time I choose so that I never have to think about it. |
| US-83 | As a user who shares screenshots and exports, I want charts and text to stay readable in whichever theme I use and in the files I hand to others. |

### Behaviour

1. **Resolution.** The effective theme is computed from a strict precedence chain, highest first: (a) an in-session temporary override, (b) an active scheduled dark window, (c) the stored user preference, (d) the OS colour-scheme signal when the preference is `system`, (e) the shipped default (effectively light). The resolution source is always knowable and is exposed to the UI so the toggle can show the effective theme.
2. **Applied before paint.** On load, the stored preference and schedule are read from local state synchronously, the effective theme is resolved, and the correct token set is applied before the first paint (FR-131, NFR-77).
3. **Live re-resolution.** A change to any input in the chain — user toggle, OS signal, schedule boundary crossing, device timezone change — re-resolves the theme and re-applies it within one paint (FR-127, FR-129, NFR-76).
4. **Token-mediated theming.** Every surface consumes semantic tokens (surface, surface-raised, border, text-primary, text-muted, accent, status-*, chart-*). Switching themes swaps the token set; it never rewrites component styles. This is what makes FR-130 and NFR-82 hold for surfaces belonging to F-1 through F-5 as well as F-6 itself.
5. **Non-destructive switching.** A theme change never interrupts an active focus session or its timer (F-3), never clears a partially typed quick-add input (F-2), never loses a pinned/override state (F-1), never resets chart zoom or filter state (F-4), and never cancels an in-flight integration sync or connection handshake (F-5).
6. **Assets.** Icons and illustrations are either single-colour vectors tinted by token, or they ship an explicit dark variant selected by the active token set. No component recolours a raster asset with a CSS filter as its only strategy.
7. **Scheduling.** When the schedule is enabled, the dark window is evaluated against the device's local time. "Sunset/sunrise" mode resolves to local sun times for the device's location/timezone; if no location is available the user is offered explicit times (see Edge cases EC-5). Crossing midnight is a supported, normal window.
8. **Native chrome.** On every effective-theme change the browser `theme-color`, status bar, and splash background are updated (FR-142); on platforms without support these calls are silent no-ops.
9. **Outbound surfaces.** In-app notifications follow the theme; email and push rendering use a fixed light-safe palette with sufficient contrast in dark clients (FR-141).
10. **Diagnostics.** Token-set version, resolution source, and any theme failure are recorded locally and available to the user-facing diagnostics view alongside the state of F-5 connections.

### Business rules

- **BR-1 — One preference.** Exactly one preference value is active per device: `light`, `dark`, or `system`. Custom colour pickers, per-screen themes, and per-project themes are out of scope for this feature.
- **BR-2 — Precedence is fixed.** The chain in Behaviour §1 is the only permitted resolution order. No feature may inject a theme value outside it.
- **BR-3 — Toggle during a scheduled window.** An explicit toggle while a schedule window is active is treated as a session-scoped temporary override. It does not delete or edit the schedule, and it is cleared at the next window boundary or at the start of the next session.
- **BR-4 — `system` always resolves.** If the OS signal is unavailable, unreadable, or reports an unrecognised value, `system` resolves to light. The product is never left unstyled or in an undefined theme.
- **BR-5 — Sync never clobbers silently.** With preference sync enabled, a device keeps its local override until the user explicitly chooses "apply to all devices". A remote value never overwrites a device's local override without that explicit action.
- **BR-6 — Theme changes never block work.** A theme change is non-blocking and non-destructive with respect to every operation in F-1..F-5 (see Behaviour §5).
- **BR-7 — Content is invariant.** Dark mode changes colour, elevation, and asset variant only. It does not change wording, data, ordering, or information density. A user switching themes must not lose or gain information.
- **BR-8 — Status colour semantics are preserved.** The colours that signal overdue/done/blocked (F-1), streak and at-risk state (F-4), and connection state (F-5) retain their meaning and remain distinguishable in dark mode. Colour is never the sole carrier of a status; an icon or label accompanies it.
- **BR-9 — Tokens are the only colour source.** Feature components reference semantic tokens. A raw colour literal in a feature component is a defect, not a stylistic choice (enforced by NFR-87).
- **BR-10 — Exports default to light.** Print and non-interactive export render from a deterministic light palette unless the user explicitly requests themed output. The on-screen theme is never silently baked into a file the user shares.
- **BR-11 — Third-party content degrades, not disappears.** Embedded content that only supports light mode is placed in a labelled light "island" container rather than forced to dark or hidden.

### Validation

- **Preference value.** Must be one of the allow-listed enums (`light`, `dark`, `system`). Any other value is rejected in whole, logged, and the effective theme falls back to the last known-good value, then to `system`.
- **Schedule times.** Start and end must be valid local times. A zero-length window (start equal to end) is rejected as invalid. Windows crossing midnight are accepted and normalised. An inverted window that is not a midnight crossing is rejected with a field-level error.
- **Location for sun-based scheduling.** "Sunset/sunrise" requires a resolvable location or timezone. If location is unavailable or denied, the setting does not silently fail — the user is prompted to supply explicit times, and the schedule is left disabled until resolved.
- **Sync payload.** A sync payload carrying an unknown preference value or an out-of-range schedule is rejected in whole. The local device retains its current setting and reports a passive sync-status item.
- **Token set integrity.** If a token set is missing, malformed, or incomplete, it is not applied at all. The last known-good set is used and the failure is surfaced in diagnostics (NFR-86).
- **Asset variant resolution.** If a dark asset variant referenced by a component does not exist, the build fails by name rather than shipping a light asset on a dark surface.

### Edge cases

- **EC-1 — OS theme changes while backgrounded.** On resume, the effective theme matches the OS with no visible flash or intermediate light frame.
- **EC-2 — OS theme changes mid-focus-session.** The active F-3 session, its timer, and its paused/running state are unaffected; only the palette changes.
- **EC-3 — Stored preference conflicts with OS.** The stored preference wins, deterministically. There is no oscillation and no "flip-flop" as the OS signal is re-read.
- **EC-4 — Timezone or DST change during an active window.** The window is recomputed from local time; no duplicate or missed boundary persists beyond one minute.
- **EC-5 — Sun times unavailable.** Offline, permission denied, or polar day/night. The schedule falls back to explicit times if configured, otherwise to the base preference, and the user is informed exactly once.
- **EC-6 — Two devices with different preferences and sync on.** Each device keeps its own preference until the user explicitly pushes one to all devices (BR-5).
- **EC-7 — User content with inline light colours.** Pasted HTML or hex colours are constrained by a legibility rule so text never becomes invisible; the original value is preserved in the underlying data, not rewritten.
- **EC-8 — Embedded frame with no dark support.** Rendered inside a labelled light island container (BR-11); surrounding surfaces remain dark.
- **EC-9 — Dark-transparent logos on dark surfaces.** A dark asset variant is used, or a subtle backing plate is applied so the mark stays visible.
- **EC-10 — Print/export captured mid-transition.** Exports always render from a deterministic palette; transition timing cannot leak into output.
- **EC-11 — First-ever load, no stored preference, no OS signal.** Resolves to light with no flash and no prompt.
- **EC-12 — Local storage unavailable.** Private browsing or quota exceeded. The theme applies for the session, the user receives one non-blocking notice that persistence is off, and no error loop occurs.
- **EC-13 — Theme toggled while an optimistic update is in flight.** A quick-add commit (F-2) or focus-timer state change (F-3) is neither lost nor duplicated.
- **EC-14 — Large F-4 dataset re-themed mid-render.** Charts re-render with the new palette without losing zoom, scroll position, or applied filters.
- **EC-15 — High-contrast dark combined with reduce-transparency.** Both preferences are honoured together; neither silently cancels the other.
- **EC-16 — Rapid repeated toggling.** Fast successive toggles settle on the last requested value with no queueing, flicker, or stuck intermediate state.

### Error handling

- **Token set failure.** Fall back to the last known-good set, record the failure in diagnostics, and show a passive notice. Never render unstyled content and never block the app.
- **Preference write failure.** Keep the theme for the current session, show exactly one non-blocking notice, retry on next launch, and do not repeat the notice once acknowledged.
- **Sync failure or conflict.** The device-local preference is authoritative for that device. Sync errors surface as a passive status item, never as a blocking modal, and never revert the on-screen theme.
- **Schedule resolution failure.** The schedule is disabled for that evaluation, the base preference applies, and the user is informed once with the reason (no location, invalid window, or unreadable clock).
- **Unsupported native chrome call.** Silent no-op. Content theming is unaffected and no error is surfaced to the user.
- **Asset variant missing at runtime.** Fall back to the light asset on a neutral backing plate so nothing becomes invisible, and raise a build/telemetry defect.
- **General rule.** No theming failure may ever block task capture (F-2), focus sessions (F-3), analytics (F-4), or integration sync (F-5). Theme degrades; functionality does not.
- **Reporting.** Every theme error is recorded with the resolution source, token-set version, platform, and app version — never with user content.

### Acceptance criteria

- **AC-1.** Given any screen or state within F-1..F-5, when the preference is set to dark, then every visible element including empty, loading, error, and modal states renders from the dark token set, with no light-coloured surface or unstyled region remaining.
- **AC-2.** Given preference = dark, when the app is cold-loaded or hard-reloaded, then zero wrong-theme frames are observable in a recorded frame trace.
- **AC-3.** Given preference = system, when the OS theme is toggled while the app is open, then the app matches within 100 ms with no reload.
- **AC-4.** Given a stored preference, when the user signs out, signs back in, and restarts the app, then the effective theme is unchanged.
- **AC-5.** Given a schedule enabled for 20:00–07:00 local time, when local time crosses 20:00 then the effective theme becomes dark, and when it crosses 07:00 the base preference is restored.
- **AC-6.** Given any dark-mode screen, when contrast is measured, then body text is ≥ 4.5:1, large text ≥ 3:1, and non-text UI ≥ 3:1; the high-contrast dark variant achieves ≥ 7:1 for body text.
- **AC-7.** Given the F-4 analytics view in dark mode, then all series, gridlines, axes, and labels are legible and every series is distinguishable without relying on colour alone.
- **AC-8.** Given an active focus session (F-3) or a partially completed quick add (F-2), when the theme is toggled, then the session, timer, and typed input are all unchanged.
- **AC-9.** Given keyboard-only use, when the theme shortcut is invoked, then the theme changes, focus does not move, and the change is announced to assistive technology.
- **AC-10.** Given dark mode is active, when any view is printed or exported, then the output is legible and light-themed unless the user explicitly requested a themed export.
- **AC-11.** Given a component added later that references a raw colour literal, when the build-time coverage check runs, then the build fails and names the offending component.
- **AC-12.** Given local storage is unavailable, when the theme is changed, then it applies for the session and exactly one non-blocking notice is shown.
- **AC-13.** Given a session-scoped override set during an active schedule window, when the window ends or a new session starts, then the override is cleared and the scheduled behaviour resumes.
- **AC-14.** Given an explicit schedule with a zero-length window, when it is saved, then it is rejected with a field-level error and no schedule is stored.

### API behaviour

- **API-1 — Read theme state.** Returns the effective theme, the stored preference, the resolution source (`user`, `system`, `schedule`, `override`, `default`), the active token-set version, and the schedule definition. Readable entirely from local state with no network dependency.
- **API-2 — Write theme state.** Accepts only the allow-listed preference enum plus an optional validated schedule. Idempotent: repeating the same write returns the same effective state. Unknown fields or out-of-range values are rejected in whole with field-level errors — never partially applied.
- **API-3 — Schedule evaluation.** Performed at read time from the device's local time and, for sun-based mode, a location/timezone input. The server never dictates the effective theme for a device.
- **API-4 — Optional preference sync.** Stores and returns only the preference enum and schedule, versioned by last-write timestamp per device. Conflicts resolve last-write-wins for the pushed value; a device's local override is preserved unless the user explicitly pushes it to all devices (BR-5).
- **API-5 — Non-interference.** No other endpoint's behaviour depends on the theme. No request from F-1..F-5 may be rejected, delayed, or altered because of a theme value, and theme state is never a prerequisite for another feature's API call.
- **API-6 — Token-set distribution.** Token sets are delivered as build-time assets, not fetched per request. The client never blocks first paint or a theme switch on a network call (NFR-80).
- **API-7 — Diagnostics.** Exposes token-set version, last resolution source, and the most recent theme error to the local diagnostics surface, without user content.

**Data model (DM-)**

- **DM-1 — Local theme record.** `preference` (enum), `schedule` (optional: mode `explicit` | `sunrise-sunset`, start, end, timezone), `device_id`, `last_updated`, `token_set_version`, `session_override` (optional, transient).
- **DM-2 — Sync record (only when sync is enabled).** `user_id`, `preference`, `schedule`, `device_id`, `updated_at`. Contains no task content, no analytics data, and no integration payloads.

### Priority

**Must-have.** Confidence: high.

Dark mode is a first-class usability and accessibility requirement rather than a cosmetic extra. The product's primary persona uses it in evening and low-light contexts, the vision explicitly calls for structure without visual friction, and every other feature in scope (F-1 through F-5) renders on the same themed surfaces — leaving theming out would leave coverage gaps on screens that already exist. The must-have core is FR-126 through FR-132 plus FR-137, FR-140, and FR-143, measured by NFR-76 through NFR-78 and NFR-81. FR-133 (scheduled switching), FR-139 (high-contrast dark), and FR-142 (native chrome) are strong should-haves that ship in the same feature but may follow the core by one increment without breaking any acceptance criterion above.

### Open Questions

- **OQ-1.** Is the theme preference intended to sync across a user's devices by default, or remain device-local unless the user opts in? This affects FR-128, FR-132, NFR-84, NFR-85, and API-4. This section assumes device-local by default with opt-in sync, and does not reduce scope either way — the answer only changes the default.
- **OQ-2.** Does "Dark Mode" cover the product's public marketing/help surfaces, or only the authenticated application? This section assumes the authenticated application plus outbound notifications (FR-141), and treats marketing pages as outside this feature unless the user confirms otherwise.
- **OQ-3.** Is a fully custom accent colour (beyond light/dark/system and the high-contrast dark variant) in scope? BR-1 excludes it as written; the user should confirm, since including it would add requirements rather than remove any.
