## F-11: Mobile Dashboard Companion
**Feature ID:** F-11

**Summary:** F-11 defines the mobile companion experience for Product Forge. It gives operators a secure, responsive, notification-driven view of the same authoritative pipeline state exposed by the dashboard: projects, portfolios, runs, stages, human-in-the-loop (HIL) gates, failures, auto-mode decisions, and multi-project run groups. The mobile companion is read-first and action-safe: it never owns domain state, never executes commands on its own, and delegates every command to the manual command surface of F-6 for preview, confirmation, and audit. It works on phones and tablets, supports offline read-only review of last-known state, degrades gracefully when connectivity or AI services are unavailable, and enforces mobile-specific security, privacy, accessibility, and notification rules.

**Boundary note:** F-11 does not own project/run records (F-1), model-tier definitions (F-2), run/stage execution or HIL gate definitions (F-3), portfolio membership rules (F-4), multi-project run-group structure (F-5), manual command semantics (F-6), auto-mode policy/ledger (F-7), the shared dashboard UX component system (F-8), conversational reasoning/grounding (F-9), or voice I/O (F-10). F-11 renders those authoritative surfaces in a mobile context and routes any operator action through the owning feature’s published command surface.

### Requirements

#### Functional Requirements

| ID | Requirement | Description | Priority |
|---|---|---|---|
| FR-251 | Mobile authentication and session | Allow an operator to authenticate into the mobile companion, establish a device-bound session, unlock with device biometrics when available, enforce idle timeout, support explicit sign-out, and require re-authentication for high-risk actions. | must-have |
| FR-252 | Mobile dashboard home | Provide a mobile-first home surface showing the operator’s most relevant state: active runs, waiting HIL gates, recent failures, auto-mode escalations, portfolio roll-ups, and quick links to projects and alerts. | must-have |
| FR-253 | Project and portfolio browsing | Let an operator browse, search, filter, and open projects and portfolios with mobile-optimized lists, summaries, status chips, and drill-down detail. | must-have |
| FR-254 | Run and stage monitoring | Show live and historical run state, stage progression, stage outcome, timings, telemetry summaries, failure reasons, and retry/skip indicators in a mobile-readable timeline. | must-have |
| FR-255 | HIL gate review and mobile decision support | Surface pending HIL gates with context, evidence, deadline, and impact; allow the operator to review and prepare a gate decision; route the final decision through the manual command surface of F-6. | must-have |
| FR-256 | Real-time updates and push notifications | Keep visible screens current through real-time updates while foregrounded, and deliver opt-in push notifications for run state changes, gate waits, failures, budget/time guardrails, auto-mode escalations, and multi-project run-group completion. | must-have |
| FR-257 | Notification preferences and quiet hours | Let operators configure which notification classes they receive, per portfolio or per project where allowed, and define quiet hours, critical override rules, and digest preferences. | should-have |
| FR-258 | Offline read-only cache and sync | Cache the last-known state of permitted projects, runs, stages, gates, and portfolios so the operator can review safely offline; queue no mutating actions except command drafts; refresh and reconcile automatically on reconnect. | should-have |
| FR-259 | Mobile command drafting and confirmation | Allow the operator to draft supported commands from mobile, preview impact, supply required parameters, and hand the draft to F-6 for confirmation and execution; the mobile companion never bypasses F-6. | must-have |
| FR-260 | Global search and filters | Provide mobile search across projects, portfolios, runs, stages, gates, and operators’ own drafts, with filters for status, owner, portfolio, time range, failure class, and gate state. | should-have |
| FR-261 | Deep linking and shareable views | Support deep links into projects, runs, stages, gates, portfolios, and notification targets so operators can navigate from a push, email, chat, or shared link into the correct mobile view. | should-have |
| FR-262 | Device management and remote wipe | Let operators see registered devices, revoke a device, remotely wipe cached mobile data, and require re-registration after revocation. Administrators with sufficient role can enforce device policy and revoke devices for a user. | must-have |
| FR-263 | Accessibility and internationalization | Provide screen-reader labels, dynamic type support, high-contrast compatibility, reduced-motion respect, keyboard/switch access where supported, localized dates/numbers/currency, and RTL-ready layouts. | must-have |
| FR-264 | Telemetry, diagnostics, and support bundle | Collect mobile performance and crash telemetry with privacy controls, and allow an operator to generate a redacted support bundle containing recent app state, connectivity events, and error identifiers. | should-have |
| FR-265 | Auto-mode and multi-project run-group visibility | Expose auto-mode policy status, decision ledger summaries, escalations, and kill-switch availability; expose multi-project run-group parent/child roll-ups and child run status without redefining those features. | should-have |

#### Non-Functional Requirements

| ID | Category | Requirement | Target / Measurement |
|---|---|---|---|
| NFR-151 | Performance | Mobile app cold start, screen transition, list rendering, and interaction response must remain responsive on mid-tier devices and degraded networks. | Cold start < 2s on mid-tier device; interaction response < 100ms; first meaningful dashboard render < 1.5s on 4G; list scroll at 60fps for up to 500 visible rows. |
| NFR-152 | Scalability and availability | The mobile companion must tolerate large portfolios, many concurrent runs, and high notification volume without blocking the operator. | 99.9% monthly availability for mobile API and push delivery; graceful degradation when real-time channel unavailable; support 10,000 concurrent mobile sessions per region. |
| NFR-153 | Security and privacy | Mobile access, local storage, notifications, and command drafting must protect pipeline state and operator identity. | Device-bound sessions; biometric unlock where available; encrypted local cache; no sensitive run payloads in push notification bodies; token rotation; remote wipe within 60s of revocation. |
| NFR-154 | Data residency and retention | Mobile caching and notification routing must respect data residency, retention, and minimization rules. | Cache TTL configurable and default <= 24h for non-critical state; no permanent offline copy of secrets; push payloads contain only opaque identifiers and summary text; regional pinning honored where configured. |
| NFR-155 | Deployment and environment | The mobile companion must operate across supported mobile operating system versions, phone/tablet form factors, and network conditions. | Supports current and previous major versions of iOS and Android; supports phone and tablet layouts; supports installable app and mobile web companion mode where offered; offline mode available after first successful authenticated load. |
| NFR-156 | Accessibility and internationalization | Mobile accessibility and locale support must meet the same product standard as the dashboard. | WCAG 2.1 AA for mobile surfaces; screen-reader traversal for all interactive elements; dynamic type up to 200%; RTL layout support; localized date/time/number/currency. |

#### User Stories

| ID | Story |
|---|---|
| US-151 | As a pipeline operator, I want to monitor active runs and waiting gates from my phone, so that I can stay informed when I am away from my desk. |
| US-152 | As a pipeline operator, I want push notifications for failures, gate waits, and auto-mode escalations, so that I can respond quickly to urgent pipeline events. |
| US-153 | As a pipeline operator, I want to review and prepare HIL gate decisions on mobile with secure confirmation, so that I can unblock work without opening a laptop. |
| US-154 | As a pipeline operator, I want to review last-known pipeline state while offline, so that I can understand what was happening even without connectivity. |
| US-155 | As a pipeline operator, I want to control notification types and quiet hours, so that I only receive alerts that matter to me. |
| US-156 | As a security administrator, I want device revocation and remote wipe controls for mobile access, so that lost or stolen devices do not expose pipeline data. |

### Behaviour

- B-1: On launch, the mobile companion checks for a valid device-bound session. If the session is missing or expired, it presents authentication. If biometric unlock is available and enabled, it offers biometric unlock before password or passkey fallback.
- B-2: After authentication, the companion opens the mobile dashboard home. The home prioritizes actionable state: waiting HIL gates, failed runs, active runs, auto-mode escalations, and portfolio exceptions.
- B-3: The operator can drill from home into a portfolio, project, run, stage, gate, or alert. Each drill-down preserves context and supports back navigation that is consistent with mobile platform conventions.
- B-4: When a run is foregrounded, the companion subscribes to real-time updates through the platform’s published event stream. If real-time updates are unavailable, it falls back to periodic refresh and displays the last-updated timestamp.
- B-5: When the operator opens a HIL gate, the companion shows the gate reason, affected stage, run context, deadline, evidence links, prior decisions if permitted, and the impact of approve/reject/escalate. The operator may prepare a decision and required note. The final decision is submitted through the manual command surface of F-6 and is not executed by the mobile companion directly.
- B-6: When the operator drafts a command such as pause, resume, cancel, retry, skip, or parameter override, the companion presents a preview with target, scope, expected effect, risk level, and required confirmation. The command is handed to F-6; the mobile companion only displays the resulting status.
- B-7: Push notifications are opt-in. The operator chooses notification classes, quiet hours, and critical overrides. Critical notifications may bypass quiet hours only when policy allows and the notification class is marked critical.
- B-8: When the device is offline, the companion shows a persistent offline indicator and serves cached read-only data. Mutating actions are unavailable except drafting, which is queued locally and clearly marked as unsent.
- B-9: On reconnect, the companion refreshes authoritative state, reconciles queued drafts, and surfaces any conflict for operator review. It never silently overwrites server state.
- B-10: Deep links open the correct mobile view after authentication, preserving the target object. If the target is inaccessible, the companion shows a recovery path to the relevant project or home.
- B-11: The companion respects role-based authorization. Actions the operator cannot perform are hidden or disabled with an explanation, not merely failing after submission.
- B-12: Auto-mode screens show policy status, current autonomy level, recent decisions, escalations, and kill-switch availability. A kill-switch action is drafted through F-6 and confirmed with re-authentication.
- B-13: Multi-project run-group screens show parent status, child run progress, aggregate gate backlog, failure counts, and drill-down into individual child runs.
- B-14: The companion supports background refresh and notification handling without blocking the foreground UI. Opening a notification routes to the correct object or to a safe fallback.
- B-15: The companion logs mobile-specific telemetry such as screen load time, network transitions, push receipt, and command-draft outcomes, with privacy controls and redaction.

### Business Rules

- BR-1: The mobile companion is a presentation and notification client. It does not own authoritative project, portfolio, run, stage, gate, auto-mode, or command state.
- BR-2: Every mutating action initiated from mobile must be routed through the manual command surface of F-6, including HIL gate decisions, pause/resume/cancel, retry, skip, parameter overrides, and auto-mode kill switch.
- BR-3: High-risk actions require re-authentication or step-up confirmation even if the operator has a valid session.
- BR-4: Push notification payloads must not contain sensitive pipeline content, secrets, model prompts, customer data, or raw logs. They may contain opaque identifiers and safe summary text.
- BR-5: Offline mode is read-only for authoritative state. Command drafts may be queued locally but must be clearly marked as unsent and must be reviewed after reconnect.
- BR-6: A revoked device loses access immediately on next network check and must be remotely wiped according to policy.
- BR-7: Notification preferences are per operator and may be constrained by administrator policy. Critical classes may be non-disableable where policy requires.
- BR-8: Mobile search and filters must respect the operator’s authorization scope. Results outside scope are not returned, not merely hidden.
- BR-9: Deep links must not bypass authentication or authorization. If the operator lacks access, the companion shows a non-sensitive access-denied state.
- BR-10: The companion must fail closed for command drafting: if the target state, authorization, or required parameters cannot be verified, it blocks the draft and explains the missing prerequisite.

### Validation

- V-1: Authentication input validates required credentials, rejects expired or revoked sessions, and enforces lockout or rate-limit policy after repeated failures.
- V-2: Device registration validates device identifier format, platform, app version, and push token. Duplicate or conflicting registrations are reconciled according to device policy.
- V-3: Notification preference input validates that selected classes are permitted for the operator’s role and that quiet hours are well-formed (start < end or overnight format).
- V-4: Command draft validation checks target existence, target authorization, required parameters, parameter ranges, and idempotency key when supplied.
- V-5: HIL gate decision validation checks that the gate is still pending, the operator has gate-decide permission, the required note is present when policy demands it, and the decision is one of the allowed outcomes.
- V-6: Search and filter input validates that date ranges are coherent, status values are known, and portfolio/project identifiers are authorized.
- V-7: Deep link validation checks link signature or token where used, target existence, target authorization, and expiry.
- V-8: Offline draft validation re-runs on reconnect, because permissions, run state, or gate status may have changed while offline.

### Edge Cases

- EC-1: The operator is authenticated but the device has been revoked elsewhere. The next network check forces sign-out and wipe.
- EC-2: The operator opens a HIL gate notification, but the gate was already decided by another operator. The companion shows the current decision and disables duplicate submission.
- EC-3: The operator drafts a pause command while offline, and the run completes before reconnect. The queued draft is marked stale and cannot be submitted without explicit review.
- EC-4: Real-time updates disconnect mid-session. The companion shows a degraded connection indicator, falls back to polling, and resumes real-time when available.
- EC-5: A push notification arrives for a run the operator no longer has access to. Opening it shows an access-denied recovery state, not run details.
- EC-6: The device has low storage or the cache is corrupted. The companion clears only its own cache, preserves drafts if possible, and requires a fresh authenticated sync.
- EC-7: The operator changes locale or timezone while the app is open. Dates, times, and numbers update without losing current navigation state.
- EC-8: A portfolio roll-up contains thousands of projects. The companion paginates, virtualizes lists, and avoids loading all child runs at once.
- EC-9: A command draft is submitted twice because of network retry. Idempotency handling prevents duplicate execution.
- EC-10: Auto-mode policy changes while the operator is viewing it. The companion shows a stale-state warning and offers refresh before any kill-switch or override draft.

### Error Handling

- EH-1: Authentication failure shows a non-sensitive inline error and does not reveal whether a username, device, or token was the failing factor.
- EH-2: Authorization failure shows a clear access-denied message with a safe recovery action, such as returning to home or requesting access.
- EH-3: Network failure shows a persistent offline or degraded banner and preserves the current view with cached data where available.
- EH-4: Server 5xx errors show a friendly error state with retry and support-bundle options; no raw stack traces are exposed.
- EH-5: Rate limiting shows a retry-after message and disables repeated submission until the window clears.
- EH-6: Conflict errors from F-6 or F-3 show the current authoritative state and explain why the command could not be applied.
- EH-7: Push registration failure shows a non-blocking warning and prompts the operator to check system notification settings.
- EH-8: Cache read failure falls back to network fetch; if network is unavailable, the companion shows an empty offline state with retry.
- EH-9: Deep link target missing shows a recovery page with search and home options.
- EH-10: Support bundle generation failure shows an error identifier and a retry option without exposing sensitive diagnostic content.

### Acceptance Criteria

- AC-1: An operator can authenticate on a supported phone, establish a device-bound session, and reach the mobile dashboard home.
- AC-2: The mobile dashboard home shows active runs, waiting HIL gates, recent failures, and portfolio exceptions for the operator’s authorized scope.
- AC-3: An operator can open a project, portfolio, run, stage, and HIL gate from mobile and see authoritative state consistent with the dashboard.
- AC-4: A pending HIL gate can be reviewed on mobile with context, evidence, and impact; the decision is submitted only through F-6 and the result is reflected after completion.
- AC-5: A run update appears in the foregrounded mobile view through real-time updates, and a push notification is delivered for configured event classes.
- AC-6: An operator can change notification preferences and quiet hours, and the companion respects those settings for subsequent notifications.
- AC-7: With network disabled, the operator can review last-known project/run/gate state and sees a persistent offline indicator.
- AC-8: With network disabled, a command draft can be created, is marked unsent, and is validated again on reconnect before submission.
- AC-9: A revoked device is signed out and wiped according to policy on the next network check.
- AC-10: A deep link from a push notification opens the correct authorized mobile view or a safe access-denied recovery state.
- AC-11: Screen-reader traversal, dynamic type, and high-contrast checks pass for the mobile dashboard, run detail, gate review, and settings screens.
- AC-12: Auto-mode and multi-project run-group summaries are visible on mobile, and kill-switch/override actions route through F-6 with step-up confirmation.
- AC-13: Push payloads contain no sensitive run content, raw logs, secrets, or customer data.
- AC-14: The mobile companion meets performance targets for cold start, dashboard render, interaction response, and list scrolling on mid-tier devices.
- AC-15: The companion degrades gracefully when real-time updates, push, AI services, or network connectivity are unavailable, without blocking read-only review.

### API Behaviour

- API-1: `POST /mobile/session` — authenticates the operator, returns a device-bound session token, expiry, device registration state, and required step-up policy. Idempotency is not required.
- API-2: `POST /mobile/devices` — registers or updates a device with platform, app version, push token, and device public key material. Returns device ID, registration status, and wipe state.
- API-3: `DELETE /mobile/devices/{deviceId}` — revokes the device and requests remote wipe. Returns revocation timestamp and wipe status.
- API-4: `GET /mobile/dashboard` — returns the mobile home model: active runs, waiting gates, recent failures, auto-mode escalations, portfolio exceptions, and last-updated timestamp. Supports scope filtering by role and authorization.
- API-5: `GET /mobile/projects`, `GET /mobile/projects/{projectId}`, `GET /mobile/portfolios`, `GET /mobile/portfolios/{portfolioId}` — return paginated mobile summaries and detail views for projects and portfolios, including run counts by status, gate backlog, failure counts, and last activity.
- API-6: `GET /mobile/runs/{runId}` and `GET /mobile/runs/{runId}/stages` — return run state, stage timeline, telemetry summaries, failure reasons, and gate references. Pagination is supported for stage and event lists.
- API-7: `GET /mobile/gates`, `GET /mobile/gates/{gateId}` — return pending and recent HIL gates with context, evidence, deadline, allowed decisions, and required note policy.
- API-8: `POST /mobile/command-drafts` — accepts a command draft from the mobile companion and returns a draft ID, validation result, preview, and handoff token for F-6. This endpoint does not execute the command.
- API-9: `GET /mobile/notifications/preferences` and `PUT /mobile/notifications/preferences` — read and update notification classes, quiet hours, critical overrides, and digest settings.
- API-10: `POST /mobile/support-bundle` — requests a redacted support bundle; returns a bundle ID, status, and download reference when ready.
- API-11: `GET /mobile/search` — searches authorized projects, portfolios, runs, stages, gates, and own drafts with filters and pagination.
- API-12: `GET /mobile/resolve-link` — resolves a deep link token or path to an authorized mobile route, or returns a safe fallback route with reason.
- API-13: All mobile API responses include an authorization scope indicator, a last-updated timestamp, and a consistency marker. Mutating endpoints are not exposed on the mobile companion; they are proxied through F-6 draft and confirmation contracts.
- API-14: Error responses use stable machine-readable codes for unauthenticated, forbidden, not-found, conflict, rate-limited, validation-failed, and dependency-unavailable conditions. Error bodies never include secrets, raw logs, or internal stack traces.

### Priority

- Must-have: FR-251, FR-252, FR-253, FR-254, FR-255, FR-256, FR-259, FR-262, FR-263.
- Should-have: FR-257, FR-258, FR-260, FR-261, FR-264, FR-265.
- Nice-to-have: none in this feature specification; all listed requirements are within F-11 scope.
