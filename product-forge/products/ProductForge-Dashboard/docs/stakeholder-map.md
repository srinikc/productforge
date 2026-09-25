## Stakeholder Map

**What is the first-release scope, and which capabilities are non-negotiable for MVP?**
Prioritize project creation, model-tier selection/customization, multi-project portfolio view, agent orchestration controls, and real-time pipeline monitoring/logging. Defer mobile, voice-enabled chat companion, and advanced auto mode until the core dashboard is stable.

**What deployment and backend/API boundary should the dashboard use?**
Use a separate dashboard frontend, deployable on a public platform such as Vercel, communicating with the existing Product Forge backend through authenticated APIs. Reuse pipeline APIs where possible and add dashboard-specific aggregation, orchestration, and notification endpoints.

**What authentication, authorization, and data-isolation model is required?**
Support user accounts with workspace/project-level roles, project-level permissions, secure API authentication, audit logging, and protection of model/provider credentials. Design the data model so multiple projects and users cannot access one another's data.

**What should be included in the first releasable MVP, given that the concept spans full portfolio orchestration, model-tier customization, mobile, voice, chat, APIs, and deployment?**
Use F-1 through F-5 plus auto-mode as the launch scope: an authenticated web dashboard for project creation, model tiers, portfolio/status, run controls, and live logs. Defer native mobile, wake-word/STT/TTS, full conversational control, and a broad external API catalog until the core control plane is proven.

**Who is the initial deployment context: a private single-user/small-team tool, or a multi-tenant SaaS product with public access and strict tenant isolation?**
Start as a private, authenticated single-tenant or small-team deployment, with clear project and operation permissions and an easy self-hosted/backend-plus-frontend option. Treat public hosting/Vercel and multi-tenant isolation as later phases, not launch blockers.

**What pipeline modules and APIs already exist, and which system should be the source of truth for project, agent, run, and log state?**
Treat the existing pipeline as the source of truth. Reuse its APIs for execution and state, and add dashboard-specific read/query/orchestration APIs plus a stable event/status contract; avoid duplicating pipeline state in the dashboard.

**What is the minimum viable release boundary, and which capabilities are true release blockers?**
Treat F-1 through F-5 as the core, include a constrained auto-mode run with start/stop/cancel and streamed logs in v1, deliver responsive web/mobile-web support, and defer native mobile, voice-enabled chat, broad public APIs, and advanced customization beyond the required model-tier workflow.

**Is the first deployment a single-tenant internal dashboard or a multi-tenant team product?**
Assume one organization/workspace for the first release, with admin/operator roles, audit logging, and idempotent controls; defer SSO, team isolation, and external sharing.

**What is the integration and deployment boundary between the dashboard and the existing pipeline backend?**
Use the existing backend/orchestrator as the source of truth; the dashboard should consume existing pipeline APIs and add only dashboard-specific endpoints. Support a Vercel-hosted frontend with a configurable backend, with same-origin deployment available later.

