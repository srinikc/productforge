# AGENTS.md — ProductForge-Dashboard

> Project-wide rules for ALL agents. Generated at run start.

## Purpose
Dashboard that is the face of the Product Forge pipeline (multi-agent, multi-project) — all operations happen through this dashboard UI.

Scope: handle ALL operations/inputs/configs/customization and everything else in the pipeline, made available and orchestrated through the dashboard. This is the one-stop solution showing proper status of projects/operations/agents.

Core capabilities:
- Create a new project with an idea; provide/select model tiers, customize a tier, or create a new tier from the list of LLM models and providers.
- Initiate project creation and the E2E workflow per the pipeline in the backend; monitor/track/provide inputs and control operations from the agent and orchestrator point of view.
- Portfolio: multiple projects; run multi-project simultaneously and manage E2E for each running project; create multi-project runs going through all defined agents.
- Everything that is interactive today (inputs/selection/outputs) in the pipeline must be managed through good UI dialogs/windows, well orchestrated in the UI and workflow.
- Top-notch UI/UX: themes/components for lists, windows, dialogs, checkboxes, popups, notifications, alerts, text boxes/entry boxes, etc. Well-orchestrated dashboard to create/manage a portfolio of projects through the UI.
- Global AI chat companion that understands the entire portfolio and projects, plus dashboard operations/control, queryable and orchestratable via chat. Build it with voice support (TTS/STT), English for now, with a wake word like Alexa. Active only when enabled and when the dashboard is up/focused/open.
- Mobile app for the dashboard complementing the web dashboard — design/implement the workflows feasible/needed on mobile.
- Tests: high quality across test types (functional, non-functional, security, others), written and managed through our test framework for design/creation/execution/results reporting and issue tracking of the dashboard.
- Dashboard UI components/pages for ALL features/config implemented in the pipeline — go through the features/modules we have implemented.
- Voice support: refer to the mymoney project at C:\Users\ADMIN\Documents\Srinikc\AI Products\mymoney.
- Deployable from public sites (e.g. Vercel) talking to the pipeline backend; support backend and dashboard at one place or separate; implement deployment options for this.
- API-first: anyone can call APIs to get relevant info and show it in a customized app. Analyze and decide whether we need all APIs in the dashboard or can reuse the pipeline APIs plus only the additional ones the dashboard needs; design/implement what is required.
- Auto mode: the pipeline can create a new project with auto mode that runs the entire pipeline automatically without human inputs — orchestrate this workflow in the UI and show pipeline logs as they execute.

## Tech stack (MUST follow docs/tech-stack.json)
- kind: 
- languages: []
- frameworks: []
- database: 

## Conventions
- No mocks, stubs, TODOs, or placeholders.
- Write real files (write_file); run tests before declaring done.
- Follow docs/CONSTITUTION.md and docs/guidelines.

## Verification / Definition of Done
- `validate` must actually run the test suite and report real results.
- Compliance must pass: no-mock gate, knowledge, architecture completeness, no secrets.
