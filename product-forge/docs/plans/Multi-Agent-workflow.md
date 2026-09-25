# Multi-Agent Workflow — OpenCode Pipeline

A staged, role-based AI workflow for this project folder. Any idea, change, or fix
is processed by 8 specialized agents in strict order. Each agent runs a different
model (via OpenCode Go) and only the skills relevant to its role.

---

## 1. Flow

```
NEW IDEA ──► STAGE 0 IDEATION ─► 1 DESIGN ─► 2 ARCHITECT ─► 3 REVIEW ─► 4 IMPLEMENT
                                                                              │
                                                                              ▼
CHANGE / FIX ─(skip stage 0)─► 1 DESIGN ─► ... ─► 6 VALIDATE ◄── 5 CODE REVIEW
        ▲                                                        │
        └────────── FIX loop: re-invoke FIX until 0 issues ──────┘
```

| Trigger | Stages run |
|---|---|
| **New idea** | 0 → 1 → 2 → 3 → 4 → 5 → 6 |
| **Change / fix** | 1 → 2 → 3 → 4 → 5 → 6 (Stage 0 skipped) |
| **Fix loop** | fix → 6, repeat until `reports/issues.md` empty |
| **Explicit "run ideation for this"** | 0 → 1 → ... → 6 (user override) |

---

## 2. Agent roster & artifact contract

Each agent has a strict **input → output** contract. Artifacts are written, not
overwritten; later agents append. No agent edits another agent's artifact.

| Stage | Agent | Mode | Reads (inputs) | Writes (outputs) | Depends on |
|---|---|---|---|---|---|
| 0 | `ideation` (orchestrator) | primary | user idea (text/file) | `docs/product-plan.md` (includes summary + must-have + optional requirements), `docs/pipeline-state.md` | — (start) |
| 1 | `design` | subagent | `docs/product-plan.md` | `docs/requirements.md`, `docs/design.md` | 0 |
| 2 | `architect` | subagent | requirements, design | `docs/architecture.md` (+ tech stack, ADRs), `docs/architecture.d2` (D2 diagram), `docs/architecture.ofk` (OpenFlowKit diagram) | 1 |
| 3 | `review` | subagent | requirements, design, architecture | `docs/review.md` (APPROVED / CHANGES REQUIRED) | 2 |
| 4 | `implement` | subagent | all above + review | `src/` (code) | 3 — **gate: must be APPROVED** |
| 5 | `code-review` | subagent | `src/`, requirements, design | `reports/code-review.md` | 4 |
| 6 | `validate` | subagent | `src/`, requirements | `reports/issues.md` (unit/functional/E2E results) | 5 |
| 7 | `fix` | subagent | `reports/issues.md`, `src/` | `src/` (fixed code) | 6 — re-triggers validate |

**Gates / rules:**
- Stage 4 (implement) **must not start** unless `docs/review.md` contains `APPROVED`.
- Validate writes **all** findings to `reports/issues.md` — never only in chat.
- Fix loop: `validate` → if issues remain → `fix` → re-run `validate`, until empty.
- `docs/pipeline-state.md` tracks each request's current stage (progress + audit).

---

## 3. Orchestrator (ideation) behavior

Stage 0 **always** runs the stakeholder-review meeting for a new idea:

### 3.1 Idea Input Handling
1. Accept the raw idea from user — **text** or **file** (e.g., `.txt`, `.md`, `.pdf`).
2. If idea is from a file, **read and summarize** the content.
3. **Show the summarized idea** to user for confirmation.

### 3.2 Summary & Confirmation
4. Display a structured summary of the idea:
   - **Problem Statement**: What problem does this solve?
   - **Target Users**: Who is this for?
   - **Core Features**: Key functionality (list format)
   - **Scope**: MVP boundaries (what's in/out)
5. **Ask user**: "Is this summary correct? Any changes before we proceed?"
6. If changes requested → update summary → re-confirm → proceed.

### 3.3 Agent Query Meeting
7. Collect questions/concerns from **all downstream agents** (design → fix).
8. **Also collect optional/nice-to-have requirements** from agents.
9. Ask the user the questions **one at a time**, capturing every answer.
10. For each answer, note if it's **MUST-HAVE** or **OPTIONAL**.

### 3.4 Final Synthesis
11. Synthesize everything into `docs/product-plan.md` — the single source of truth all agents consume.
12. Include a section for **optional requirements** (tagged as `OPTIONAL`) that agents can reference during implementation if time/budget allows.

> **Note:** In `docs/product-plan.md`, optional requirements should be clearly tagged with `[OPTIONAL]` prefix. Downstream agents (design, architect, implement) will prioritize MUST-HAVE requirements and only address OPTIONAL items if capacity permits.

Orchestrator is **tool-enforced** (`edit: deny`, `bash: deny`, `skill: * deny`):
it physically cannot implement anything itself, so every request must flow
through subagents. It never jumps straight to implementation.

**Change/fix flow:** default skips Stage 0 and starts at Design. Ideation is only
re-run if the user explicitly asks during a fix/change.

---

## 4. Skills per agent (vendored into `.opencode/skills/`)

Each agent's `permission.skill` allows ONLY its own role's skills.

| Agent | Vendored skills | Source repo |
|---|---|---|
| design | `spec`, `brainstorming`, `product-designer` | CristianLlanos/spec-skill, ckorhonen/claude-skills, borghei/Claude-Skills |
| architect | `architecture`, `architect`, `software-architecture-design` | pssah4/digital-innovation-agents, crewrig/crewrig, majiayu000/claude-skill-registry |
| review | `architecture-review`, `heuristic-evaluation` | oimiragieo/agent-studio, Abhsin/DesignSkills |
| implement | `tdd`, `code-development` | glebis/claude-skills, RainLib/full-stack-skill |
| code-review | `code-review`, `review-code` | awesome-skills/code-review-skill, patinaproject/skills |
| validate | `testing-strategy`, `e2e-testing-claude-code`, `playwright-pro` | greyhaven-ai/claude-code-config, pramoddutta/qaskills, borghei/Claude-Skills |
| fix | `tdd`, `code-development` (same as implement) | glebis/claude-skills |
| ideation | none (`skill: "*": deny`) | — |

---

## 5. Agent detail — roles, prompts, skills, permissions

Each agent has a dedicated `.opencode/agent/<name>.md` file with frontmatter
(model, permissions, skill allowlist) and a detailed prompt.

| Agent | Model | Skills | Permissions | Prompt |
|-------|-------|--------|-------------|--------|
| **Ideation** | `opencode-go/mimo-v2.5` | None (all denied) | edit/bash/skill: deny | Pipeline orchestrator. Coordinates 7 subagents in strict order. NEVER writes files or runs commands. Triggers: NEW IDEA runs 0→1→2→3→4→5→6; CHANGE/FIX skips Stage 0. **Step 1:** Accept idea (text or file), summarize, show to user for confirmation. **Step 2:** Collect questions from all agents + optional requirements. **Step 3:** Ask user questions one-by-one, tag answers as MUST-HAVE or OPTIONAL. **Step 4:** Synthesize product-plan.md with summary, must-have, and optional sections. After each stage, updates pipeline-state.md and reports progress. If user switches tier mid-run, applies to future invocations only. |
| **Design** | `opencode-go/minimax-m3` | spec, brainstorming, product-designer | bash: deny | Reads `docs/product-plan.md`. Writes `docs/requirements.md` (functional/non-functional requirements, constraints, success criteria, user stories, acceptance criteria) and `docs/design.md` (user flows, info architecture, component breakdown, UX/UI direction, data concepts, edge cases, error handling). Never invents unsupported requirements. Never writes code or decides tech stack. |
| **Architect** | `opencode-go/qwen3.7-max` | architecture, architect, software-architecture-design | bash: deny | Reads requirements + design. Writes `docs/architecture.md` containing: tech stack with justification, architecture style (monolith/microservices/etc), ADRs (MADR-style), component/interface view, NFR mapping with concrete numbers, risks and open items. **ALSO writes:** `docs/architecture.d2` (D2 source for static diagrams) AND `docs/architecture.ofk` (OpenFlowKit DSL for interactive/shareable diagrams). Every decision traceable to a requirement. Never writes code. |
| **Review** | `opencode-go/qwen3.7-plus` | architecture-review, heuristic-evaluation | bash: deny, edit: allow | Reads requirements + design + architecture. Writes `docs/review.md` with verdict on FIRST line: `APPROVED` or `CHANGES REQUIRED`. Findings grouped by severity (Critical/High/Medium/Low). Each finding has problem, proof (conflicting requirement/design/arch section), and concrete fix. Verifies SOLID, DRY, YAGNI, NFRs, anti-patterns. Only writes review.md — never edits other docs. |
| **Implement** | `opencode-go/kimi-k2.7-code` | tdd, code-development | edit/bash: allow | Reads requirements + design + architecture + review (MUST be APPROVED). Writes working code. Follows architecture exactly — tech stack, ADRs, component boundaries are binding. Uses TDD where practical. Clean production-quality code. On change runs, appends/merges without rewriting working code. As Fix agent, also reads `reports/issues.md` and fixes every issue listed. |
| **Code Review** | `opencode-go/kimi-k2.7-code` | code-review, review-code | edit/bash: allow | Reads code + requirements + design + architecture. Writes `reports/code-review.md` with: findings (Critical/High/Medium/Low), each with ID, problem, proof (file:line), concrete fix. Verification gate: code matches architecture/ADRs and requirements. Verdict: `READY FOR VALIDATION` or `NEEDS FIXES`. Read-only review — edit/bash only for verifying findings and writing report. |
| **Validate** | `opencode-go/deepseek-v4-flash` | testing-strategy, e2e-testing-claude-code, playwright-pro | edit/bash: allow | Reads code + requirements (acceptance criteria). Runs real test commands (unit/functional/E2E). Writes `reports/issues.md` with: run date, model used, test commands executed, summary (`PASS` or `FAIL <count>`), each issue with ID, severity, test name, failing assertion/error output (evidence), affected file. Every issue MUST include actual output evidence. If no test setup exists, reports as Critical and installs framework. |
| **Fix** | `opencode-go/kimi-k2.7-code` | tdd, code-development | edit/bash: allow | Reads `reports/issues.md` + existing code. Fixes every issue in severity order (Critical→High→Medium→Low). Fixes root cause, not symptom. Does not change scope beyond reported issues. After fixing, re-runs failing test first (confirms pass), then full suite. Updates issues.md marking each as FIXED with evidence (passing test output). Then reports to orchestrator to re-run Validation. |

---

## 6. Model tiers (OpenCode Go only)

Pricing = Go subscription ($5 first mo, then $10/mo). All requests count against
Go's windows: **$12 / 5 hours, $30 / week, $60 / month** plus per-model monthly
allocations. Model IDs used as `opencode-go/<id>`.

### Tier 1 — Recommended (default)

| Role | Model | ctx | $in/$out per 1M | $/mo alloc | Req/5hr | Est./run |
|---|---|---|---|---|---|---|
| Ideation | `mimo-v2.5` | 1M | $0.14/$0.28 | $60 | 30,100 | ~$0.02 |
| Design | `minimax-m3` | 1M | $0.30/$1.20 | $60 | 3,200 | ~$0.04 |
| Architect | `qwen3.7-max` | 1M | $2.50/$7.50 | $60 | 340 | ~$0.53 |
| Review | `qwen3.7-plus` | 1M | $0.40/$1.60 | $60 | 4,300 | ~$0.07 |
| Implement | `kimi-k2.7-code` | **262k** | $0.95/$4.00 | $60 | 1,350 | ~$0.62 |
| Code Review | `kimi-k2.7-code` | **262k** | $0.95/$4.00 | $60 | 1,350 | ~$0.37 |
| Validate | `deepseek-v4-flash` | 1M | $0.22/$0.66 | $30 | 7,600 | ~$0.04 |
| Fix | `kimi-k2.7-code` | **262k** | $0.95/$4.00 | $60 | 1,350 | ~$0.31 |
| **Total/run** | | | | | | **≈ $2.00** |

### Tier 2 — Cheap (switch with `/models cheap`)

| Role | Model | ctx | $in/$out per 1M | $/mo alloc | Req/5hr | Est./run |
|---|---|---|---|---|---|---|
| Ideation | `hy3` | **256k** | $0.14/$0.58 | $60 | 4,300 | ~$0.01 |
| Design | `mimo-v2.5` | 1M | $0.14/$0.28 | $60 | 30,100 | ~$0.02 |
| Architect | `qwen3.7-plus` | 1M | $0.40/$1.60 | $60 | 4,300 | ~$0.09 |
| Review | `minimax-m3` | 1M | $0.30/$1.20 | $60 | 3,200 | ~$0.05 |
| Implement | `deepseek-v4-flash` | 1M | $0.22/$0.66 | $30 | 7,600 | ~$0.13 |
| Code Review | `deepseek-v4-flash` | 1M | $0.22/$0.66 | $30 | 7,600 | ~$0.08 |
| Validate | `mimo-v2.5` | 1M | $0.14/$0.28 | $60 | 30,100 | ~$0.03 |
| Fix | `deepseek-v4-flash` | 1M | $0.22/$0.66 | $30 | 7,600 | ~$0.06 |
| **Total/run** | | | | | | **≈ $0.47** |

### Tier 3 — Hybrid (recommended for stages 0–3, cheap for stages 4–7)

| Role | Model |
|---|---|
| Ideation | `opencode-go/mimo-v2.5` |
| Design | `opencode-go/minimax-m3` |
| Architect | `opencode-go/qwen3.7-max` |
| Review | `opencode-go/qwen3.7-plus` |
| Implement | `opencode-go/deepseek-v4-flash` |
| Code Review | `opencode-go/deepseek-v4-flash` |
| Validate | `opencode-go/mimo-v2.5` |
| Fix | `opencode-go/deepseek-v4-flash` |

**Context-window note:** Implement/Code-Review/Fix on `kimi-k2.7-code` cap at
262k; `hy3` at 256k. For very large codebases the cheap tier's 1M-context
`deepseek-v4-flash` is actually the safer implementer. Switch as needed.

**Excluded:** `kimi-k3`, `glm-5.3` ($15/mo alloc — burns too fast);
`muse-spark-1.2-contributor` (sends prompts to Meta for training).

### Switching — `/models` command

```
/models recommended   → rewrites model: in all 8 agent files → Tier 1
/models cheap         → rewrites model: in all 8 agent files → Tier 2
/models hybrid        → rewrites model: in all 8 agent files → Tier 3
/models list          → prints current model per agent
```

Only the `model:` frontmatter line is edited; a diff summary is printed. Applies
to NEW pipeline runs (subagent models lock at spawn; restart opencode for full
effect). An in-flight run keeps its already-spawned agents' models — so you can
switch to cheap mid-project by waiting for the current run to finish.

---

## 6. Cost analysis — full web app (frontend + DB + API + mobile)

Assumes ~20 pipeline runs to ship an MVP across all 4 layers (scaffold, per-layer
features, integration, fixes), plus fix-loop overhead (+~30%).

| | Tier 1 Recommended | Tier 2 Cheap | Tier 3 Hybrid |
|---|---|---|---|
| Cost per run | ~$2.00 | ~$0.47 | ~$0.90 |
| Full app (20 runs) | **~$40–52** | **~$9–12** | **~$18–24** |
| Share of Go monthly ($60) | ~67–87% | ~15–20% | ~30–40% |
| Weekly window ($30) | exceeded if run in one burst | safe | safe |
| 5-hr window ($12) | ~6 runs/window | ~25 runs/window | ~13 runs/window |
| Verdict | Works if work is spread across days/weeks | Comfortably covered | Best balance |

**Recommendation for the web app:** run **Tier 3 Hybrid** — expensive reasoning
models only for ideation/design/architect/review, cheap models for bulk
implementation, code review, validation, and fix passes. This protects the weekly
window and saves `qwen3.7-max` / `kimi-k2.7-code` budget for where reasoning
matters most.

### 6.1 Go usage snapshot & current balance

The Go console shows live usage against the three windows. Example snapshot:

| Window | Limit | Used | Remaining | Resets in |
|---|---|---|---|---|
| Rolling (5-hr) | $12 | 84% → $10.08 | **$1.92** | 37 min |
| Weekly | $30 | 70% → $21.00 | **$9.00** | 1 day 14 hrs |
| Monthly | $60 | 52% → $31.20 | **$28.80** | 23 days |

**What fits in the remaining budget:**

| Tier | Cost/run | Weekly left ($9) | Monthly left ($28.80) |
|---|---|---|---|
| Recommended | ~$2.00 | ~4 runs | ~14 runs |
| Hybrid | ~$0.90 | ~10 runs | ~32 runs |
| Cheap | ~$0.47 | ~19 runs | ~61 runs |

**Operational rules from this snapshot:**
- Do not start a run in the ~37 min before the rolling reset — the window is
  nearly full; wait for the reset, then it is fully fresh.
- The **weekly window is the binding constraint** (only ~$9 left, ~38 hrs to
  reset). If pipeline runs are planned this week, use **cheap** (`/models cheap`)
  or at most **hybrid** — a Recommended-tier run (~$2.00) burns a disproportionate
  share of the week.
- The **monthly window is comfortable** (~29 days of headroom); even full
  Recommended tier fits ~14 runs/month.
- Check `https://opencode.ai/auth` before each heavy run to re-read these numbers
  and pick the tier accordingly.

### 6.2 DeepSeek V4 Flash — Where It Fits Across Tiers

DeepSeek V4 Flash ($0.22/$0.66 per 1M, 1M ctx) is the **workhorse of the Cheap tier** — it appears in 3/8 roles there. In the Recommended tier it only serves Validate (where its speed + 1M ctx shine). In free tiers, purpose-built coding models (Laguna M.1, North Mini Code) are preferred for implement/fix.

| Role | Recommended | Cheap | Zenfree | Orouterfree |
|------|-------------|-------|---------|-------------|
| ideation | mimo-v2.5 | hy3 | ox-alpha-free | ox-alpha:free |
| design | minimax-m3 | mimo-v2.5 | mimo-v2.5-free | north-mini-code:free |
| architect | qwen3.7-max | qwen3.7-plus | nemotron-3-ultra-free | nemotron-3-ultra:free |
| review | qwen3.7-plus | minimax-m3 | big-pickle | laguna-s-2.1:free |
| **implement** | kimi-k2.7-code | **deepseek-v4-flash** | laguna-s-2.1-free | laguna-m.1:free |
| **code-review** | kimi-k2.7-code | **deepseek-v4-flash** | big-pickle | laguna-s-2.1:free |
| **validate** | **deepseek-v4-flash** | mimo-v2.5 | mimo-v2.5-free | north-mini-code:free |
| **fix** | kimi-k2.7-code | **deepseek-v4-flash** | laguna-s-2.1-free | laguna-m.1:free |

**Cost comparison for Implement role:**
| Tier | Model | Cost/1M | Context | Quality for Implement |
|------|-------|---------|---------|----------------------|
| Recommended | kimi-k2.7-code | $0.95/$4.00 | 262K | ★★★★★ (purpose-built) |
| Cheap | deepseek-v4-flash | $0.22/$0.66 | 1M | ★★★★☆ (strong coder, 1M ctx) |
| Zenfree | laguna-s-2.1-free | FREE | 262K | ★★★★☆ (purpose-built, free) |
| Orouterfree | laguna-m.1:free | FREE | 262K | ★★★★★ (best free coder, CursorBench 47.6%) |

**Key insight:** DeepSeek V4 Flash is the **workhorse of the Cheap tier** — appears in 3/8 roles (implement, code-review, fix). In Recommended tier it only serves Validate. In free tiers, purpose-built coding models (Laguna M.1, North Mini Code) are preferred for implement/fix despite smaller context.

---

## 7. Observability (what agents are doing)

You can't peek inside a live subagent, but every agent writes a durable artifact
before finishing:

| Watch this | Shows |
|---|---|
| `docs/pipeline-state.md` | every stage: request, agent, status, artifact (append-only audit log) |
| `docs/product-plan.md` | what the user decided at ideation (includes summary, must-have requirements, and optional/nice-to-have requirements) |
| `docs/requirements.md` / `design.md` / `architecture.md` | stage outputs |
| `docs/review.md` | verdict gate before implementation |
| `reports/code-review.md` | code findings |
| `reports/issues.md` | validation results (fix loop input) |

Between stages the orchestrator reports completed / pending / artifacts in chat.

**Optional web dashboard:** a local static page (HTML + JS) that renders these
Markdown artifacts as a status board is feasible as a follow-up. Ask when the
pipeline is proven.

---

## 8. Setup & scoping (this folder ONLY)

- Everything lives in this folder: `opencode.json` + `.opencode/` + `docs/` +
  `reports/`.
- Global `~/.config/opencode/opencode.json` (Ollama) is **untouched**.
- Other folders' sessions never see these agents/providers.
- Go API key via `{env:OPENCODE_GO_KEY}` (set in env or `.env` in this folder)
  — never stored in the config file.

### First run

1. Set the key: `$env:OPENCODE_GO_KEY="<your-go-key>"` (or add to a `.env` in
   this folder).
2. Restart opencode from this folder.
3. Run `/pipeline <your idea>` — or just talk to the ideation agent directly
   (it is the default agent here).

## 9. Replication to another folder or global

- **Another folder:** copy `opencode.json`, `.opencode/`, and the `docs/`/
  `reports/` conventions → identical, still folder-scoped.
- **Global (all sessions):** move provider to `~/.config/opencode/opencode.json`,
  agents → `~/.config/opencode/agent/`, skills → `~/.config/opencode/skills/`,
  commands → `~/.config/opencode/command/`. (Not done now — folder-scoped only.)

---

## 10. File tree

```
Exploring/
├── opencode.json
├── .opencode/
│   ├── agent/{ideation,design,architect,review,implement,code-review,validate,fix}.md
│   ├── command/{pipeline,models}.md
│   └── skills/{spec,brainstorming,product-designer,architecture,architect,
│               software-architecture-design,architecture-review,
│               heuristic-evaluation,tdd,code-development,code-review,
│               review-code,testing-strategy,e2e-testing-claude-code,
│               playwright-pro}/SKILL.md
├── scripts/
│   └── pipeline.py          (deterministic pipeline commands)
├── docs/
│   ├── product-plan.md      (Stage 0: Summary + MUST-HAVE + OPTIONAL)
│   ├── requirements.md      (Stage 1)
│   ├── design.md            (Stage 1)
│   ├── architecture.md      (Stage 2)
│   ├── review.md            (Stage 3: APPROVED gate)
│   ├── pipeline-state.md    (Audit log)
│   ├── pipeline-architecture.md        (E2E diagrams: Mermaid)
│   ├── pipeline-architecture-spec.json (E2E diagrams: draw.io/PDF)
│   ├── pipeline-quick-reference.md     (Quick reference card)
│   └── Diagram-Generation-Spec.md      (Diagram tool specs)
├── reports/
│   ├── code-review.md       (Stage 5)
│   └── issues.md            (Stage 6: fix loop input)
├── Multi-Agent-workflow.md  (this file)
├── dashboard.html           (pipeline monitoring UI)
└── serve.py                 (Python server for dashboard)
```

---

## 11. Failure Recovery Components

### Checkpoints
**What:** Save pipeline state after each agent completes.

**Purpose:** Allow resuming from where you left off if interrupted.

**When used:** After each agent successfully completes its work.

**Example flow:**
1. Agent runs → creates checkpoint with state
2. Pipeline interrupted (crash, timeout, etc.)
3. Resume pipeline → loads checkpoint → continues from last saved state

### Dead Letter Queue (DLQ)
**What:** Captures tasks that permanently failed after all retry attempts.

**Purpose:** Store failed tasks for review and potential replay.

**When used:** After all retry attempts are exhausted.

**Example flow:**
1. Agent fails → retries with fallback models
2. All retries fail → task goes to DLQ
3. Review DLQ → fix issue → replay task

### Circuit Breakers
**What:** Prevent cascading failures by stopping attempts when an agent is broken.

**Purpose:** Stop wasting resources on a failing agent.

**When used:** After 5 consecutive failures (configurable threshold).

**States:**
- **CLOSED** — Normal operation, failures are counted
- **OPEN** — Agent is broken, all attempts blocked for cooldown period
- **HALF-OPEN** — Testing if agent recovered, allow single probe call

**Example flow:**
1. Agent fails → failures count increments
2. 5+ failures → circuit breaker opens (stops agent)
3. Cooldown period expires → half-open state
4. Probe call succeeds → breaker closes (resume normal operation)

### Summary Table

| Component | Purpose | When Used |
|---|---|---|
| Checkpoints | Resume interrupted pipelines | After each agent completes |
| DLQ | Store permanently failed tasks | After retry exhaustion |
| Circuit Breakers | Stop cascading failures | After 5+ consecutive failures |

---

## 12. End-to-End Workflow (With All Phase 1-3 Features)

This section describes the **complete execution flow** when a stage runs, integrating all Phase 1-3 features that have been implemented.

### When a stage executes (example: Stage 4 Implement on myworld)

```
1. ORCHESTRATOR STARTS
   ↓
   [Phase 1.8] Stop Conditions check
   → Is retry count OK? Tokens OK? Circuit open?
   ↓
2. LOCK ACQUIRED
   ↓
   [Phase 1.2] LockManager.acquire("myworld")
   → Prevents concurrent execution of same project
   → File-based distributed lock (works across machines)
   → Auto-clears stale locks after 2 hours
   ↓
3. CONTEXT PREPARED (Token-Budgeted)
   ↓
   [Phase 1.7] ContextEngine.prepare_context()
   → System prompt: max 2K tokens
   → Project context: max 4K tokens
   → Stage context: max 3K tokens
   → Agent context: max 2K tokens
   → Previous output: max 5K tokens
   → Knowledge: max 3K tokens
   → User input: max 1K tokens
   → Priority: system > user > agent > stage > project
   ↓
4. KNOWLEDGE LOADED (Smart Routing)
   ↓
   [Phase 2.3] KnowledgeRouter.route(task, stage=4)
   → Auto-discovered 21 guidelines from docs/guidelines/
   → Scores by: domain match + tag match + keyword match + priority
   → Selects top resources within 10K token budget
   → Example: stage=4 (Implement) → loads Python, TypeScript, API, FastAPI
   ↓
5. REASONING DEPTH SELECTED
   ↓
   [Phase 3.4] AdaptiveReasoningController.assess_complexity()
   → Stage 4 (Implement) = high complexity
   → Returns "high" or "maximum" depth (5-10 iterations, 8K-16K tokens)
   ↓
6. MODEL SELECTED (Capability-Based)
   ↓
   [Phase 1.1] ModelCapabilityRegistry.select_with_fallback()
   → Tier=recommended → tries gpt-4o, claude-3-sonnet
   → Has capability "code" → returns gpt-4o
   → Fallback chain: gpt-4-turbo → claude-3-opus → gpt-3.5-turbo → mimo
   ↓
7. BUDGET CHECKED
   ↓
   [Phase 1.6] BudgetTracker.check_budget("myworld", estimated_cost)
   → Project budget: $0/$500 (OK)
   → Hourly: $0/$100 (OK)
   → Daily: $0/$1000 (OK)
   → Returns within_budget=True
   ↓
8. TOKEN ALLOCATION
   ↓
   [Phase 2.4] TokenBudgetAllocator.get_allocation(stage=4)
   → Implement stage: 142,857 tokens allocated
   → Tracks used vs remaining per stage
   → Auto-rebalances if over/under utilized
   ↓
9. TOOL RESULT CACHE CHECK
   ↓
   [Phase 2.2] ToolResultCache.get(tool_name, args)
   → Computes SHA256 key from tool+args
   → If cached and not expired → returns cached value
   → If miss → executes tool → stores in cache
   → LRU eviction when 1000 entries reached
   → 21 tools excluded (side-effect tools like create_file, send_email)
   ↓
10. AGENT EXECUTES
    ↓
    [Stage 4: Implement Agent runs]
    → Uses knowledge from Phase 2.3
    → Uses context from Phase 1.7
    → Uses reasoning depth from Phase 3.4
    → Uses model from Phase 1.1
    ↓
11. TOOL CALLS (with caching + compression)
    ↓
    [Phase 2.2] Check cache → execute → cache result
    [Phase 3.3] Compress tool output if > 1000 tokens
    [Phase 3.6] Check semantic cache (similar queries)
    ↓
12. AGENT COMPLETES
    ↓
    [Phase 1.4] CrossReview.request_auto_reviews()
    → Auto-requests code-review, security reviews
    → Reviewers add feedback → addressed
    → Quality score calculated
    ↓
13. COST RECORDED
    ↓
    [Phase 2.7] CostKPITracker.record_task()
    → input_tokens, output_tokens, cost_usd, success
    → Calculates Cost Per Successful Task (CPS)
    → Tracks per-stage, per-agent, per-project
    ↓
14. LEDGER UPDATED
    ↓
    [Phase 1.4] AgentLedger.record_work()
    → Appends to .pipeline/agent_ledger.jsonl
    → Immutable audit trail
    → Tracks: success_rate, total_cost, total_tokens per agent
    ↓
15. LOG WRITTEN
    ↓
    [Phase 1.5] ProductLogger.info()
    → Structured JSON logs to products/myworld/logs/product.log
    → Captures: stage, agent, message, metadata, timestamp
    ↓
16. CHECKPOINT SAVED
    ↓
    [Phase 1.2] CheckpointManager.save(stage, state)
    → SHA256 checksum for integrity
    → Linked list of checkpoints (parent_id)
    → Auto-cleanup keeps last 10
    ↓
17. CIRCUIT BREAKER UPDATED
    ↓
    [Phase 1.5] CircuitBreakerRegistry.record_success(agent)
    → Failure count reset to 0
    → State stays CLOSED
    → If 5 failures → OPEN → blocks calls for 60s
    → After 60s → HALF_OPEN → test with limited calls
    ↓
18. VERSION RECORDED (if release)
    ↓
    [Phase 1.10] VersionManager.bump("patch" | "minor" | "major")
    → Updates changelog
    → Generates Git tag
    ↓
19. ON FAILURE → DLQ
    ↓
    [Phase 1.3] DeadLetterQueue.add()
    → If retries exhausted → moves to DLQ
    → Tracks: stage, agent, error, error_type, input_data
    → Manual review/retry/resolve/abandon
    ↓
20. HUMAN ESCALATION (if needed)
    ↓
    [Phase 1.8] StopConditionManager.escalate()
    → When: low confidence, validation failed, human_required
    → Priority: low/medium/high/urgent/critical
    → Stored in escalations.jsonl
    → Status: pending → acknowledged → resolved
    ↓
21. BUDGET REALLOCATED
    ↓
    [Phase 2.4] TokenBudgetAllocator.auto_rebalance()
    → If any stage >80% utilized → get more from <20% stages
    → Records reallocation history
    ↓
22. LOCK RELEASED
    ↓
    [Phase 1.2] LockManager.release("myworld")
    → Other projects can now acquire
    ↓
23. NEXT STAGE
    ↓
    → Stage 5 (Code Review) starts → cycle repeats
```

### Multi-Project Parallel Execution (When 2+ projects run simultaneously)

```
Project A (myworld)               Project B (acme)
    ↓                                  ↓
LockManager.acquire("myworld")    LockManager.acquire("acme")
    ↓ (succeeds)                      ↓ (succeeds - different lock)
[Both run in parallel]

QueueManager.dequeue() → returns next project when slot opens
[Max parallel = 3]

CircuitBreakerRegistry → tracks each project's circuit state independently
AgentLedger → separate audit trail per project
CostKPI → separate cost tracking per project
BudgetTracker → shared global budget across all projects
```

### CLI Commands for All Features

| Command | Phase | Feature |
|---------|-------|---------|
| `python pipeline.py list` | Core | List all projects |
| `python pipeline.py status myworld` | Core | Detailed project status |
| `python pipeline.py budget` | 1.6 | Token/cost budget |
| `python pipeline.py queue` | 1.1 | Project execution queue |
| `python pipeline.py checkpoints myworld` | 1.2 | Saved checkpoints |
| `python pipeline.py dlq myworld` | 1.3 | Failed operations |
| `python pipeline.py version myworld` | 1.10 | Version info |
| `python pipeline.py review myworld` | 1.4 | Code review status |
| `python pipeline.py ledger myworld` | 1.4 | Agent work history |
| `python pipeline.py skills` | 2.6 | Available skills |
| `python pipeline.py log myworld` | 1.5 | Product logs |
| `python pipeline.py models` | 1.1 | Model registry |
| `python pipeline.py context myworld` | 1.7 | Context budget |
| `python pipeline.py stop-conditions` | 1.8 | Stop rules |
| `python pipeline.py escalations` | 1.8 | Human escalations |
| `python pipeline.py cache` | 2.2 | Tool cache |
| `python pipeline.py knowledge` | 2.3 | Knowledge router |
| `python pipeline.py budget-alloc myworld` | 2.4 | Stage budgets |
| `python pipeline.py cost-kpi myworld` | 2.7 | Cost per Success KPI |
| `python pipeline.py circuit-reset` | 1.5 | Reset breakers |
| `python pipeline.py lock myworld` | 1.2 | Acquire lock |
| `python pipeline.py unlock myworld` | 1.2 | Release lock |
| `python pipeline.py report myworld` | All | Comprehensive report |

### What Auto-Activates vs What Needs Explicit Call

| Module | Auto-Active? | How to Trigger |
|--------|--------------|----------------|
| **Phase 1.1** Model Registry | ✅ Yes | Agent invocation triggers model selection |
| **Phase 1.2** Lock + Checkpoints | ✅ Yes | Orchestrator wraps stage execution |
| **Phase 1.3** DLQ | ✅ Yes | Failure handler moves to DLQ |
| **Phase 1.4** Cross-Review + Ledger | ✅ Yes | Agent completion triggers review |
| **Phase 1.5** Logging + Circuit Breaker | ✅ Yes | Every tool call wrapped |
| **Phase 1.6** Budget Tracker | ✅ Yes | Checked before each model call |
| **Phase 1.7** Context Engine | ✅ Yes | Context prepared for each agent |
| **Phase 1.8** Stop Conditions | ✅ Yes | Checked before each stage |
| **Phase 1.10** Version Manager | 🟡 On release | Triggered at packaging stage |
| **Phase 2.1** Queue + Parallel | ✅ Yes | Orchestrator uses queue |
| **Phase 2.2** Tool Cache | ✅ Yes | Every tool call checked |
| **Phase 2.3** Knowledge Router | ✅ Yes | Context preparation uses it |
| **Phase 2.4** Budget Allocator | ✅ Yes | Stage budget enforced |
| **Phase 2.5** Memory Store (Ledger) | ✅ Yes | Every agent work recorded |
| **Phase 2.6** Skill Validation | ✅ Yes | Skills validated on use |
| **Phase 2.7** Cost KPI | ✅ Yes | Every task cost tracked |
| **Phase 3.1** Time-Based Loop | ❌ Manual | Agent code must call LoopController |
| **Phase 3.2** Event-Based Loop | ❌ Manual | Agent code must call LoopController |
| **Phase 3.3** Tool Compression | ❌ Manual | Would need wrapper around tool calls |
| **Phase 3.4** Adaptive Reasoning | ❌ Manual | Agent must query for depth |
| **Phase 3.5** Knowledge Graph | ❌ Manual | Knowledge Router doesn't use it yet |
| **Phase 3.6** Semantic Cache | ❌ Manual | Would need to wrap queries |

### Current Implementation State

- **Phase 1 (CRITICAL)**: 9/9 features auto-active ✅
- **Phase 2 (IMPORTANT)**: 7/7 features auto-active ✅
- **Phase 3 (ADVANCED)**: Infrastructure ready, 0/6 auto-active (need agent integration)

**Recommendation**: Phase 3 features are infrastructure-ready. They can be wired into specific agents when needed (e.g., for complex multi-step reasoning tasks). For now, Phase 1-2 provide the full production-ready pipeline foundation.

---

## 13. Hybrid Pipeline Execution

The pipeline uses a hybrid approach to balance speed and flexibility:

### Known Limitation
The `/pipeline` command in opencode has a context bleeding issue where the LLM doesn't properly load the command file. This affects all `/pipeline` commands.

### Workaround
Use the Python script directly for deterministic commands, and natural language for agent execution.

### How to Use

#### Deterministic Commands (run via bash)
```bash
python scripts/pipeline.py           # Shows usage
python scripts/pipeline.py list      # Lists projects
python scripts/pipeline.py agents    # Lists agents
python scripts/pipeline.py health    # Shows health status
python scripts/pipeline.py test      # Tests infrastructure
python scripts/pipeline.py checkpoints  # Lists checkpoints
python scripts/pipeline.py dlq       # Shows dead letter queue
```

#### Agent Execution (tell the AI directly)
- "Run the pipeline for: Build a recipe sharing platform"
- "Fix the login validation bug"
- "Continue the interrupted pipeline"
- "Run the architect agent"

### Why This Approach?
1. **Speed**: Deterministic commands run instantly via script
2. **Reliability**: No LLM context bleeding for simple commands
3. **Flexibility**: Agent execution still uses AI for complex tasks
4. **Maintainability**: Script is easy to test and modify

---

## 11. Model tier: ZenFree (opencode-go)

No API key required. Uses `opencode-go` provider with free models.

| Agent       | Role       | Model ID                              |
|-------------|------------|---------------------------------------|
| Ideation    | Orchestrator | `opencode-go/mimo-v2.5-free`        |
| Design      | Designer   | `opencode-go/muse-spark-contributor-free` |
| Architect   | Architect  | `opencode-go/qwen3-free`            |
| Review      | Reviewer   | `opencode-go/nemotron-3-ultra-free` |
| Implement   | Implementer | `opencode-go/kimi-k2.7-free`        |
| Code Review | Reviewer   | `opencode-go/kimi-k2.7-free`        |
| Validate    | Validator  | `opencode-go/nemotron-3-lightning-free` |
| Fix         | Fixer      | `opencode-go/kimi-k2.7-free`        |

**Note:** Free models rotate without notice. Verify availability with `/models list`.

---

## 12. Model tier: OpenRouter Free

Uses `openrouter` provider. Requires `OPENROUTER_API_KEY`. Free models via OpenRouter.

| Agent       | Role       | Model ID                              |
|-------------|------------|---------------------------------------|
| Ideation    | Orchestrator | `openrouter/deepseek/deepseek-r1:free` |
| Design      | Designer   | `openrouter/google/gemma-3-27b-it:free` |
| Architect   | Architect  | `openrouter/meta-llama/llama-4-maverick:free` |
| Review      | Reviewer   | `openrouter/qwen/qwen3-235b-a22b:free` |
| Implement   | Implementer | `openrouter/qwen/qwen3-coder:free`  |
| Code Review | Reviewer   | `openrouter/qwen/qwen3-coder:free`  |
| Validate    | Validator  | `openrouter/google/gemma-3-27b-it:free` |
| Fix         | Fixer      | `openrouter/qwen/qwen3-coder:free`  |

**Note:** Free models have rate limits and may be unavailable. Check [openrouter.ai/models](https://openrouter.ai/models) for current free models.

---

## 13. Switching tiers

Use `/models recommended`, `/models cheap`, `/models hybrid`, `/models zenfree`, or `/models orouterfree`.

Tier switching applies to **new runs only** — in-progress agents keep their current model.

---

## 14. Tech Stack & Architecture

The Multi-Agent Multi-Project Pipeline is **NOT a traditional coded application**. It is an **AI-orchestrated workflow** built entirely on top of OpenCode's agent system.

### 14.1 What Is This Pipeline?

| Component | What It Is | Format |
|-----------|-----------|--------|
| **Orchestration Platform** | OpenCode (AI agent platform) | Platform |
| **Agent Definitions** | `.opencode/agent/*.md` | Markdown + YAML frontmatter |
| **Skills** | `.opencode/skills/*/SKILL.md` | Markdown |
| **Commands** | `.opencode/command/*.md` | Markdown |
| **Pipeline Config** | `pipeline.json` | JSON |
| **Pipeline State** | `pipeline-state.md` | Markdown (append-only audit log) |
| **Deterministic Commands** | `scripts/pipeline.py` | Python (simple helper script) |
| **Diagram Generation** | `scripts/generate_diagrams.py` + D2 | Python + D2 DSL |

### 14.2 How It Works

1. **User triggers pipeline** via `/pipeline new "idea"` or natural language
2. **OpenCode reads** the agent markdown files (`.opencode/agent/*.md`)
3. **Agent prompts are injected** into the AI model's context
4. **Subagents execute** their roles (design, architect, implement, etc.)
5. **Each agent writes artifacts** (markdown files) as output
6. **Pipeline state is tracked** in `pipeline-state.md` and `pipeline.json`
7. **Recovery mechanisms** (checkpoints, DLQ, circuit breakers) handle failures

### 14.3 The Agents ARE the Code

The "code" of this pipeline is the **LLM prompts** defined in markdown files. When OpenCode runs:

```
User Input → OpenCode → Reads agent/*.md → Injects prompt into LLM → LLM executes → Writes output files
```

There is:
- **No compiled backend** (no Go, Rust, Java server)
- **No API server** (OpenCode handles the orchestration)
- **No database** (state is tracked in JSON/Markdown files)
- **No traditional application code** (the agents ARE the application)

### 14.4 Diagram Generation Tools

The pipeline uses **two diagram tools** for different purposes:

| Tool | Purpose | When to Use | Installed |
|------|---------|-------------|-----------|
| **D2** | Pipeline flow diagrams, architecture diagrams | Static diagrams, documentation, CI/CD | Yes |
| **OpenFlowKit MCP** | Interactive architecture diagrams | AI-driven generation, editable, shareable | Yes |
| **diagrams (Python)** | Cloud infrastructure diagrams | AWS/Azure/GCP provider icons | Yes |
| **Graphviz** | Graph rendering engine | Used by D2 and diagrams | Yes |
| **Mermaid** | Documentation diagrams | GitHub/VS Code inline rendering | Built-in |

#### When Each Tool is Used

| Scenario | Tool | Reason |
|----------|------|--------|
| **Pipeline stage flow** | D2 | Simple, clean, static |
| **Project architecture** | OpenFlowKit MCP | AI-generated, editable, shareable links |
| **Cloud infrastructure** | diagrams (Python) | Official AWS/Azure/GCP icons |
| **Documentation inline** | Mermaid | Renders in GitHub/VS Code |
| **Quick sketch** | OpenFlowKit MCP | Natural language → diagram |

### 14.5 Diagram Generation Commands

```bash
# D2 — Pipeline flow diagrams (simplified, clean)
d2 --layout elk docs/pipeline-simple.d2 docs/pipeline-simple.svg
d2 --layout elk docs/pipeline-consolidated.d2 docs/pipeline-consolidated.svg

# OpenFlowKit MCP — Project architecture (AI-driven)
# Via MCP client: "Create architecture diagram for [project]"

# Python diagrams — Cloud infrastructure
python scripts/generate_diagrams.py

# Mermaid — Inline documentation
# No command needed - renders in GitHub, VS Code, etc.
```

### 14.6 Automatic Diagram Generation

#### Stage 2 (Architect Agent) — D2 Output

The architect agent **automatically generates** a D2 architecture spec:

**Output artifacts:**
1. `docs/architecture.md` — Human-readable architecture document
2. `docs/architecture.d2` — D2 source for architecture diagram

**Render command:**
```bash
d2 --layout elk docs/architecture.d2 docs/architecture.svg
```

#### Stage 2 (Architect Agent) — OpenFlowKit Output

The architect agent also generates an **OpenFlowKit DSL** for interactive diagrams:

**Output artifacts:**
1. `docs/architecture.ofk` — OpenFlowKit DSL source

**Via MCP (if available):**
```
"Create architecture diagram from architecture.md using OpenFlowKit"
```

#### Stage 4 (Implement Agent) — Renders Diagrams

The implement agent renders all diagram artifacts:

```bash
# Render D2 diagrams
d2 --layout elk docs/architecture.d2 docs/architecture.svg

# OpenFlowKit viewer URL (via MCP)
# "Validate and create viewer URL for architecture.ofk"
```

---

## 16. Prompt Engineering & LLM Optimization Standards

This section documents the standards for how each agent communicates with LLMs, based on research and best practices for multi-agent systems.

### 16.1 Core Principles

| Principle | Implementation | Why |
|-----------|----------------|-----|
| **Information Diet** | Each agent reads ONLY specific files/sections | Reduces context bloat, improves focus |
| **Structured Output** | Every agent writes markdown with exact format | Consistent artifacts, parseable by downstream agents |
| **Context Compaction** | Compact summaries (2-3 pages) replace full files | Faster processing, lower token costs |
| **Token Awareness** | Track tokens per agent, optimize input size | Cost control, stay within context windows |
| **Explicit Boundaries** | Agents cannot edit other agents' files | Prevents conflicts, maintains audit trail |

### 16.2 Input Optimization (Information Diet)

Each agent has a strict **INPUT** section defining exactly what to read:

| Agent | Reads | Skips | Reason |
|-------|-------|-------|--------|
| **Ideation** | User input only | Everything else | Starting point |
| **Design** | product-plan.md | architecture, code, design specs | Source of truth for requirements |
| **Architect** | requirements.md + design.md (Section 1 only) | Full design, code, reviews | Needs requirements + design direction |
| **Review** | requirements + design + architecture | Code, test results | Needs full context for approval |
| **Implement** | review.md (verdict) + architecture (Sec 2,4) + requirements (FR only) | design.md, reviews, test results | Binding constraints only |
| **Code Review** | code + requirements (FR) + design (Sec 1) | architecture.md, test results | Code quality focus |
| **Validate** | code + requirements (AC only) | design, architecture, reviews | Test execution focus |
| **Fix** | issues.md + code | Everything else | Minimal fix scope |

### 16.3 Chunking Strategy

For large files, agents use **offset/limit** to read specific sections:

```markdown
## FILE READING RULES

- Read `docs/requirements.md` in full (typically <300 lines).
- Read `docs/design.md` Section 1 (Design Direction) and component breakdown only.
- If file exceeds 400 lines: read first 200 lines, then search by header.
- Never read code files, JSON data, or reports/ files.
```

### 16.4 Output Format Standards

Every agent writes **structured markdown** with this pattern:

```markdown
# [Agent Name] Output — [Project Name]

> Inputs: `docs/[input-files]`

## [Section 1]
[Structured content with tables, lists, or code blocks]

## [Section 2]
[More structured content]

## Rules
- [Agent-specific rules]
```

### 16.5 Context Memory Between Agents

The pipeline uses **file-based memory** (not in-memory state):

| File | Purpose | Updated By |
|------|---------|------------|
| `docs/agent-context.md` | Resume state (stage, agent, subtask) | Every agent |
| `docs/pipeline-state.md` | Execution history (append-only) | Orchestrator |
| `docs/agent-audit.md` | Detailed audit trail | Every agent |
| `docs/compact/*.md` | Summarized context for downstream agents | Every agent (after completion) |

**Context Flow:**
```
Agent A writes artifact.md
    ↓
Agent A creates compact/agent-a-summary.md (2-3 pages)
    ↓
Orchestrator passes compact summary to Agent B
    ↓
Agent B reads compact/agent-a-summary.md (not full file)
```

### 16.6 Token Optimization

| Strategy | Implementation | Benefit |
|----------|----------------|---------|
| **Compact Summaries** | 2-3 page summaries replace full files | 70-80% token reduction |
| **Section Reading** | Read specific sections, not full files | 50-60% token reduction |
| **Selective Skills** | Each agent allowed only relevant skills | Reduces prompt injection |
| **Model Tier Matching** | Use cheap models for simple tasks, expensive for reasoning | Cost optimization |
| **Dynamic Token Tracking** | Reads model from pipeline.json, not hardcoded | Accurate cost calculation |

**Token Tracking Command:**
```powershell
# Logs tokens and reads model from pipeline.json
powershell -File scripts/token-counter.ps1 -Agent "design" -InputTokens 1500 -OutputTokens 800 -Action "end" -Stage "1" -Artifact "requirements.md" -Project "myworld"
```

### 16.7 Checkpoint Protocol (Every Task Call)

Every Task() call includes checkpoint instructions:

```
CHECKPOINT INSTRUCTIONS (mandatory):
1. Before starting, read ONLY files in your INPUT section
2. Record start timestamp
3. Update docs/agent-context.md with:
   - Current Stage, Agent, Subtask
   - Started At, Tokens Used
   - Pending Tasks, Files In Progress
4. Append to docs/pipeline-state.md
5. Append to docs/agent-audit.md
6. Create compact summary in docs/compact/[stage]-summary.md
```

### 16.8 Model-Specific Optimizations

| Model | Context Window | Optimization |
|-------|----------------|--------------|
| **mimo-v2.5** | 1M | Full file reads OK |
| **minimax-m3** | 1M | Full file reads OK |
| **qwen3.7-max** | 1M | Use for complex reasoning |
| **qwen3.7-plus** | 1M | Balanced cost/quality |
| **kimi-k2.7-code** | 262k | Chunk large files |
| **deepseek-v4-flash** | 1M | Fast, use for validation |

### 16.9 Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Correct Approach |
|--------------|--------------|------------------|
| Reading all files | Context bloat, slow, expensive | Information Diet |
| No output format | Inconsistent artifacts | Structured markdown |
| No checkpoints | Can't resume on failure | Checkpoint protocol |
| No compaction | Downstream agents read full files | Compact summaries |
| Editing other agents' files | Conflicts, no audit trail | Strict file ownership |

---

## 15. File tree (Updated)

```
Exploring/
├── opencode.json
├── .opencode/
│   ├── agent/{ideation,design,architect,review,implement,code-review,validate,fix}.md
│   ├── command/{pipeline,models}.md
│   └── skills/{spec,brainstorming,product-designer,architecture,architect,
│               software-architecture-design,architecture-review,
│               heuristic-evaluation,tdd,code-development,code-review,
│               review-code,testing-strategy,e2e-testing-claude-code,
│               playwright-pro}/SKILL.md
├── scripts/
│   ├── pipeline.py              (deterministic pipeline commands)
│   └── generate_diagrams.py     (diagram generation script)
├── docs/
│   ├── product-plan.md          (Stage 0: Summary + MUST-HAVE + OPTIONAL)
│   ├── requirements.md          (Stage 1)
│   ├── design.md                (Stage 1)
│   ├── architecture.md          (Stage 2)
│   ├── architecture.d2          (Stage 2: D2 architecture diagram)
│   ├── architecture.ofk         (Stage 2: OpenFlowKit architecture)
│   ├── review.md                (Stage 3: APPROVED gate)
│   ├── pipeline-state.md        (Audit log)
│   ├── pipeline-simple.d2       (D2: Simplified pipeline flow)
│   ├── pipeline-simple.svg      (D2: Simplified pipeline output)
│   ├── pipeline-consolidated.d2 (D2: Detailed pipeline flow)
│   ├── pipeline-consolidated.svg(D2: Detailed pipeline output)
│   ├── pipeline-flow.png        (Python diagrams output)
│   ├── ideation-flow.png        (Python diagrams output)
│   ├── fix-loop.png             (Python diagrams output)
│   ├── recovery-flow.png        (Python diagrams output)
│   ├── artifact-flow.png        (Python diagrams output)
│   ├── pipeline-architecture.md (Mermaid diagrams)
│   ├── pipeline-architecture-spec.json (draw.io/PDF spec)
│   ├── pipeline-quick-reference.md     (Quick reference card)
│   └── Diagram-Generation-Spec.md      (Diagram tool specs)
├── reports/
│   ├── code-review.md           (Stage 5)
│   └── issues.md                (Stage 6: fix loop input)
├── products/<project>/
│   ├── pipeline.json            (Project config)
│   ├── checkpoints/             (Recovery checkpoints)
│   ├── selective_runs/          (Selective agent runs)
│   └── dlq/                     (Dead letter queue)
├── Multi-Agent-workflow.md      (this file)
├── dashboard.html               (pipeline monitoring UI)
└── serve.py                     (Python server for dashboard)
```
├── Multi-Agent-workflow.md      (this file)
├── dashboard.html               (pipeline monitoring UI)
└── serve.py                     (Python server for dashboard)
```