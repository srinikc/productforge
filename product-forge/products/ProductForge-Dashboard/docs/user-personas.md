## User Personas

**What is the primary delivery target for the dashboard (web-first responsive UI) and should the mobile companion be a separate native app or a progressive web app sharing the same codebase?**
Web-first responsive UI using a shared design system; mobile companion as a PWA / responsive view to leverage same design tokens and reduce duplication.

**How should the AI chat companion be integrated into the dashboard UI (persistent side panel, modal, or floating button) and under what conditions should voice wake word be active?**
Persistent collapsible side panel accessible via a header icon; voice wake word active only when the dashboard is focused and the companion is enabled, using the same design tokens for chat bubbles and voice indicators.

**Should the dashboard rely exclusively on existing pipeline APIs for all data and operations, or are additional dashboard‑specific aggregation APIs needed for portfolio overview, real‑time status, and chat companion orchestration?**
Reuse pipeline APIs where possible and add a thin dashboard‑specific aggregation layer (e.g., /dashboard/projects/summary, /dashboard/agent/status, /dashboard/chat) to avoid over‑fetching and to support UI‑only features like auto‑mode logs.

**Should the initial release (MVP) include all listed features, or should we prioritize the 'must-have' features (F1-F5) and defer the 'nice-to-have' items (F6-F9) to later phases?**
Prioritize the must-have features (project creation, multi‑portfolio view, agent orchestration, model tier selection, pipeline monitoring) for the MVP; treat nice‑to‑have features as future enhancements.

**For the AI chat companion, is it required to launch with full voice support (wake word, TTS/STT) or can we start with a text‑only chat and add voice capabilities later?**
Launch with a text‑only chat companion first; voice support (wake word, TTS/STT) can be added in a subsequent iteration.

**Is a separate native mobile application required, or can we meet mobile needs with a responsive web dashboard that adapts to touch interactions?**
Begin with a responsive web dashboard that works well on mobile browsers; evaluate the need for a native mobile app after validating core usage patterns.

**What tenancy, collaboration, and authorization model must the dashboard support in v1?**
Start with authenticated, single-user portfolios. Defer multi-team workspaces, role-based access, SSO, and project sharing until later.

**How mature is the existing backend API contract, and what canonical project lifecycle and auto-mode behavior must the dashboard expose?**
Keep the backend orchestrator as the source of truth, reuse pipeline APIs, add only dashboard-specific APIs, and use REST plus SSE/WebSocket for live status. Support Draft, Configured, Queued, Running, Blocked, Completed, Failed, and Canceled states; auto mode should pause when human input is required.

**Is the mobile requirement a native app, or can the web dashboard be delivered as a responsive PWA in v1?**
Deliver a mobile-optimized responsive PWA in v1 and defer a native mobile app until core dashboard workflows are validated.

**Who is the first production audience, and does v1 need multi-user, role-based access or only a single operator per dashboard?**
Start with AI product builders and developers managing multiple projects in one organization, with authenticated users and simple Owner/Admin/Operator roles from v1.

**What should be included in the first releasable MVP given the broad scope?**
Prioritize project creation, model-tier configuration, portfolio status, per-project orchestration controls, real-time logs/errors, and API-backed data; include a basic auto-run mode but defer native mobile and the full voice-enabled companion.

**Should the dashboard own pipeline execution, or should it act as an orchestration UI over the existing backend?**
Treat the existing pipeline backend as the source of truth for projects, agents, runs, logs, and model tiers; make the dashboard an API-first orchestration layer with separate deployable frontend/backend components.

