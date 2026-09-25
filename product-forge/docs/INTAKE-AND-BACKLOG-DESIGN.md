# Idea Intake → Overall Backlog → Analysis — Design

Status: **proposal (no code until confirmed)**. Supersedes `docs/BACKLOG-AND-INTAKE.md`.
Reuses the **existing** intake engine (no duplication): `core/conversation_models.py`,
`core/conversation_compiler.py`, `core/intent_router.py`, storage `products/.conversations/*`,
API `/api/v1/intake/*`, adapters `adapters/{chatgpt,claude,gemini}` (original dashboard design).

## 0. Locked decisions (from user)
- **Lane naming:** `Overall Backlog` with lanes `Inbox · Ideas/Parking · New Projects · Projects · Product Forge`.
- **Projects lane lists a project only if something was sent for it** (a change/feature/context). Same rule for Product Forge.
- **"Backlog 1, 2, 3…"** = **arrival order labels**, not iterations/releases. Each intake item gets tagged
  **scope-prefixed**: `PF Backlog N` (Product Forge) / `<Project> Backlog N`, sequentially per scope as it comes in from adapters.
- **explore_only** items are **parked with a follow-up date**; the system raises **weekly review prompts**; a prompt can be **snoozed**.
- **Batch analysis scope = per project backlog and per Product Forge backlog** (not globally).
- **Adapters:** keep the three original (`chatgpt`, `claude`, `gemini`) **plus one Generic API** callable from any other app.
- **Parked review cadence = weekly, snoozable.** `new_project` promotion **requires HIL approval**.

---

## 1. Intents
| Intent | Example | Destination (after analysis) |
|---|---|---|
| **new_project** | "a meal-planner app" | **New Projects** lane → triage → may become a project |
| **project_change** | "add CSV export to e2e-free" | that **project's backlog** |
| **forge_change** | "add change-package view to Product Forge" | **Product Forge backlog** |
| **explore_only** | "what if we did X someday" | **Ideas / Parking** (no scheduling; follow-up date) |

Projects/Product Forge appear in Overall Backlog **only when at least one item exists** for them.

---

## 2. Object model
```
Adapter → POST /api/v1/intake  |  POST /api/intake (generic)
   ▼
Conversation (raw, provenance)                       .conversations/conversations.json
   │ compile → ExtractedIdea / Requirement / Decision  .conversations/{ideas,decisions}.json
   ▼ classify + analyze
BacklogItem   (schedulable unit)
   │  type: idea | project | change | explore
   │  scope: project:<id> | product_forge | new_project | parking
   │  label: "Backlog N"  (sequential within scope, arrival order)
   ▼ accept(now|later) → schedule
Project run / Product Forge (self-)enhance ─► Plan ─► ChangePackages ─► done → closed
```
- **Conversation** = raw/audit, never scheduled.
- **BacklogItem** = only schedulable unit; `type`/`scope` are **analysis output**.
- **label** = `Backlog N` per scope (N increments on arrival; stable display id). Internal id `BI-####`.
- Parked items carry `follow_up_at`, `review_every` (default **7 days**), and `snooze_until`; a weekly sweep raises review prompts.

---

## 3. Overall Backlog — dashboard IA
```
Overall Backlog
├── Inbox (received, not yet analyzed)                    [count]
├── Ideas / Parking      → items + follow-up date + review prompt
├── New Projects         → candidate products (triage → promote to project)
├── Projects             → only projects with items
│   └── <project>        → Backlog 1 · Backlog 2 · Backlog 3 …
└── Product Forge      → only when items exist
    └── Backlog 1 · Backlog 2 · Backlog 3 …
```
Per lane row: `label (Backlog N) · title · type · source · confidence · value/effort/risk · status · received_at · follow_up_at`.
Actions: **analyze one · analyze this backlog (batch) · accept now/later · reject · move/re-route · set follow-up · snooze review**.
- **new_project** promotion creates the project via portfolio (`run_portfolio add`) **only after HIL approval**.
- Parked items: weekly review prompt (7-day cadence); `snooze` pushes `snooze_until` and suppresses prompts.

---

## 4. Backend architecture
```
adapters(chatgpt|claude|gemini|generic) ─► IntakeService ─► Classifier/IntentRouter ─► AnalysisService ─► BacklogRegistry
                                            (normalize,      (4 intents, scope+label        (single + per-backlog    (per-scope
                                             dedupe, store    assignment)                    batch)                    stores)
                                             conversation)                                                            │
                                                                                                        Scheduler ◄──────┘
                                                                                              (portfolio.enqueue | product_forge self-enhance)
```
| Component | Backing |
|---|---|
| Adapter registry | **refactor** `core/intake.py` → `core/intake_adapters.py` (per-source `adapters/<src>/{schema.yaml,instructions.md}`; add `generic`) |
| Conversation intake | existing `conversation_models` + `conversation_compiler` |
| Classify/route | `core/intent_router.py`; explicit `scope`/`type` in payload wins if present |
| Analysis | **new** `core/backlog_analysis.py` (single + per-backlog batch) |
| Backlog registry | `core/backlog.py` extended: `scope`, `label (Backlog N)`, `type`, `follow_up_at`, provenance |
| Scheduling | `core/portfolio.py:enqueue` / `core/enhance.py` + `core/capacity.py` |
| Follow-ups | aging/date check → notifications (reuse `core/notifications`) |
| Persona | `core/persona.py` feeds sense-making + accept |

---

## 5. Analysis
**A. Single** (`analyze(id)`): `sense_making (sound|weak|unclear)`, `duplicate_of`,
`value/effort/risk`, `moscow`, `suggested_scope` (`project:x | product_forge | new_project | parking`), `why`.

**B. Per-backlog batch** (`analyze(scope=<project|Product Forge>)`) — runs on one project's backlog or the
Product Forge backlog:
- **Dedupe** → `dup_groups` (keep-one recommendation)
- **Union/Merge** → `merge_groups` (proposed merged title/body)
- **Sense** → nonsense / stale / out-of-scope items
- **Routing** → project vs Product Forge vs new project, with rationale
- **Sequencing** → dependencies + suggested order

Results stored as a **Backlog Analysis Report**; applied only on confirm (HIL, or `human` proxy in auto mode).

---

## 6. API surface
```
# adapters (existing contract preserved)
POST /api/v1/intake · /upload-chunk · /upload-complete
POST /api/v1/intake/{id}/compile|approve|reject|route
GET  /api/v1/intake/{id}/messages|ideas|analysis|plan|preview
GET  /api/v1/intake/instructions?source=chatgpt|claude|gemini|generic
# backlog + analysis
GET  /api/v1/backlog?scope=&status=          (Overall Backlog read model)
POST /api/v1/backlog/{id}/triage|accept|close|move|follow-up|snooze
POST /api/v1/backlog/analyze {scope:"project:x"|"product_forge"}
GET  /api/v1/backlog/reports/{run_id}
# generic ingestion (from any external app)
POST /api/intake            GET /api/backlog   GET /api/persona
```

---

## 7. Statuses
`received → compiled → triaged → accepted(later) → queued → scheduled → executing → implemented → verifying → done`
terminal: `rejected | duplicate | merged | parked | wontfix` (`parked` ⇒ has `follow_up_at`)

---

## 8. Phases
- **P0** align intake: `core/intake_adapters.py` registry → conversation engine; `/api/intake` delegates. *No behavior loss.*
- **P1** BacklogItem model: `scope`, `label (Backlog N)`, `type`, provenance, `follow_up_at`.
- **P2** classify 4 intents → route to correct lane/backlog; per-scope sequential labelling.
- **P3** single-item analysis.
- **P4** per-backlog batch analysis (dedupe / union / routing) + report + confirm-apply.
- **P5** scheduling (accept now → portfolio / Product Forge self-enhance) + capacity gate.
- **P6** parked review prompts: **weekly** sweep (7-day), `snooze` support, via `core/notifications`.
- **P7** adapters: `generic` schema/instructions; verify chatgpt/claude/gemini against new backend.
- **P8** Dashboard: **Overall Backlog** page (lanes above) + per-project/Product Forge backlog views + analysis UI.

## 9. Confirmed decisions
1. `Backlog N` numbering is **per scope** (each project restarts at 1; Product Forge has its own).
2. Parked review: **weekly** prompt, **snoozable** (`snooze_until`).
3. `new_project` promote → create project via portfolio (`run_portfolio add`) **with HIL approval**.

## 10. ONE backlog — Intake + pipeline share it (decision)
**Yes — one ledger, sectioned. Not multiple backlogs.**

There is a single source of truth for *work items* (`BacklogItem`, per scope), which **both** intake and the
running pipeline read and update. Execution detail stays where the pipeline already keeps it, **linked** to the
item (never duplicated as a second backlog).

**Dashboard sections = filters over the same records, not different stores:**
```
Overall Backlog
├── Intake     (origin=intake)  received · compiled · triaged · parked      ← adapters land here
├── Pipeline   (origin=pipeline) accepted → queued → scheduled → executing → verifying   ← pipeline drives these
└── Done       (done · rejected · duplicate · merged · wontfix)
```

**Two origins, one store (product-level rule):**
- `origin=intake`   — items arriving from external adapters (chatgpt/claude/gemini/generic).
- `origin=pipeline` — items the **pipeline itself** produces: enhancement/change features, RCCA follow-ups,
  tech-debt, defects promoted to work items, insights. They enter the **same** `backlog/open.json`.
- Same at the **Product Forge scope**: `products/backlog/` holds Product Forge intake items + Product Forge self-improvements in one ledger.
- Pipeline **updates the same record's status** (single writer); no per-origin store.

**Product Forge backlog (`scope=product_forge`) — same shape, two origins:**
```
products/backlog/
├── open.json     ← Intake (origin=intake)  +  Pipeline (origin=pipeline)
└── closed.json
```
- `origin=intake`   — external ideas sent **about the Product Forge** (chatgpt/claude/gemini/generic).
- `origin=pipeline` — the Product Forge's **own observations while building projects**: recurring defects, RCCA follow-ups,
  insights, capacity/token issues, missing capabilities, tech-debt of the Product Forge itself.
- Same statuses, same sections (Intake | Pipeline), same APIs with `scope=product_forge`; scheduling = Product Forge **self-enhance**
  (`core/enhance.py`), subject to `core/capacity.py`.
- In **Overall Backlog**, `Project Product Forge` lane + each project lane are just `scope` filters over one model.
- Product Forge backlog is **per-arrival labelled `Backlog 1, 2, 3…`** independently of any project.

**Bridge to execution (already half-built):**
1. An accepted `project_change` item becomes/updates a **feature in `products/<p>/product-plan.json`** carrying `epic: BI-####`.
2. `core/iteration_planner.py` groups features **by `epic`** → **iteration** (= one implementation run / sprint).
3. `pipeline-state.json` + stage/gate records + test cycles + defects + change packages + builds + git **reference the `epic`/iteration**.
4. Pipeline events **project the item status back** into the ledger (single writer) — so the same record shows `executing → verifying → done` without a second backlog.

**Product Forge** = same ledger with `scope=product_forge`; its iterations = Product Forge self-enhance runs.

**Ownership rule:** backlog owns *intent + item status*; pipeline owns *execution artifacts*. One writer per file;
status flows one way (pipeline → projector → ledger).

| Detail | Lives in | Linked by |
|---|---|---|
| Raw intake | `.conversations/*` | `conversation_id` |
| Work item | `backlog/{open,closed}.json` | `id` (`BI-####`) |
| Feature to build | `products/<p>/product-plan.json` | `feature.epic` |
| Iteration/run | `iteration_planner` + `pipeline-state.json` | `iteration_id`, `epic_ids[]` |
| Tests/QA | `quality-metrics.json`, `qa-manifest.json`, test cycles | `epic` |
| Defects | defect store | `epic` |
| Builds/git | `builds/`, `core/vcs.py` check-ins | `epic` |
