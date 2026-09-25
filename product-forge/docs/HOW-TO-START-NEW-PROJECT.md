# How to Start a New Project

Simple guide to use Product Forge pipeline for any new project.

---

## Step 1: Tell the Orchestrator

Say: **"Start new project: [your project name]"**

Example: "Start new project: taskmanager"

The orchestrator will:
1. Create project directory at `products/<name>/`
2. Initialize `pipeline.json`
3. Create `AGENTS.md` with your project rules
4. Start the pipeline

## Step 2: Ideation (Stage 0)

The ideation agent asks: **"What do you want to build?"**

Tell it:
- What the project does (one paragraph)
- Who uses it
- Key features (10-15 features)
- What's most important (P0 = must have, P1 = should have, P2 = nice to have)

Example: "I want a task manager app. Users can create tasks, set deadlines, get reminders. Features: login, dashboard, task list, calendar, notifications..."

The agent creates:
- `docs/product-plan.md` — your scope document
- `pipeline.json` — pipeline state

**You approve before moving to Step 3.**

## Step 3: Design (Stage 1)

The design agent creates:
- `docs/requirements.md` — all functional requirements (FRs)
- `docs/design.md` — UI/UX design, wireframes, components

**You review and approve before moving to Step 4.**

## Step 4: Architecture (Stage 2)

The architect agent creates:
- `docs/architecture.md` — tech stack, database schema, API design, all NFRs
- `docs/architecture.drawio` — architecture diagram

**You review and approve before moving to Step 5.**

## Step 5: Implementation (Stages 4-0 through 4d)

Implementation happens in phases:

**Stage 4-0: Skeleton**
- DB schema created (tables exist but empty)
- API endpoints created (return 501 for now)
- UI pages created (empty but routed)
- You see the full structure in browser

**Stage 4a: Phase 1 Features**
- Auth, Dashboard, Search, ToDo enabled
- Each feature: DB queries → API logic → business logic → UI
- Tests written in test framework
- Code review happens here
- **You test each feature in browser**

**Stage 4b: Phase 2 Features**
- Calendar, Goals, News, Health enabled
- Phase 1 features still work
- **You test everything again**

**Stage 4c: Phase 3 Features**
- Exploratory, Spiritual, Documents, Financial enabled
- Previous features still work

**Stage 4d: Phase 4 (Mobile)**
- React Native mobile app
- All screens work

## Step 6: Testing (Stage 5 + 10)

- Validate agent runs all tests from test framework
- Unit, API, DB, UI, security, performance tests
- Results shown in dashboard
- Issues logged with resolution details

## Step 7: Code Review (Stage 6)

- Code review agent checks every file
- Finds: stubs, TODOs, mock data, security issues, performance issues
- Issues sent to fix agent
- Fix agent fixes, code review re-checks

## Step 8: Documentation (Stage 8)

- User guide created
- API guide created
- Install guide created
- **You review before packaging**

## Step 9: Packaging (Stage 9)

Packages created for:
- Docker
- Windows (.msi)
- Linux Debian (.deb)
- Linux RPM (.rpm)
- macOS (.dmg)

Each package includes:
- Application files
- Install/uninstall scripts
- User guide
- API guide
- BOM (Bill of Materials)

**You approve before deployment.**

## Step 10: Deployment (Stage 11)

- Deploy to your choice: local, Docker, cloud, Vercel
- App verified working
- Sanity test passes

## Step 11: Done

- Final summary generated
- All features listed
- All test results shown
- Links to guides and dashboard
- **Pipeline asks: "Exit?"**

---

## Quick Reference

| What | Where |
|------|-------|
| Project rules | `docs/CONSTITUTION.md` |
| Project contract | `products/<name>/AGENTS.md` |
| Pipeline state | `products/<name>/pipeline.json` |
| Requirements | `products/<name>/docs/requirements.md` |
| Architecture | `products/<name>/docs/architecture.md` |
| Tests | `test-framework/tests/<name>/` |
| Test dashboard | `http://localhost:3011` |
| Pipeline dashboard | `http://localhost:8080` |
| Issues | `test-framework/defects/<name>/defects.json` |

---

## What Agents Do

| Agent | What It Does | Time |
|-------|-------------|------|
| ideation | Defines scope and features | 2-3 min |
| design | Creates requirements and UI/UX | 5-10 min |
| architect | Designs architecture and tech decisions | 5-10 min |
| implement | Writes working code | 15-30 min per phase |
| validate | Runs tests | 5-10 min |
| code-review | Reviews code quality | 5-10 min |
| fix | Fixes issues found | 5-15 min |
| document | Writes documentation | 5-10 min |
| package | Builds packages | 5-10 min |
| deploy | Deploys to environment | 5-10 min |

---

## Tips

1. **Be specific in ideation.** The more detail you give, the better the output.
2. **Review each stage carefully.** Don't rush approvals.
3. **Test features in browser** after each implementation phase.
4. **Check the dashboard** to see what's happening.
5. **Read the test results** before approving.

---

## Project Configuration (new options)

These fields go in `products/<project>/project.json` (all optional unless noted):

```json
{
  "idea": "One-paragraph product brief fed to Stage 0 ideation (or use idea.md)",
  "budget": {
    "currency": "USD",
    "soft_cost": 0.35,
    "hard_cost": 0.60,
    "soft_tokens": 500000,
    "hard_tokens": 800000,
    "variance_percent": 10
  },
  "implementation_iterations": "auto",
  "enable_delegation": false,
  "enable_tools": true,
  "auto_approve": false
}
```

| Field | Meaning |
|---|---|
| `idea` / `idea.md` | The product brief for Stage 0 (otherwise the agent invents one). |
| `budget.soft_cost` / `hard_cost` | Soft budget (warn/throttle at +variance) and hard ceiling (stop). |
| `budget.soft_tokens` / `hard_tokens` | Token ceilings (the run breaker enforces these). |
| `budget.variance_percent` | Accepted variance band (default 10%). |
| `implementation_iterations` | `"auto"` (planner decides 1–6) or a fixed integer. |
| `enable_delegation` | Opt-in orchestrator-routed agent delegation (default off). |
| `enable_tools` | Agent tool loop — **default ON**: `implement*`/`devops`/`validate`/`code-review`/`fix` write **real files** and run commands (per their spec). Set `false` for cheap markdown-only runs. Env `TOOL_LOOP_MAX_ITERS`. |

### Implementation iterations
The pipeline runs implementation as **iterations**, each with a **feature subset**
(sized to keep per-iteration output bounded). The planner splits features from the
product plan by priority and estimated size; unused iteration stages (`4d`–`4f`)
are skipped automatically. Override the count with `implementation_iterations`.

### Budget & model tiering
Set a budget, then ask the orchestrator for a **tier proposal** (criticality-aware,
with a capability floor). Applying it requires approval and writes a runtime
`model-tier.json` the executor uses:

- `GET /api/v1/tier/proposal?project=<p>`
- `POST /api/v1/tier/apply` with `{ "project": "<p>", "approve": true }`

### Telemetry, journal, breakers
- `GET /api/v1/telemetry?project=<p>` — tokens/cost/truncation/compaction rollups.
- `GET /api/v1/project-status?project=<p>` — done/pending/current (`PROJECT-STATUS.md`).
- `GET /api/v1/alerts?project=<p>` — run-breaker alerts.
- `GET /api/v1/iterations?project=<p>` — planned iterations + feature subsets.
- `GET /api/v1/delegations?project=<p>` / `GET /api/v1/messages?project=<p>`.
- `GET /api/v1/cost-history` — cross-project cost index.

---

*This guide applies to ANY project. The pipeline is the same regardless of what you're building.*
