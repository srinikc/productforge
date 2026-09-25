## F-8: Dashboard UX Component System

**Feature ID:** F-8

**Summary:** F-8 defines the shared dashboard UX component system for Product Forge: the versioned design-token foundation, the primitive/composed/feature component library, and the cross-cutting UX behaviours (loading, empty, error, real-time updates, theming, responsiveness, accessibility, internationalization, motion) that every dashboard surface in F-1 through F-7 (and any later feature) composes from. F-8 owns the *presentation contract* — how pipeline state, run telemetry, gate backlogs, portfolios, and operator commands are rendered, announced, and interacted with — so that an operator sees one consistent language of colour, layout, feedback, and control regardless of which feature produced the data. F-8 does not own any domain state: it renders authoritative state published by F-1 (projects/runs registry), F-2 (model tiers), F-3 (runs, stages, HIL gates), F-4 (portfolios), F-5 (multi-project run groups), F-6 (manual command surface), and F-7 (auto-mode policy/ledger). Where F-6 issues a command, F-8 provides the affordance, confirmation, and result feedback; the command's semantics belong to F-6.

**Boundary note:** F-8 does not define pipeline stages, run lifecycle rules, portfolio membership, model tiers, or autonomy policy. It consumes their state and their command contracts and guarantees a consistent, accessible, performant rendering of those contracts.

---

### Requirements

#### Functional Requirements

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| FR-159 | **Design token foundation** — Publish a single canonical, versioned token set covering colour (raw palette + semantic roles), spacing scale, radius, elevation, typography (family, size, weight, line-height), motion (duration, easing), and z-index. All components resolve visual values exclusively from tokens; no component may hard-code a raw hex, px spacing, or shadow. | must-have | Token package is the only theming surface (see FR-160). |
| FR-161 | **Primitive component library** — Ship foundational primitives: Button (variants: primary, secondary, ghost, danger, link; sizes: sm/md/lg), IconButton, Input, Textarea, Select, Combobox, Checkbox, Radio, Toggle, Badge, Tag, Tooltip, Icon, Divider, Avatar, Spinner-free progress primitives. Each primitive exposes states: default, hover, active, focus-visible, disabled, loading, invalid, read-only. | must-have | Feeds every higher-level component. |
| FR-162 | **Layout and container components** — Provide the app shell (top bar, collapsible sidebar, content region, breadcrumb slot), PageHeader, Section, Card, Grid/Stack/Inline layout helpers, SplitPane, and TabSet with URL-synced active tab. Layout components accept density (comfortable/compact) driven by token scale. | must-have | Shell accommodates the 32-stage, gate-heavy views from F-3. |
| FR-163 | **Data-display components** — Provide DataTable (columns, sortable headers, row selection, sticky header/first column, column resize, column visibility), key-value list, definition list, tree view, and virtualized list. | must-have | Backbone of project/run/portfolio surfaces. |
| FR-164 | **Status and lifecycle visualization** — Render a canonical StatusPill/StatusBadge for every pipeline entity state (queued, running, paused, gate-pending, blocked, retrying, succeeded, failed, cancelled, archived, restored) with an unambiguous token-bound colour, icon, and text label. A single mapping table is the source of truth and is shared across all features. | must-have | Colour is never the sole differentiator (see NFR-98). |
| FR-165 | **Pipeline graph component** — Render a pinned pipeline version as an ordered node graph: stage nodes, connectors, gate markers, current-position indicator, per-node outcome, and branch/parallel indicators where the stage model permits. Support zoom, pan, node focus, keyboard traversal, and a linear fallback list when the viewport cannot render a graph. | must-have | Used by F-1, F-3, F-5, F-6, F-7. |
| FR-166 | **Real-time update binding** — Provide a live-binding layer that subscribes components to the run/stage event stream, applies incremental patches to local view models, coalesces bursts, and surfaces a connection-state indicator (live / reconnecting / degraded-to-polling / offline). Full-fidelity state is re-fetched on reconnect. | must-have | Consumes event surface owned by F-3. |
| FR-167 | **Loading-state system** — Provide skeleton primitives (text line, paragraph, avatar, card, table row, chart block, graph node) with shape and count configured per component. Content regions MUST use skeletons rather than blocking spinners; a spinner is permitted only inside an already-rendered control (e.g. a submitting button). | must-have | Prevents layout shift (see NFR-99). |
| FR-168 | **Empty-state system** — Provide a reusable EmptyState component (slots: illustration, headline, description, primary CTA, secondary action, hint). Publish a canonical catalogue mapping every list, table, and page to a specific empty-state definition, including first-run, filtered-to-zero, permission-empty, and error-empty variants. | must-have | Required for every list/page before a feature ships. |
| FR-169 | **Error-state system** — Provide a reusable ErrorState component with severity, plain-language summary, technical detail (collapsible), recovery action(s), and a displayable correlation/trace id. Provide full-page error surfaces for 403/404/409/500-class outcomes with a recovery CTA. | must-have | Distinct from transport-error handling in FR-166. |
| FR-170 | **Toast and notification surface** — Provide a toast host with severity levels, stacking policy, auto-dismiss rules (info/success auto-dismiss with configurable duration; warnings/errors persist until dismissed unless marked transient), action slot (e.g. Undo, Retry, View), and an in-app notification centre with unread count, grouping, and mark-as-read. | must-have | Shared feedback channel for F-1, F-4, F-5, F-6, F-7 commands. |
| FR-171 | **Overlay system (modal + drawer)** — Provide Modal, FullScreenDialog, Drawer (left/right/bottom), Popover, and ConfirmDialog primitives with focus trap, initial-focus target, escape/backdrop dismissal policy, scroll lock, and restoration of focus to the invoking element on close. | must-have | Host for creation flows (F-2) and command confirmations (F-6). |
| FR-172 | **Form component system** — Provide a Field wrapper rendering label, required indicator, help text, character/limit counters, inline error, and aria-describedby wiring; standardise validation timing (validate on blur and on submit; suppress error until first blur or submit attempt). | must-have | Applies to F-2 creation wizard, F-6 overrides, F-7 policy editor. |
| FR-173 | **Command and control affordances** — Provide DangerousActionConfirm (explains impact, requires explicit acknowledgement), DryRunPreview surface (renders the would-be effect of a command before it is issued), and typed-phrase confirmation for irreversible operations (permanent project delete, emergency halt, kill-switch engage). | must-have | Affordance only; command semantics owned by F-6/F-7. |
| FR-160 | **Theme engine** — Support light theme, dark theme, and system-preference follow, resolved at first paint with no flash of incorrect theme. Support per-user theme override (persisted client-side) and per-tenant brand override achieved only by overriding token *values*, never by component forks. | must-have | Requires FR-159 to be complete. |
| FR-174 | **Responsive layout system** — Define a breakpoint set (compact / medium / expanded) and a documented rearrangement for the shell and for each data-dense component (tables degrade to card lists; graph degrades to linear list; sidebar collapses to drawer). | must-have | See also NFR-100. |
| FR-175 | **Keyboard and focus system** — Provide a documented global keyboard map, roving-tabindex patterns for composite widgets (menus, tabs, tables, graph), a visible ≥2px focus indicator on every interactive element, skip-to-content and skip-to-navigation links, and a CommandPalette for keyboard-driven navigation and command invocation. | must-have | No keyboard traps; see NFR-101. |
| FR-176 | **Screen-reader and announcement system** — Default to semantic HTML; supply correct ARIA roles/relationships for composite widgets; provide a shared live-region announcement bus with priority levels so that async state changes (run started, gate pending, run failed) are announced exactly once and are not duplicated by both the component and the toast. | must-have | Announcement de-duplication is a hard rule (see BR-8). |
| FR-177 | **Internationalization and locale formatting** — Provide locale bundles (message catalogs), plural/gender-aware message formatting, and locale-aware formatting components for date, time, relative time, number, currency, percentage, and file size. Provide full RTL layout mirroring driven by a direction token, with explicit non-mirrored exceptions (icons with semantic direction, pipeline graph connectors). | must-have | See NFR-102. |
| FR-178 | **Filter, sort, and search toolbar** — Provide a standard Toolbar with search input (debounced, with result count and clear affordance), filter chips, facet controls, sort control, and saved-view management (create, rename, set default, delete) persisted as named view state. | should-have | Used by F-1, F-3, F-4, F-5. |
| FR-179 | **Pagination and virtualization** — Provide cursor-based pagination controls (next/previous/load-more, page-size selection where the backing API supports it) and row/card virtualization with overscan tuning for tables and lists exceeding the render threshold. | must-have | Threshold and budget defined in NFR-103. |
| FR-180 | **Chart and metric components** — Provide standard charts (line, area, bar, stacked bar, donut, heatmap) and metric tiles (single value, delta, sparkline) with consistent axes, legends, tooltips, and empty/loading/error variants. Every chart MUST expose an equivalent accessible data table view. | should-have | Used by F-3, F-4, F-5, F-7 dashboards. |
| FR-181 | **Motion and transition system** — Provide tokenised durations and easings; define standard enter/exit, expand/collapse, and reorder transitions; respect `prefers-reduced-motion` by substituting an instant or opacity-only equivalent; never animate in a way that delays task completion. | should-have | See NFR-99 and NFR-101 (no flashing > 3Hz). |
| FR-182 | **Component catalogue and playground** — Publish a living catalogue per component containing: purpose, props/API, all states, accessible usage notes, do/don't guidance, and copy-pasteable examples. The catalogue is the authoritative reference for feature teams and is regenerated on every release. | should-have | Enables consistent adoption. |
| FR-183 | **Component versioning, telemetry, and deprecation** — Version the component system independently; publish a compatibility policy for breaking changes; emit non-PII usage telemetry to track adoption and identify unused components; document a deprecation path with a mechanical migration aid before removing a component. | nice-to-have | See NFR-104 for PII limits. |

#### Non-Functional Requirements

| ID | Requirement | Target / Measurement |
|---|---|---|
| NFR-99 | **Perceived performance** | First Contentful Paint < 1 s, Largest Contentful Paint < 2.5 s, Cumulative Layout Shift < 0.1, Time to Interactive < 3 s on the reference 3G profile; skeletons MUST reserve final layout dimensions so CLS contribution from loading transitions is ≈ 0. |
| NFR-105 | **Interaction latency** | Input-to-visual-feedback < 100 ms for hover/focus/press; locally-handled interactions (open menu, toggle, tab switch) < 100 ms; command issuance acknowledgement (optimistic state) < 150 ms. |
| NFR-101 | **Bundle and delivery budget** | Initial dashboard route JS ≤ 200 KB gzipped excluding framework runtime baseline as agreed by Architect; component library must be tree-shakeable with per-component entry points; no component may be imported into the critical path without a measured budget. |
| NFR-106 | **Accessibility conformance** | WCAG 2.1 AA for all components and states: text contrast ≥ 4.5:1, large text ≥ 3:1, UI/graphical objects and focus indicators ≥ 3:1; all interactive elements keyboard reachable and operable; correct roles/states via automated a11y test suite in CI with zero critical violations. |
| NFR-98 | **Colour-independence** | No state, severity, or outcome may be conveyed by colour alone; every colour-coded element MUST also carry a text label, icon, or pattern. Verified by greyscale rendering review of the status catalogue (FR-164) and all charts. |
| NFR-100 | **Touch and pointer ergonomics** | Minimum 44×44 CSS px touch target on compact breakpoints; minimum 24×24 CSS px pointer target on expanded breakpoints with ≥ 8 px spacing between adjacent targets. |
| NFR-107 | **Browser and device support** | Support the current and previous major versions of Chrome, Edge, Firefox, and Safari on desktop, plus the current and previous major versions of mobile Safari and Chrome on Android; documented graceful degradation for unsupported features. |
| NFR-108 | **Theme integrity** | No flash of incorrect theme at first paint; theme switch completes in < 100 ms with no layout shift; every documented component state is verified in both light and dark themes before release. |
| NFR-109 | **Real-time throughput** | Sustain ≥ 50 incremental state patches/second across visible components without exceeding a 16 ms frame budget per batch; bursts above the batch rate are coalesced rather than queued unboundedly; reconnection re-sync completes < 3 s from network restore. |
| NFR-103 | **Large-dataset scalability** | Tables, lists, and graphs remain interactive (scroll and sort interactions within NFR-105 budget) with ≥ 10,000 rows and ≥ 500 graph nodes, achieved via FR-179 virtualization and incremental rendering. |
| NFR-102 | **Internationalization readiness** | 100% of user-facing strings externalised to locale bundles (zero hard-coded copy in components); complete RTL mirroring with no clipped or overlapping layout at the compact breakpoint; all formatted values respect the active locale. |
| NFR-110 | **Client-side security** | All rendered text is escaped by default; raw HTML injection is prohibited in shared components; any sanitised-rich-text surface must be explicitly allow-listed and audited; no evaluation of user-supplied markup as code; external links carry appropriate rel attributes. |
| NFR-104 | **Data handling and residency** | Component telemetry (FR-183) MUST NOT contain project names, idea text, run payloads, operator identities, or any PII; only anonymous component/version/prop-shape usage. UI preference persistence (theme, density, saved views where client-scoped) stays client-side unless a backing store owned by another feature is explicitly used. Telemetry payloads are governed by the same residency rules as the rest of the platform. |
| NFR-111 | **Deployment and environment parity** | The component system is released as a versioned, immutable artefact; the same version renders identically in development, staging, and production; token overrides are environment-configurable without a code change; rollback to the previous component version is possible without a data migration. |
| NFR-112 | **Observability and quality gates** | Component runtime errors are contained by per-region error boundaries and reported with component id/version and correlation id; the release pipeline blocks on failing accessibility, visual-regression, and contrast checks; a11y violations and broken states are observable in production through error-boundary reporting. |

#### User Stories

| ID | Story |
|---|---|
| US-91 | As a **pipeline operator**, I want a consistent visual language for every pipeline state across every screen, so that I can read the health of many projects at a glance without re-learning each page. |
| US-92 | As an **operator working long shifts**, I want a dark theme that follows my system or my explicit choice and never flashes the wrong theme, so that the dashboard is comfortable and stable to use. |
| US-93 | As a **screen-reader user**, I want meaningful, non-duplicated announcements when a run changes state or a gate becomes pending, so that I can supervise pipelines without sight. |
| US-94 | As a **keyboard-only operator**, I want to reach and operate every control, including the pipeline graph, and to invoke common actions from a command palette, so that I never need a mouse. |
| US-95 | As a **mobile operator**, I want data-dense tables and the pipeline graph to reflow into usable card and list forms with finger-sized targets, so that I can check and steer runs from a phone. |
| US-96 | As a **product designer**, I want a single token set and a documented component catalogue, so that my designs map 1:1 to shipped components and stay consistent over time. |
| US-97 | As a **frontend engineer**, I want tree-shakeable, versioned components with clear props and states, so that I can build a feature screen without inventing new visual patterns. |
| US-98 | As a **new engineer onboarding**, I want a living playground showing every component state and its accessible usage, so that I can build correctly on day one. |
| US-99 | As an **operator in an RTL locale**, I want the entire layout mirrored correctly with formatted dates, numbers, and currency in my locale, so that the dashboard feels native to me. |
| US-100 | As an **operator on a slow or unreliable connection**, I want skeletons that reserve space, a clear live/reconnecting/offline indicator, and graceful degradation, so that I always know the freshness of what I am seeing. |
| US-101 | As an **operator with colour-vision deficiency**, I want every status to carry a text label or icon in addition to colour, so that I can distinguish succeeded, failed, and gate-pending runs reliably. |
| US-102 | As an **operator responding to a failure**, I want an error surface that states what happened, offers a recovery action, and shows a correlation id, so that I can act and escalate precisely. |
| US-103 | As a **tenant administrator**, I want to apply my organisation's brand by overriding design tokens only, so that I get branded colours without diverging from the shared component behaviour. |
| US-104 | As a **support engineer**, I want a correlation id on every error surface and consistent component versioning, so that I can reproduce and route an issue quickly. |
| US-105 | As a **product manager**, I want adoption telemetry per component and per theme, so that I can prioritise investment and safely retire unused components. |

---

### Behaviour

The component system is a **presentation layer with a strict contract**:

1. **Token-first rendering (FR-159).** Every visual property resolves through a token. A component receives semantic props (e.g. `variant="danger"`, `status="gate-pending"`) and maps them to tokens internally. Features never pass raw colours or spacing.
2. **State ownership.** Components are stateless with respect to domain data. They receive view-models produced by feature-owned adapters and emit intention events (e.g. `onConfirm`, `onRetry`). The component system never mutates authoritative state; it renders what it is given and reports what the user did.
3. **Canonical status mapping (FR-164).** A single exported mapping table resolves any pipeline entity state to `{ label, token, icon, ariaLabel }`. All features import this table; no feature may define its own status colours. Adding a new entity state requires adding it to the mapping table, which triggers the accessibility and contrast gates.
4. **Live binding lifecycle (FR-166).** A component bound to live data moves through `connecting → live → reconnecting → degraded(polling) → offline`. The binding layer patches only changed fields, batches updates within a frame, and on reconnection discards local patches in favour of a full authoritative re-fetch. The visible connection indicator reflects this state at all times.
5. **Feedback discipline.** Every user-initiated command produces exactly one of: an inline state change (optimistic), a toast, an inline field error, or a blocking dialog. Success feedback for non-destructive, self-evident actions is inline; failure feedback is never silent.
6. **Announcement de-duplication (FR-176).** When a state change is both rendered visually and pushed to a toast, exactly one live-region announcement is emitted at the highest applicable priority. The component that owns the primary surface is the announcer; the toast suppresses announcement when it is acting as a duplicate.
7. **Progressive disclosure.** Dense controls (advanced filters, raw event detail, technical error detail) are collapsed by default and revealed on demand, keeping first-run surfaces legible.
8. **Determinism across environments (NFR-111).** Given the same component version, tokens, locale, theme, and data, rendering is identical across environments; no environment-conditional visual forks.

---

### Business Rules

| ID | Rule |
|---|---|
| BR-1 | The status mapping table (FR-164) is the single source of truth for entity-state presentation; features MUST NOT introduce parallel status colours or labels. |
| BR-2 | No component may hard-code a colour, spacing, radius, elevation, or timing value; all such values must come from tokens. A lint rule enforces this in the component package. |
| BR-3 | Status and severity MUST always be conveyed by at least two channels (colour + text, or colour + icon). Colour-only encoding is prohibited. |
| BR-4 | Irreversible operations (permanent delete, emergency halt, kill-switch engage) MUST use typed-phrase confirmation (FR-173); reversible destructive operations MUST use a confirmation dialog with an explicit impact statement. |
| BR-5 | A command that supports dry-run MUST present the dry-run preview before the confirmation step for high-impact operations, and the preview result MUST be visibly dated/attributed as a projection, not a fact. |
| BR-6 | Toast auto-dismiss applies to informational and success toasts only; warnings and errors persist until dismissed unless explicitly marked transient by the issuing feature. |
| BR-7 | Empty state is mandatory: a list/page with zero items MUST render an `EmptyState`; falling through to a bare "no data" string is not permitted. |
| BR-8 | Each asynchronous state change is announced to assistive technology exactly once; duplicate announcements from concurrent surfaces are a defect. |
| BR-9 | Theme overrides (per-user and per-tenant) may change only token values; they MUST NOT alter component structure, interaction, or accessible names. Any override failing contrast checks (NFR-106) is rejected and the default token is used. |
| BR-10 | Charts and graphs MUST provide an equivalent accessible data view; a chart with no accessible alternative is not release-eligible. |
| BR-11 | Saved views (FR-178) store filter/sort/search state only — never credentials, never server-side secrets. |
| BR-12 | A component may be removed only after the deprecation window and migration aid defined in FR-183 have been published and adoption telemetry shows no remaining production usage. |
| BR-13 | Live-bound surfaces MUST display connection state; rendering "stale" data without an indicator is prohibited. |
| BR-14 | Client-side preference persistence is limited to non-sensitive presentation state (theme, density, column visibility, last-used view); it must not persist domain data or identifiers. |

---

### Validation

| ID | Validation |
|---|---|
| V-1 | **Token completeness** — every semantic role referenced by any component resolves to a defined token in both light and dark themes; a build check fails on any unresolved token reference. |
| V-2 | **Contrast** — automated contrast audit of every documented component state (default, hover, active, focus-visible, disabled, invalid) in both themes; any pair below the NFR-106 threshold fails the build. |
| V-3 | **Focus visibility** — automated check that every focusable component renders a ≥ 2 px focus indicator with ≥ 3:1 contrast against its adjacent background in both themes. |
| V-4 | **Keyboard operability** — every composite widget is verified keyboard-reachable, operable, and escapable; no keyboard trap exists outside of an intentionally modal overlay. |
| V-5 | **ARIA correctness** — automated role/relationship validation for composite widgets (tabs, menus, tables, tree, graph, dialog) with zero critical violations. |
| V-6 | **Touch target size** — automated measurement of interactive element bounding boxes against NFR-100 minimums at compact breakpoints. |
| V-7 | **Layout-shift budget** — automated CLS measurement of loading→loaded transitions; skeletons must reserve final dimensions within the NFR-99 budget. |
| V-8 | **Bundle budget** — per-component and critical-path bundle size measured on every build against NFR-101; exceeding the budget fails the release gate. |
| V-9 | **String externalisation** — a lint rule fails any user-facing literal string inside the component package that is not sourced from a locale bundle. |
| V-10 | **RTL integrity** — automated visual verification that no component at compact and expanded breakpoints clips, overlaps, or mis-orders under `dir="rtl"`. |
| V-11 | **Reduced-motion compliance** — automated check that `prefers-reduced-motion` substitutes a non-animated or opacity-only path for every transition and that no animation exceeds 3 Hz flashing (NFR-106). |
| V-12 | **Status-mapping totality** — every entity state enumerated by the pipeline model has a mapping entry; an unmapped state renders a fallback "Unknown" status and raises a build warning rather than a silent failure. |
| V-13 | **Theme override safety** — tenant/user token overrides are validated against contrast rules (BR-9) before being applied; invalid overrides are rejected with an explanatory message. |
| V-14 | **Telemetry payload shape** — schema validation that telemetry events contain only allowed fields and no PII (NFR-104); a violating event is dropped client-side and never transmitted. |

---

### Edge Cases

| ID | Case | Expected Behaviour |
|---|---|---|
| EC-1 | A pipeline entity reports a state not present in the status mapping table. | Render a neutral "Unknown" status pill with the raw state string shown as tooltip text, emit a console warning, and continue rendering the rest of the surface. |
| EC-2 | Real-time connection drops mid-run while a gate is pending. | Transition the connection indicator to `reconnecting`, keep the last-known state visible with a "last updated" timestamp, disable commands that require live confirmation, and re-sync fully on reconnect. |
| EC-3 | A user has applied a tenant brand override whose primary colour fails contrast. | Reject the offending override, fall back to the default token, and surface an explanatory message to the administrator; all other overrides remain applied. |
| EC-4 | A pipeline graph has more nodes than can be legibly rendered at the current viewport (≥ 500). | Switch to the linear fallback list with virtualization, offer an opt-in graph view with pan/zoom, and preserve current-node position across the switch. |
| EC-5 | A DataTable receives 10,000+ rows. | Virtualize rendering, keep sort and scroll within the interaction budget (NFR-105), and preserve selection state across virtualized scroll. |
| EC-6 | Locale is RTL and the graph has directional connectors. | Mirror layout and text direction, but do not mirror semantically directional icons (e.g. forward/back arrows) or graph connector direction; document each exception. |
| EC-7 | A command's optimistic UI succeeds but the server rejects the command. | Revert the optimistic state, surface an inline error or persistent toast explaining the rejection, and preserve the user's input so it can be retried. |
| EC-8 | Two surfaces announce the same async event simultaneously (e.g. a run-failed badge and a toast). | Emit exactly one live-region announcement at the highest applicable priority (BR-8); the secondary surface suppresses its announcement. |
| EC-9 | `prefers-reduced-motion` is enabled while a transition is in progress. | Complete the current transition immediately (no mid-flight abort flicker) and substitute non-animated behaviour for all subsequent transitions. |
| EC-10 | A component receives partial or null data from its adapter while a feature is loading. | Render the skeleton shape for missing regions rather than blank space or a broken layout; never render `undefined`/`null` as visible text. |
| EC-11 | A saved view (FR-178) references a filter field that no longer exists. | Load the view, drop the stale filter, show a non-blocking notice that the view was adjusted, and offer to re-save. |
| EC-12 | A user switches theme while a chart is mid-animation. | Recolour tokens immediately; do not restart the animation; ensure the final frame uses the new theme's palette. |
| EC-13 | A destructive-action confirmation dialog is open when the underlying entity is deleted by another operator. | On confirm, the command returns a conflict outcome; show a clear "no longer exists" message with a refresh action; never silently succeed. |
| EC-14 | Very long unbroken strings (project names, error messages, correlation ids) are rendered. | Wrap or truncate with accessible full value available via tooltip or expandable detail; no horizontal overflow breaking the surrounding layout. |

---

### Error Handling

| ID | Error condition | Handling |
|---|---|---|
| EH-1 | Component runtime render error. | A per-region error boundary catches the failure, renders the ErrorState component (FR-169) in place of the broken region, keeps the rest of the dashboard interactive, and reports component id/version plus correlation id for observability (NFR-112). |
| EH-2 | Live event stream transport failure. | Degrade to polling, surface a persistent `degraded` connection banner with a manual "Reconnect" action, and restore live mode automatically when the stream recovers (FR-166). |
| EH-3 | Command rejected by server (validation, conflict, permission). | Map the server outcome to the correct inline field error, conflict notice, or permission error; never present a generic "something went wrong" when a specific cause is known. |
| EH-4 | Malformed or unreadable data from a feature adapter. | Render a data-unavailable ErrorState for the affected region with a retry action; do not crash the whole surface; log the adapter contract violation for the owning feature. |
| EH-5 | Theme or token resolution failure at first paint. | Fall back to the default light (or system-resolved) token set, render immediately, and record the failure for observability; never render an unstyled surface. |
| EH-6 | Telemetry/analytics transport failure. | Drop the event silently client-side (telemetry must never degrade UX) and never retry unboundedly; log locally at debug level only. |
| EH-7 | Locale bundle missing a requested key. | Render the default-locale string and mark the miss for translation tooling; never render the raw key as user-visible copy in production. |
| EH-8 | Clipboard or download action unavailable (permissions/browser). | Present an inline fallback (selectable text area or alternate export) with a clear explanation rather than a silent no-op. |

---

### Acceptance Criteria

| ID | Criterion | Verifies |
|---|---|---|
| AC-1 | Every visual property in the component package resolves from a token; a lint/build check fails on any hard-coded colour, spacing, radius, elevation, or timing value. | FR-159, BR-2 |
| AC-2 | The full primitive set listed in FR-161 exists with all documented states and passes the automated state matrix test. | FR-161 |
| AC-3 | Every pipeline entity state renders through the canonical StatusPill with a text label and an icon, and is visually distinct in greyscale. | FR-164, BR-3, NFR-98 |
| AC-4 | The pipeline graph renders a 32-stage pipeline with gate markers, current position, and per-node outcome; keyboard traversal reaches every node; a linear fallback is available. | FR-165, FR-175 |
| AC-5 | With the event stream connected, a run-state change is reflected in a bound component within 1 s and the connection indicator reads `live`; severing the stream shows `reconnecting` then `degraded`, and reconnection restores authoritative state within 3 s. | FR-166, NFR-109 |
| AC-6 | Loading content regions render skeletons that reserve final dimensions; measured CLS contribution from the loading transition is within the NFR-99 budget. | FR-167, NFR-99 |
| AC-7 | Every list and table in the catalogue renders a defined EmptyState for its zero-item case; no surface falls through to a bare "no data" string. | FR-168, BR-7 |
| AC-8 | A forced 500-class and a forced 404 produce full-page error surfaces with a recovery action and a correlation id; a forced region error keeps the remainder of the dashboard interactive. | FR-169, EH-1 |
| AC-9 | Info and success toasts auto-dismiss; warnings and errors persist until dismissed; a toast action (Undo/Retry/View) is operable by keyboard. | FR-170, BR-6 |
| AC-10 | Every modal/drawer traps focus, sets an initial focus target, dismisses per policy, and returns focus to the invoking element on close. | FR-171 |
| AC-11 | Field validation displays errors on blur and on submit (not on every keystroke), with label, help text, and error wired via aria-describedby. | FR-172 |
| AC-12 | An irreversible operation requires a typed-phrase confirmation; a high-impact reversible operation shows an impact statement and, where dry-run exists, a clearly-labelled projection before confirmation. | FR-173, BR-4, BR-5 |
| AC-13 | Switching between light and dark at first paint produces no flash of incorrect theme and no layout shift; every documented state passes contrast checks in both themes. | FR-160, NFR-108, V-2 |
| AC-14 | At the compact breakpoint, tables degrade to card lists, the graph degrades to a linear list, the sidebar collapses to a drawer, and every interactive target meets the 44×44 minimum. | FR-174, NFR-100, V-6 |
| AC-15 | Every interactive element is reachable and operable by keyboard, shows a ≥ 2 px focus indicator, and no keyboard trap exists outside modal overlays; skip links are present. | FR-175, NFR-106, V-3, V-4 |
| AC-16 | An async run-state change produces exactly one live-region announcement; a concurrent toast does not duplicate it. | FR-176, BR-8, EC-8 |
| AC-17 | In an RTL locale the full layout mirrors correctly, and dates, numbers, and currency render per locale; zero user-facing strings are hard-coded in the component package. | FR-177, NFR-102, V-9, V-10 |
| AC-18 | Search input is debounced, shows a result count, and clears cleanly; saved views persist filter/sort/search state and survive a reload without storing credentials. | FR-178, BR-11 |
| AC-19 | A 10,000-row table and a 500-node graph remain interactive within the NFR-105 latency budget via virtualization. | FR-179, NFR-103, EC-5 |
| AC-20 | Every chart exposes an equivalent accessible data table; charts render correct empty, loading, and error variants. | FR-180, BR-10 |
| AC-21 | With `prefers-reduced-motion` enabled, all transitions substitute a non-animated or opacity-only path, and no animation exceeds 3 Hz flashing. | FR-181, V-11 |
| AC-22 | The catalogue renders every component's purpose, props, states, accessibility notes, and examples, and regenerates on release. | FR-182 |
| AC-23 | Telemetry events contain only allowed fields (no PII); a violating event is dropped client-side and never transmitted. | FR-183, NFR-104, V-14 |
| AC-24 | A published compatibility policy for breaking changes exists, and removal of a component is blocked until the deprecation window and migration aid are complete. | FR-183, BR-12 |
| AC-25 | The component system is released as an immutable, versioned artefact rendering identically across development, staging, and production, with rollback to the prior version requiring no data migration. | NFR-111 |

---

### API Behaviour

The component system exposes a **UI contract**, not a network API. Its external surface is the component API, the token API, the theme API, the live-binding API, and the design-system metadata endpoints used by tooling.

| ID | Surface | Behaviour |
|---|---|---|
| API-1 | **Token API** — `tokens(theme, overrides?) → { colour, spacing, radius, elevation, typography, motion, zIndex }`. Pure, synchronous, side-effect free. `overrides` may only replace semantic role values, never introduce new roles. Unknown roles are ignored and logged (BR-9, V-13). |
| API-2 | **Status mapping API** — `statusMap(entityKind, state) → { label, token, icon, ariaLabel }`. Total over known states; returns the "Unknown" fallback for unrecognised states (V-12, EC-1). Immutable; extended only by release. |
| API-3 | **Component props contract** — Every component accepts only semantic props (`variant`, `status`, `size`, `density`, `severity`) plus an `as`/slot escape hatch; components reject raw style/colour props at type level. Emits intention events (`onCommand`, `onConfirm`, `onRetry`, `onDismiss`) and never performs domain mutation itself. |
| API-4 | **Live-binding API** — `bind(source, { selectors, onPatch, onStatusChange }) → { status, close }`. `onPatch` delivers coalesced incremental patches within a frame budget (NFR-109); `onStatusChange` reports `connecting | live | reconnecting | degraded | offline`. On reconnect the binding fetches a full authoritative snapshot and discards pending local patches (FR-166). `close()` unsubscribes deterministically with no leaked timers or sockets. |
| API-5 | **Announcement API** — `announce({ message, priority, source }) → void`. Priority ∈ `polite | assertive`. De-duplicates against an identical `message` from the same logical event within a short window (BR-8, EC-8). Components MUST route all async announcements through this API. |
| API-6 | **Preference API** — `preferences.get(key)` / `set(key, value)` for non-sensitive presentation state only (theme, density, column visibility, saved views). Persistence is client-side; `set` rejects keys outside the allow-list (BR-14, NFR-104). |
| API-7 | **Notification API** — `notify({ severity, title, message, actions, transient }) → id` and `dismiss(id)`. Honours BR-6 auto-dismiss policy; actions are keyboard operable; returns a stable id for programmatic dismissal and for announcement de-duplication. |
| API-8 | **Component metadata / catalogue endpoint** — Static, build-generated manifest describing every component: id, version, props schema, supported states, a11y notes, examples, and deprecation status. Consumed by the catalogue (FR-182) and by tooling that enforces BR-2, V-9, and FR-183 deprecation rules. Non-PII, cacheable, environment-identical (NFR-111). |
| API-9 | **Telemetry emit API** — `emitComponentUsage({ componentId, version, propsShape, theme, locale }) → void`. Best-effort, non-blocking, silently dropped on transport failure (EH-6); schema-validated to forbid PII (V-14, NFR-104); never retried unboundedly. |

**Contract stability:** The component API, token API, status mapping API, and live-binding API are versioned together (FR-183). Breaking changes require a new major version, a documented migration aid, and satisfaction of BR-12 before any component removal. Additive prop/state changes are non-breaking and may ship within a minor version.

---

### Priority

**Overall feature priority: must-have.**

F-8 is the rendering substrate for the entire dashboard. Every must-have feature (F-1 project/run registry, F-2 creation wizard, F-3 run initiation and monitoring, F-4 portfolios, F-5 multi-project runs, F-6 manual command surface) depends on F-8 for consistent, accessible, real-time presentation of its state and for the confirmation/feedback affordances around its commands. Without F-8, each feature would invent its own status colours, loading patterns, and feedback behaviour, producing an inconsistent and inaccessible dashboard.

| Priority | Scope |
|---|---|
| **must-have** | FR-159–FR-177, FR-179 (tokens, primitives, layout, data display, status mapping, pipeline graph, live binding, loading, empty, error, toast/notification, overlays, forms, command affordances, theming, responsiveness, keyboard/focus, screen-reader announcements, i18n/RTL, pagination/virtualization) and NFR-99–NFR-112. These are non-negotiable for a coherent and accessible dashboard. |
| **should-have** | FR-178 (filter/sort/search toolbar), FR-180 (charts and metric tiles), FR-181 (motion system), FR-182 (component catalogue and playground). High value for operator efficiency and long-term consistency; can follow the must-have core but must not be omitted from the release boundary. |
| **nice-to-have** | FR-183 (component versioning, adoption telemetry, and formal deprecation policy). Valuable for sustainable evolution and safe retirement of components; can land once the library has stabilised and multiple consumers exist. |

**Dependency note:** The chart components (FR-180) and saved views (FR-178) are *should-have* on the basis that the underlying reporting surfaces belong to F-3/F-4/F-5/F-7; if any of those features ship their dashboards in the first release, FR-178 and FR-180 escalate to **must-have** for those surfaces to meet the accessibility and consistency bar set by NFR-106 and BR-10.
