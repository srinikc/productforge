## Domain Analysis

**What should be included in the first MVP, and what can be deferred?**
Ship the web dashboard MVP first: project creation, model-tier selection/customization, portfolio view, per-project status/logs, manual run controls, and auto mode. Defer voice, mobile, and the full AI chat companion until the core dashboard is stable.

**What pipeline APIs and backend capabilities already exist that the dashboard must orchestrate?**
Treat the existing Product Forge pipeline as the source of truth. Reuse its project, agent, model, run, and log APIs wherever possible, and add only dashboard-specific APIs for authentication, notifications, and UI orchestration.

**What deployment, security, and real-time requirements should guide the architecture?**
Start with a separate public web frontend and private backend API, deploy the frontend to a platform such as Vercel, secure all dashboard APIs with authentication, and use WebSocket or Server-Sent Events for real-time project status and logs.

**Should the dashboard be deployed as a standalone SPA (e.g., on Vercel) that consumes the existing pipeline APIs, or do we need a tightly coupled backend/frontend monolith deployed together?**
Deploy as a standalone SPA (e.g., Vercel) consuming the pipeline APIs via an API‑first approach; keep backend and dashboard separate for scalability and independent releases.

**For mobile support, should we build dedicated native iOS/Android apps or start with a responsive web/PWA that reuses the dashboard UI?**
Start with a responsive web/PWA that adapts to mobile devices; this satisfies the mobile companion requirement while minimizing effort, with native apps considered later if needed.

**Regarding the AI chat companion, should we implement full wake‑word voice (STT/TTS) support now, or begin with a text‑based chat interface and add voice later as a nice‑to‑have?**
Begin with a text‑based chat companion; voice (wake‑word, STT/TTS) can be added later as an optional enhancement once the core dashboard is stable.

**What authentication and authorization strategy will be employed for the dashboard (e.g., OAuth2/OIDC, JWT, role-based access control) and will it support multi-tenant isolation?**
Adopt OAuth2/OpenID Connect with JWT tokens and role-based access (Viewer, Builder, Admin) to secure dashboard and API endpoints.

**Will the dashboard expose internal pipeline APIs directly to clients, or will there be an API gateway/service mesh handling authentication, rate limiting, input validation, and encryption?**
Place an API gateway (e.g., Kong, AWS API Gateway) in front of all backend services, enforce HTTPS, JWT validation, rate limiting, and sanitize inputs to mitigate OWASP risks.

**What accessibility standards (WCAG level) will the UI target, and have we planned for keyboard navigation, ARIA labeling, screen‑reader support, and sufficient color contrast for all components including dialogs, notifications, and the voice‑enabled chat companion?**
Target WCAG 2.1 AA compliance: use semantic HTML, ARIA roles/labels, ensure full keyboard operability, provide text alternatives for audio, and maintain contrast ratio ≥4.5:1 for text.

**Which technology stack should we use for the dashboard frontend and its backend API (if separate)?**
Use React with TypeScript for the frontend (leveraging a component library like Ant Design or Material‑UI) and a Python FastAPI backend to reuse existing pipeline services and keep the stack consistent with the rest of the Forge.

**For the voice‑enabled AI chat companion, which STT/TTS and wake‑word solutions should we integrate?**
Start with the browser Web Speech API for STT/TTS (zero‑cost, works in Chrome/Edge/Firefox) and add Porcupine for wake‑word detection; optionally allow fallback to Azure Cognitive Services or Google Cloud for higher accuracy when online.

**How should we deliver the mobile companion – as a cross‑platform hybrid app, a PWA, or separate native builds?**
Build a cross‑platform React Native app that shares UI components with the web dashboard (via React Native for Web) and optionally package it as a PWA for browsers, giving a single codebase while still supporting native device features.

**Which frontend framework and UI component library will be used to build the dashboard (e.g., React/Vue/Angular with Ant Design, Material-UI, etc.)?**
Use React with TypeScript and Ant Design (or Material-UI) for a rich, themeable component set and strong ecosystem support.

**Will the dashboard consume only the existing pipeline backend APIs, or will it require additional dashboard‑specific APIs (e.g., for UI state, chat companion, project metadata)?**
Reuse the pipeline APIs wherever possible and add a thin dashboard‑specific API layer for UI‑centric operations (preferences, chat sessions) to keep the backend clean.

**How will voice wake‑word detection and TTS/STT be implemented (client‑side Web Speech API vs third‑party service, specific libraries)?**
Leverage the browser Web Speech API for STT/TTS and an open‑source wake‑word engine like Porcupine for client‑side wake‑word detection, ensuring privacy and offline capability.

**What is the exact v1 release boundary: which capabilities are required for the first production release, and what must be deferred?**
Define v1 as the web dashboard MVP covering project creation/configuration, model-tier management, portfolio view, pipeline start/stop controls, real-time status, and logs. Defer the mobile companion, wake-word voice/TTS/STT, global chat companion, auto mode, and custom public-site deployment patterns. Require 100% traceability for v1 must-haves, passing functional/API/integration/security/accessibility tests, no open Sev-1/Sev-2 defects, and successful deploy/smoke validation before release.

**Who can access portfolio data and operations, and what is the authoritative state and API boundary between the dashboard and pipeline backend?**
Assume authenticated SSO/OAuth with RBAC roles such as owner, admin, member, and viewer; enforce project-level isolation and audit all privileged actions. The backend should own project, run, agent, and log state and validate every mutation; the dashboard should consume existing pipeline APIs and add only dashboard-specific orchestration endpoints. Add API contract tests, authorization tests, and secret-handling checks so frontend actions cannot bypass backend enforcement.

**What scale, latency, availability, and deployment targets should define production readiness?**
Use provisional targets of 100 concurrent users, 100 projects, 20 concurrent pipeline runs, real-time status updates within 5 seconds, dashboard read p95 under 500 ms, action acknowledgement p95 under 2 seconds, and 99.9% backend API availability. Support separate dashboard/backend deployment with a same-origin production option; gate release on load, stress, resilience, logging-volume, accessibility, and security-performance testing.

**Should the first production release use a hosted, separately deployable dashboard/API/worker architecture, or a single/self-hosted deployment?**
Use a hosted SaaS default: deploy the static dashboard on Vercel, run the API and durable pipeline workers in a managed cloud region, and use managed database, object-storage, and queue services. Package them separately and configure dev, staging, and production environments; add self-hosting later.

**What access and tenancy model must be enforced for users and API clients?**
Use authenticated multi-tenant accounts with a workspace/project hierarchy, role-based permissions, invite-based users, project-scoped API tokens, and MFA/SSO for administrators. Keep every control and data API project-scoped and audit all changes.

**Which privacy, retention, and voice requirements are mandatory for the first release?**
Treat prompts, logs, outputs, and credentials as sensitive: encrypt in transit and at rest, use provider allowlists and secret management, configure retention and backups, and publish an audit trail. Ship text chat in the MVP and defer wake-word/continuous STT/TTS until latency, privacy, and cost requirements are approved.

**What should be included in the first release versus deferred to later phases?**
Release the web portfolio dashboard, project creation, model-tier configuration, orchestration controls, real-time monitoring/logs, and notifications. Defer voice support, a separate mobile app, chat-companion orchestration, and third-party API customization to later phases; keep auto mode as an early capability if backend automation already exists.

**What is the intended primary audience and access model?**
Target AI product builders and technical operators managing multiple projects. Use role-based access with authenticated individual accounts, team membership, and project-level permissions; initially support one owner/admin and collaborators rather than complex organizational roles.

**What architecture and API model should documentation assume?**
Treat the existing pipeline as the system of record and expose its capabilities through REST/JSON APIs with OpenAPI documentation. Keep the web dashboard as a separate frontend deployed on a platform such as Vercel, communicating with a centrally hosted backend; add only dashboard-specific endpoints for notifications, activity feeds, and companion state.

**For v1, should the mobile app be delivered as native iOS/Android packages, a responsive web/PWA, or both?**
Use native iOS and Android packages plus a responsive web/PWA fallback; defer desktop installers.

**Should the dashboard and pipeline backend be packaged and deployed as separate artifacts or as one combined product?**
Support separate static dashboard and containerized backend as the primary model, with a combined self-hosted bundle/archive as an additional option.

**Which runtime, platform, signing, and software-compliance requirements must the release artifacts satisfy?**
Target browser clients, Node.js LTS backend, and OCI/Docker containers; generate an SBOM and license inventory, run dependency vulnerability/license scans, document supported platforms, and sign release artifacts.

**Should the dashboard be the exclusive human entry point for pipeline operations, or should existing CLI/API workflows remain supported?**
Make it the primary human control plane for supported operations while preserving backend APIs and CLI/automation access; the backend remains the source of truth.

**What should be included in the first releasable MVP versus the full dashboard vision?**
Ship portfolio overview, project creation/configuration, model-tier selection/customization, run start/pause/stop/cancel, stage status and logs, and basic auto-run; defer native mobile, voice companion, and exhaustive migration of every existing interaction until the core flows are stable.

**What is the preferred initial deployment and access model?**
Use a web-first responsive dashboard deployed on Vercel with a separate pipeline backend/API, shared authentication, initial single-organization/team support with role-based access, and API keys/OAuth for integrations; add native mobile and broader multi-tenancy later.

**Who will be allowed to access the dashboard and pipeline APIs, and what deployment boundary is required?**
Assume a private, authenticated product with organization-level tenants. Require SSO/OIDC, role-based access control, tenant isolation, and a separate backend/dashboard deployment. Do not expose unauthenticated or public write APIs.

**What types of data will projects, prompts, logs, and uploads contain, and what retention or privacy obligations apply?**
Treat all pipeline data as confidential by default. Encrypt data in transit and at rest, use approved providers with no-training settings, keep secrets out of prompts and UI, minimize and redact logs, and define retention and deletion policies before enabling regulated data.

**Which dashboard actions and auto-mode operations require approval, audit, or safeguards?**
Require explicit approval for destructive, expensive, external, or production-affecting actions. Audit all control and API events, use least privilege, idempotency, rate limits, circuit breakers, and human confirmation for voice-controlled or critical pipeline operations.

**What FinOps outcomes must the dashboard guarantee: cost attribution, budget control, forecasting, anomaly detection, or chargeback?**
Start with per-project, per-agent, and per-model-tier cost attribution, budget alerts, and auto-mode cost caps. Defer chargeback and advanced forecasting until usage data is reliable.

**Is the dashboard intended for one internal team or multiple external customers, and who owns the cloud and LLM-provider spend?**
Treat the first release as an internal single-tenant dashboard. The backend should own cost accounting and billing integration; the dashboard should provide read-only visibility and limited operational controls.

**What cost telemetry, latency, and retention are available from the pipeline backend and LLM providers?**
Instrument costs at operation, agent, and model-invocation level; aggregate every few minutes, retain at least 90 days of detailed data, archive longer-term summaries, and reconcile provider invoices monthly.

**What measurable success criteria (product goals / KPIs) should define a successful v1 — e.g., share of pipeline operations performed via dashboard vs CLI, time-to-first-project, reduction in stalled runs awaiting input, chat/voice companion adoption?**
v1 succeeds if: ≥80% of routine pipeline operations (create/run/monitor/input) are done via the dashboard, time-to-first-running-project <10 minutes, stalled runs awaiting human input reduced vs baseline, and the AI companion is used at least weekly by the primary operator. Defer vanity metrics like DAU.

**When scope or UX trade-offs arise, how should we prioritize the personas — confirm Priya (Portfolio Operator) as the primary persona, Marco (API/integrator) as secondary, and Sam (mobile supervisor) as tertiary for v1?**
Confirm Priya as the decisive persona for all v1 trade-offs (portfolio clarity, steerable runs, human-input dialogs); Marco's API-first needs are a close secondary since they're cheap to uphold; Sam's mobile needs are limited to monitoring + input/approval, deferring heavy mobile workflows to later phases.

**What is the intended business goal of this product for v1 and beyond — internal enablement tool for the Product Forge pipeline, or a productized offering (internal-team SaaS or externally sellable dashboard) that pricing/monetization strategy must eventually cover?**
Treat v1 as an internal-first control plane that must not block later productization: no pricing/billing in v1, but keep tenancy, usage/cost telemetry, and API surfaces clean enough that a pricing-strategist can later model tiers (seat, usage/token, or portfolio-scale pricing) without a rewrite.

**For v1, does marketing own an internal adoption/rollout deliverable (launch announcement, onboarding tour copy, short demo, training/README) to drive Priya's and Sam's switch from CLI to dashboard, or does marketing activity start only after the release ships?**
Include a lightweight internal launch kit in v1 scope — in-product onboarding tour, README/getting-started page, and a short demo — and defer broader enablement campaigns (workshops, email sequences) to post-launch.

**Since the API-first surface (Marco, the Builder-Integrator) is a core pillar, should v1 include public-facing API documentation/developer landing page as a marketing deliverable, or are internal-only docs sufficient for launch?**
Ship internal API docs as part of v1; defer the public developer portal/landing page to a later phase until the API contract is proven with internal users.

**Should the dashboard carry its own product name/brand identity distinct from 'Product Forge' (e.g., a standalone landing/messaging identity for future external positioning), or does it simply ship under the existing Product Forge brand with no separate branding work in v1?**
Ship under the existing Product Forge brand with no separate naming or branding effort in v1; revisit standalone positioning only if the business-goal decision later productizes the dashboard.

**How will new users be activated — should v1 ship a seeded demo/starter project plus a guided first-run tour (empty-state CTA → idea → tier → auto-mode kick-off) so a new Priya reaches a completed first run without reading the CLI README?**
Yes — include a one-click starter project template and a 5-step onboarding tour in v1; this is the activation lever that converts existing CLI users to the dashboard.

**Should v1 include an out-of-band notification channel (email, Slack/webhook, or push) that fires when a run needs input or fails — since the dashboard/voice companion is only active when the tab is open, retention depends on reaching users when they are away (Sam's core loop)?**
Yes — at least one notification channel (email or Slack webhook) is a v1 requirement; without it, runs stall and the dashboard loses its primary retention trigger.

**For referral/advocacy, should v1 include any shareable growth artifact (e.g., a read-only portfolio/run-summary share link or public project showcase) to fuel word-of-mouth among pipeline users, or is advocacy limited to organic word-of-mouth from API docs and demos?**
Defer public showcases — v1 advocacy relies on the marketing deliverables (demo, announcement, API docs); add a shareable read-only run-summary link in v2 as a low-cost growth loop.

**Existing pipeline users already have projects, runs, and tier configs created via CLI — must onboarding include importing/adopting that existing state into the dashboard (e.g., a 'your existing projects appear here' flow), or does onboarding only assume net-new users creating projects from scratch in the dashboard?**
Since the pipeline backend is the source of truth, existing projects/tiers created via CLI should automatically appear in the dashboard with no separate migration step — onboarding should just recognize portfolio-empty vs portfolio-populated states and tailor the first-run guidance accordingly (skip the create-project tour if projects already exist).

**Does first-run onboarding need a guided setup step for backend/LLM provider credentials (API keys, provider config) before a user can create their first project, or are those assumed pre-configured on the pipeline backend outside the dashboard?**
Assume credentials are pre-configured on the backend for MVP; the onboarding flow's first-run wizard should only cover idea → tier preset → run mode, with a non-blocking 'check backend connection/keys' status indicator rather than a full key-management wizard (defer key management UI to a later phase).

**What in-app onboarding/help surfaces must v1 ship — contextual empty-state guidance and inline tooltips, a dismissible guided tour, an in-app help/docs panel, or a feedback/support channel — and which are launch blockers vs post-launch?**
V1 launch blockers: rich empty-state CTAs with inline hints on every page plus a dismissible first-run tour of the core loop (create → run → respond to input); defer a full in-app help center, video walkthroughs, and feedback widget to post-launch, linking out to external docs instead.

**Should the AI companion be built on an emerging agent-interop standard (e.g., Model Context Protocol / tool-calling registry) so its 'understands the whole portfolio and can orchestrate dashboard operations' capability is powered by a standard tool layer rather than bespoke hardcoded intents — making it extensible as new pipeline modules appear?**
Yes — expose pipeline operations as MCP-style tools registered from the existing API surface; this is the fastest emerging-trend path to a companion that stays in sync with new features without custom NLU per operation.

**Should we benchmark and adopt proven observability UX patterns from leading agent-ops tools (LangSmith, Arize/Phoenix, Temporal UI) — specifically a per-run trace timeline with agent-span drill-down, token/cost waterfall, and replayable step history — as the target pattern for our project/run detail views?**
Yes — these patterns are becoming the de-facto expectation for multi-agent dashboards; adopting the trace-timeline + cost-waterfall pattern in v1 differentiates us from raw-log viewers and matches what Priya/Marco already recognize from other tools.

**For real-time portfolio status and streaming pipeline logs, should we scout and standardize on SSE (Server-Sent Events) for dashboard log/status streams, reserving WebSocket only for bidirectional chat/voice — given SSE's resilience through proxies (Vercel, CDNs) and simpler one-way log streaming?**
Yes — SSE for logs/status (retry-friendly, works on static-hosted SPAs behind CDNs) and WebSocket (or WebRTC for voice) only for the chat companion; this split is the pragmatic emerging pattern for deployable dashboards talking to a separate pipeline backend.

**When the product becomes revenue-generating, what pricing model should underpin it: seat-based subscription, usage-based pricing (metered per pipeline run / LLM tokens), or a hybrid (platform fee + usage overage)?**
Hybrid: a per-seat platform subscription for dashboard/API access plus metered usage for pipeline runs (passed-through or marked-up LLM/compute cost), because run cost varies widely by model tier and seat count alone fails to recover variable LLM spend.

**Should v1 (even if internal/unpriced) ship metering instrumentation — per-run and per-tenant usage counters, model-tier cost attribution, and budget-cap events — so unit economics can be measured from day one rather than retrofitted later?**
Yes: v1 must emit per-run/per-tenant usage and cost telemetry in a stable, queryable format (telemetry only, no billing UI), since retrofitting metering onto an existing pipeline is expensive and pricing/packaging decisions need real unit-cost data within the first release cycle.

**For packaging, should API access be a separate priced SKU (like Marco's integrator tier), or bundled with dashboard seats where differentiation is only rate limits and support level?**
Bundle API access with the same tiers and differentiate only by rate limits, quotas, and support SLA in v1–v2 — pricing API separately too early fragments the offering and suppresses Marco's integration adoption, which is the main growth channel.

**What is the v1 support operating model for dashboard users: which channel do users report issues or get help through (in-app feedback form, Slack/email, issue tracker), who triages it, and what response/escalation targets apply when a run failure or dashboard bug is reported — especially since this support intake should feed the existing test/issue-tracking framework?**
Ship a lightweight in-app 'Report an issue / Get help' entry that captures user, project, run ID, and logs and files directly into our existing test/issue-tracking framework, with the Customer Success Lead triaging within one business day and escalating pipeline-level failures to the pipeline engineering owner.

**What customer-health signals should Customer Success monitor from day one to catch at-risk users and stalled adoption (e.g., zero dashboard logins after onboarding, runs stalled awaiting input beyond a threshold, repeated failed runs, no project created in first N days), and what outreach playbook triggers when a user's health score drops?**
Define a simple health score tracked weekly: activated (first completed run within 7 days), weekly active operators, count/duration of stalled runs, and failed-run rate — with the CS lead personally reaching out within 48 hours of a stalled-run or activation threshold breach.

**What user-lifecycle management must v1 support for retention and offboarding — team-member invitation, role changes, deprovisioning (revoke dashboard sessions and API keys immediately when a user leaves), and account/project data handling on departure — beyond the access/tenancy model already decided?**
v1 includes admin invite + role change (admin/operator/viewer) with one-click deprovision that revokes sessions and API keys and logs the action to an audit trail; data deletion/export requests are handled manually by the CS lead until volume justifies automation.

**What community channel (e.g., dedicated Slack/Discord workspace, existing team channel, or discussion forum) should v1 establish as the home for dashboard users to ask questions, share results, and report feedback — and is opening it a launch blocker or post-launch?**
Launch blocker as a lightweight channel: reuse an existing internal Slack/Teams channel for v1 rather than spinning up a new Discord/community platform; formalize a dedicated public community space only when/if the dashboard becomes an externally sold product.

**What social-proof and shareable content should be produced at launch (e.g., announcement post, demo GIF/video of a portfolio run, user testimonial from an existing CLI user, public changelog/release-notes feed) and who owns creating it — should marketing commit to a fixed launch-content package for v1?**
Yes — commit to a minimal launch-content package owned by marketing: one internal launch announcement with a short demo GIF of a live run, plus a public changelog/release-notes feed; defer testimonials and external social posts until real users have adopted the dashboard.

**Should v1 seed an early-adopter/evangelist cohort (recruit 3-5 existing pipeline CLI users to trial the dashboard, give feedback, and act as internal advocates during rollout) or does adoption rely purely on organic discovery of the dashboard?**
Yes — recruit a small early-adopter cohort of existing CLI users pre-launch; their feedback de-risks v1 and their advocacy is the most credible driver of the CLI-to-dashboard switch among Priya and Sam personas.

**Which CRM system of record and sales pipeline stages should we configure to track this dashboard product from first touch to close (e.g., Discovery → Demo → Pilot → Closed Won), and are we adding this as a new pipeline/product line in the existing CRM or standing up new objects (products, quotes, licenses)?**
Reuse the existing company CRM (create a 'Product Forge Dashboard' product line with stages: Sourced → Discovery → Demo → Pilot/POC → Proposal/Quote → Closed Won/Lost); only create a new CRM instance if none exists, in which case HubSpot with these same stages.

**What is the initial ICP and sales motion for v1 — outbound-led (we prospect named accounts), inbound-led (API docs and launch content drive signups), or product-led (self-serve signup with sales only for larger/team deals) — and who is the economic buyer we build the pitch and qualification criteria around?**
Product-led with sales-assist: self-serve dashboard/API access for individual operators, with sales engaging team/enterprise conversations; economic buyer is the engineering or product leader who owns AI-pipeline tooling budgets.

**What deal-desk rules must we define for v1 pricing execution — discount authority levels, approval path for pricing exceptions, standard contract terms (billing cycle, overage handling for usage-based fees), and pilot/POC terms (length, success criteria, conversion path)?**
Standard terms: annual billing with monthly usage overage billed in arrears, 30-day POC with agreed success criteria, discount authority capped at 10% for reps and anything above routed to leadership approval; start simple and formalize once first deals arrive.

**Which LLM providers will process user content (prompts, project ideas, logs, uploads), what contractual/data-processing terms must be in place with them (DPA, sub-processor list, no-training/no-retention commitments, data residency), and does any user content ever contain third-party confidential or personal data that triggers GDPR-style obligations?**
Use only provider API endpoints with no-training and short/no-retention data terms, sign a DPA with each provider, maintain a documented sub-processor list, and document in the privacy policy that content is sent to named LLM providers as processors. Assume prompts/projects may contain personal or confidential data, so apply minimization and encryption in transit/at rest by default.

**For the voice companion (wake word, STT, TTS): is audio processed entirely on-device/client-side, or streamed to a cloud STT service — and what are the requirements for audio retention, user consent/notice for ambient microphone capture, and whether any voice data could qualify as biometric/special-category data under applicable privacy law?**
Process wake-word detection and, where feasible, STT locally (Web Speech API / on-device models), never persist raw audio or voiceprints, show a clear visible+audible indicator whenever the mic is active, and include a one-line consent notice on first enable. This keeps voice out of biometric-data territory and avoids an audio-retention regime in v1.

**What is the IP/licensing posture for launch: (a) license policy for third-party OSS dependencies in the dashboard and voice stack (permissive-only vs copyleft), (b) ownership of pipeline-generated outputs and the dashboard's own code, and (c) what ToS/API terms must exist at release — even for internal v1 — covering acceptable API use, rate limits, and liability disclaimers for third parties calling the API-first surface?**
Adopt a permissive-only dependency policy (MIT/Apache-2.0/ISC; flag anything GPL/AGPL/EUPL for approval), state that pipeline outputs are owned by the customer/operator, and ship a lightweight internal ToS + API terms addendum covering acceptable use, rate limits, and 'as-is' disclaimer from day one — even if the v1 is internal/unpriced — since the API-first surface invites external callers.

**Does the existing pipeline backend emit a structured event/stream of run lifecycle transitions (run_started, agent_stage_changed, human_input_required, run_completed, run_failed, tokens_used), or must we build an event collection/instrumentation layer (e.g., a tracked events endpoint or telemetry store) before dashboard analytics can be reliable?**
The backend almost certainly does not emit a product-analytics event taxonomy today — assume we must define a canonical event schema (project/run/agent/user dimensions) and add a lightweight event ingestion endpoint or have the dashboard log events directly to an analytics store in v1, with the pipeline backend emitting run-lifecycle events as the primary source.

**Is there enough expected dashboard traffic (user count, run volume) to justify A/B testing / experimentation infrastructure in v1, or should experimentation be deferred in favor of descriptive metrics (funnels, adoption, latency) plus qualitative feedback?**
Defer formal experimentation infrastructure to post-v1. The initial audience is a small internal user base (Priya/Sam/Marco personas) — v1 should ship descriptive instrumentation only (event logging, dashboards, funnels), with no A/B framework until there is sufficient volume.

**Before we can claim 'reduction in stalled runs' or 'adoption vs CLI' as KPIs, do we need to capture a pre-launch baseline from current CLI usage (e.g., run counts, average time-to-completion, stall rate) — and can that data be derived today from existing pipeline logs/state, or must we instrument the CLI too?**
Yes — require a pre-launch baseline captured from existing pipeline run logs/state (run volume, completion time, stall/timeout rate, per-run token cost) for at least the last ~30 days before dashboard launch; instrumenting the CLI itself is unnecessary if run records already persist these fields, but we must confirm and document where that history lives before sprint 1.

