# Backlog Unification — Detailed Analysis & Plan

Goal: **one backlog per scope** (each project + Product Forge) carrying `origin` + `status`,
referenced by pipeline, portfolio, and agents — E2E, no gaps. No second/n-th store for the same purpose.

## 0. Executive summary (TL;DR)
1. Today work-item-ish data is spread over **7+ stores** (product-plan features, feature-status.md,
   agent_ledger, issues/*, test-framework defects, intake conversations, Product Forge docs) with **no shared key**.
2. Fix = **one `BacklogItem` registry per scope** (`products/<p>/backlog/`, `product-forge/backlog/`) that everything
   references; the other files stay as **detail/evidence stores**, linked by id — not duplicated.
3. **Plan ≠ Backlog**: plan = *how it's built* (modules/features, technical state); backlog = *what work is wanted*.
   A `type=feature` item and a plan `Feature` are the same thing from two sides → linked by `feature_id`.
4. **One truth per concern, one writer per file** (§8). Derived views (`feature-status.md`, boards, QIR) are
   regenerated, never hand-edited.
5. **Product Forge's own state moves out of `products/pipeline_dashboard/`** (old dashboard product we're rewriting)
   into a dedicated `product-forge/` namespace (§9); new `dashboard/` is **read-only** and owns nothing.
6. Refactor = **additive bridges only** (no pipeline/product-plan/defect rewrite).


---

## 1. Inventory — everything that currently holds work-item-ish data

### 1.1 Project scope (`products/<project>/`)
| Store | Shape | Owner (writer) | Purpose |
|---|---|---|---|
| `product-plan.json` → `modules[].features[]` | `Feature{id, name, status, priority, module, phase, description, requirements[], implementation, testing, security, code_review}` | `core/product_plan.py:ProductPlan`; drivers `core/orchestrator/feature_tracker.py`, `orchestrator/checkpoint.py`, `stage_runner.py` | **the de-facto work items** (what to build) |
| `docs/feature-status.md` | markdown table `F-x · name · priority · status` | `core/project_journal.py:write_feature_status` (via checkpoint) | **projection/report** of the above |
| `ledger/agent_ledger.json` → `work_items[]` | `AgentWork{id, agent, project, stage, action, files_written/read, inputs_used, output_produced, status, started/completed, error, metadata}` | `core/agent_ledger.py`; created by `core/product_ingestion.py` | **agent execution log** (currently empty/unused in e2e-free) |
| `traceability.json` → `matrix[]`, `coverage_metrics` | requirement→feature→test matrix | `product-plan`/spec stages | requirements trace |
| `issues/<stage>-<agent>-issues.json` | `{project, stage, agent, issues[], counts}` | stage agents (validate/security/nfr) | **per-stage issues** (overlaps defects) |
| `test-framework/defects/<project>/defects.json` | `Defect{defect_id, title, severity, status, test_*, root_cause, affected_features[], fix_*, verified_at}` | `test-framework/core/defect_tracker.py` | **defects** (already links `affected_features`) |
| `pipeline-state.json`, `project-status.json` | stage execution status | executor | execution state (not work items) |
| `docs/requirement*.md`, `design.md`, `architecture.md` | narrative | stage agents | narrative |

### 1.2 Intake scope (cross-project)
| Store | Shape | Owner |
|---|---|---|
| `.conversations/conversations.json` | `Conversation{id, source_platform, intent, target_project_id, title, status, messages[]}` | `core/conversation_models.py:ConversationStore` |
| `.conversations/ideas.json` | `Idea{id, conversation_id, project_id, title, description, confidence, status}` | same |
| `.conversations/decisions.json` | decisions | same |
| `.conversations/implementation_plans.json` | `Plan{id, conversation_id, file_changes[], risk_level, requires_tests, rollback_available, status}` | same |
| `.conversations/change_packages.json` | `ChangePackage` | same |
| `pipeline_dashboard/api/router.py` intake handlers | API only | `intake_api_handle_*`, `intake_api_route`, `intent_router` |

### 1.3 Product Forge scope (`products/pipeline_dashboard/`)
| Store | Reality |
|---|---|
| `docs/product-plan.md`, `product-spec.md`, `pipeline-state.md` | markdown only |
| `specs/`, `ledger/`, `backlog/` | **missing — no work-item ledger exists for the Product Forge** |
| `.conversations/` (also a copy under `pipeline_dashboard/products/.conversations`) | intake, shared shape |

### 1.4 Non-runtime duplicate
`build/lib/**` contains a **stale copy** of `core/` (incl. `agent_ledger.py`, `product_plan.py`)
→ must be excluded from wiring/migration (ideally cleaned).

---

## 2. Duplication / gaps found
| # | Issue |
|---|---|
| D1 | **Work items exist in 3 forms**: product-plan `Feature`, intake `Idea/ChangePackage`, and (unused) `agent_ledger.work_items`. No single key linking them. |
| D2 | **Defects vs stage issues** overlap: `issues/*.json` (stage agents) and `test-framework/defects/*/defects.json` are two stores for "problems found". |
| D3 | **No `origin` / `type`** anywhere → intake items, features, defects, and follow-ups are indistinguishable in one list. |
| D4 | **Status flows one way only into features**; backlog/portfolio/scheduler cannot see feature status; feature status cannot see intake status. |
| D5 | **Defects only link `affected_features`**; no item id, so a bug-fix is not a first-class backlog item. |
| D6 | **Product Forge has no ledger at all** (docs only) → its backlog can't be read/updated. |
| D7 | `agent_ledger.work_items` unused → agent work is not attributed to any work item. |
| D8 | **Iterations reference `epic` names** parsed from markdown (`extract_features`), not stable item ids. |
| D9 | Portfolio/agents never read or write backlog → enqueue/self-enhance not item-driven. |
| D10 | `docs/feature-status.md` is a *projection* (fine) but is written from checkpoints, not from the item registry → drift risk. |
| D11 | `build/lib/**` stale copies shadow real modules in searches/tooling. |

---

## 3. Target model — one backlog per scope

```
BacklogItem (registry, SSOT for "work" as a referenceable unit)
  id            BI-0001                (per scope)
  scope         project:<id> | product_forge
  origin        intake | pipeline
  type          idea | feature | change | bug | tech-debt | project | explore
  section       intake | pipeline | done        (derived from status/origin)
  label         "Backlog N" (per scope, arrival order)
  title, body
  status        new|triaged|accepted|queued|scheduled|executing|verifying|done|rejected|parked|duplicate|merged|wontfix
  priority      moscow + value/effort/risk + score
  links         {conversation_id, idea_ids[], cp_ids[], feature_id, defect_ids[], iteration_ids[], commit, artifacts[]}
  provenance    source (chatgpt|claude|gemini|generic|pipeline|...), created_by, created_at, updated_at
  follow_up     {at, every:7d, snooze_until}      (parked/explore only)
```

**Layering rule (nothing duplicated, everything linked):**
- **BacklogItem** = registry everyone references (pipeline, portfolio, agents, dashboards).
- **product-plan `Feature`** = technical decomposition (stays); item links `feature_id`; feature status mirrors to item.
- **Defect** = QA artifact (stays); item links `defect_ids[]`; defect open/resolve mirrors item status.
- **agent_ledger AgentWork** = execution evidence (stays); gains `item_id`.
- **Intake stores** = raw conversations (stay); promotion creates items with back-refs.
- **`docs/feature-status.md`** = projection rendered **from items** (via feature link).

---

## 4. Wiring map (who reads/writes what)

| Bridge | Trigger | Writer | Effect |
|---|---|---|---|
| **B1 plan↔backlog** | `ProductPlan.update_feature_status` / `FeatureTracker.seed\|mark_*` | `core/backlog_link.py` | ensure item for feature; mirror status (`planned→new`, `completed→executing/verifying`, `verified→done`) |
| **B2 intake↔backlog** | `/api/v1/intake` compile/approve/route; `core/intake.py` | adapter bridge | promote Idea/CP → item (`origin=intake`, `type` per intent) |
| **B3 defects↔backlog** | `DefectTracker.add_defect` / resolve | `core/backlog_link.py` | create/close item (`type=bug`, `origin=pipeline`), link `feature_id` from `affected_features` |
| **B4 issues→defects** | stage validate/security/nfr write `issues/*.json` | `test_framework_integration` | route into DefectTracker (single problem store) |
| **B5 agents↔backlog** | agent work recorded | `core/agent_ledger.py` + `stage_runner` | `AgentWork.item_id`/`feature_id`; agents receive item context |
| **B6 iterations↔backlog** | `iteration_planner` | plans by `item.id` | `PlannedIteration.item_ids[]` (§ replace markdown `epic` when available) |
| **B7 portfolio↔backlog** | `accept(now)` / `portfolio.enqueue` | portfolio | enqueue by `item_ids`; capacity gate; status→`queued/scheduled` |
| **B8 Product Forge↔backlog** | insights/RCCA/enhance | `core/enhance.py` + insights | create Product Forge items (`origin=pipeline`); self-enhance consumes them |
| **B9 status projector** | pipeline stage events | `core/backlog.py` (single writer) | item status updated once, idempotent |
| **B10 reports** | checkpoint/report | `project_journal` | render `feature-status.md` + item board from registry |

---

## 5. Phased implementation plan

- **P0 — Backlog v2** (`core/backlog.py`): add `scope/origin/type/section/label/links/provenance/follow_up`;
  one writer + lock + atomic writes; open/closed/history; `ensure_item()`, `set_status()`, `link()`, `list(scope,origin,section)`, `stale()`, `next_label()`.
- **P1 — B1 plan bridge** (`core/backlog_link.py`): `ensure_feature_item()`, `mirror_feature_status()`;
  call from `ProductPlan.update_feature_status`, `FeatureTracker.seed/mark_*`. Idempotent, non-fatal.
- **P2 — B2 intake bridge** (`core/intake.py` → `intake_adapters.py` + promotion): adapters `chatgpt|claude|gemini|generic`;
  compile/approve/route → item; keep `/api/v1/intake/*` contract.
- **P3 — B3/B4 defects bridge**: `backlog_link.on_defect_open/resolve`; route `issues/*.json` into `DefectTracker`.
- **P4 — B5 agent attribution**: `AgentWork.item_id` (+ `metadata.item_id`), set by `stage_runner` per iteration plan.
- **P5 — B6/B7/B8 wiring**: iteration plan carries `item_ids`; `portfolio.enqueue(items)`; Product Forge items + self-enhance.
- **P6 — Product Forge backlog**: create `products/backlog/`; derive initial items from `docs/product-plan.md` + Product Forge insights/RCCA.
- **P7 — B9/B10 projector + reports**: single status writer; render feature-status/board from items.
- **P8 — APIs**: unify `/api/v1/backlog/*` (`list/triage/accept/close/move/follow-up/snooze/analyze`);
  existing feature/iteration endpoints read through the link; keep `/api/intake` generic facade.
- **P9 — Migration + E2E + docs**: `scripts/dev/migrate_backlog.py` (idempotent, per project + Product Forge);
  E2E test `intake → item → feature → iteration → agents → defects → done`; update docs; `wired_audit` green; exclude/clean `build/lib/**`.

---

## 6. Risks / safeguards
- **Two writers**: mitigated by *single writer* = `core/backlog.py` (all others call it).
- **Refactor risk**: bridges are additive + non-fatal (`try/except`) so a bridge failure never breaks a run.
- **Markdown-parsed epics** (`extract_features`) remain a fallback until items carry ids.
- **Stale `build/lib`**: exclude from migration; clean separately.
- **Backfill**: migration is idempotent (`ensure_item` keyed by `feature_id`/`defect_id`/`conversation_id`).

---

## 7. Plan vs Backlog — both exist, different questions

They are **not duplicates**; they answer different questions and have different lifetimes.

| | **Backlog** (`backlog/*.json`) | **Product plan** (`product-plan.json`) |
|---|---|---|
| Answers | *What work is wanted / refused / done?* | *How is the product decomposed to be built?* |
| Unit | `BacklogItem` (intent) | `Feature` inside `Module` (technical) |
| Holds | origin, type, status, priority, request text, provenance, follow-up | module, phase, requirements[], implementation, testing, security, code_review |
| Scope | every project **+ Product Forge** | a project under build (Product Forge: markdown plan today) |
| Lifespan | permanent (arrives → done/rejected/parked) | per build/spec version |
| Contains ideas/explore/new-project? | **yes** | **no** (only accepted, decomposed work) |
| Owner | `core/backlog.py` | `core/product_plan.py` |

Relation: **accepted item → 0..n features**; a `type=feature` item is the *same thing* seen from two
sides → linked by `feature_id` (no content duplication). `idea | explore | project | bug` items may have **no** feature.

**Status mirroring (one direction: feature → item):**
`planned → accepted/scheduled` · `completed → verifying` · `verified → done`.

### Structure (final)
```
# PROJECT (under build)
products/<project>/
├── backlog/
│   ├── open.json           # BacklogItem registry (origin=intake|pipeline)
│   ├── closed.json
│   ├── counters.json       # next BI id + next "Backlog N" label (per scope)
│   └── history/BI-0001.jsonl
├── product-plan.json       # modules[].features[] (+ optional feature.backlog_id)
├── docs/feature-status.md  # projection (rendered from items/features)
└── ledger/agent_ledger.json# execution evidence (work_items[].item_id)

# PRODUCT FORGE
products/
├── backlog/{open.json,closed.json,counters.json,history/}   # scope=product_forge
├── portfolio-registry.json · portfolio-state.json · portfolio.db
└── pipeline_dashboard/docs/product-plan.md                  # Product Forge plan (markdown today)
```

### Mapping examples
| Item | origin | type | links | status |
|---|---|---|---|---|
| `BI-0007` "what if voice notes" | intake | explore | — | parked (follow_up) |
| `BI-0008` "add CSV export" | intake | change | feature F-9 | accepted → verifying |
| `BI-0009` "F-10 Search API" | pipeline | feature | feature F-10 | executing |
| `BI-0010` "redirect 500 on empty slug" | pipeline | bug | defect D-3, feature F-2 | triaged |
| `BI-0003` "Product Forge: cache tier configs" | pipeline | tech-debt | — | queued (scope=product_forge) |

### Do we need to refactor?
**No rewrite — additive bridges only.**

| Change | Type |
|---|---|
| `backlog.py` v2 (scope/origin/type/links/…) | new/extend |
| `core/backlog_link.py` bridge; call from `ProductPlan.update_feature_status`, `FeatureTracker.seed/mark_*`, `DefectTracker.add/resolve` | additive |
| `Feature.backlog_id` (+ `item.links.feature_id`) | additive field |
| `AgentWork.item_id` (metadata) + `stage_runner` passes ids | additive |
| iteration plan carries `item_ids[]` | small change (`iteration_planner` + `stage_runner`) |
| `products/backlog/` for Product Forge + Product Forge items from insights/RCCA | new |
| migration script; unified `/api/v1/backlog/*`; reports render from registry | new |
| **unchanged**: pipeline DAG/stages, product-plan schema, defect tracker internals, conversation storage, portfolio substrate | none |
| **optional later**: make plan features *derived* from items; give Product Forge a `product-plan.json` | deferred |

---

## 8. One truth per concern (ownership + reference model)

**Rule: each concern has exactly one authoritative file and one writer. Everything else links by id.**

| Concern (truth) | Authoritative file | Single writer | Readers | Derived views |
|---|---|---|---|---|
| Raw intake | `.conversations/*` | `ConversationStore` (intake API) | backlog promotion, dashboard | — |
| **Work items / owner status** | `backlog/{open,closed}.json` (per scope) | **`core/backlog.py`** | portfolio, coordinator, agents, dashboard, reports | boards |
| Technical decomposition | `product-plan.json` (Product Forge: own plan) | `core/product_plan.py` | iteration planner, stage runner, agents | `docs/product-plan.md` |
| Execution state | `pipeline-state.json` / `project-status.json` | executor | dashboard, reports | `PROJECT-STATUS.md` |
| Problems (defects) | `test-framework/defects/<scope>/defects.json` | `DefectTracker` | backlog(bug items), QIR/Go-No-Go, dashboard | `qa-manifest`, issues report |
| Execution evidence | `ledger/agent_ledger.json` | `AgentLedger` | dashboard, audit | `agent-audit.md` |
| Scheduling/substrate | `product-forge/portfolio/*` | `core/portfolio.py` | run_pipeline, coordinator | — |
| Reports | `docs/feature-status.md`, QIR, Go/No-Go | generators (read-only) | humans, dashboard | — |

**Cross-references (ids only; never copy content):**
```
conversation_id ─► item(origin=intake) ─► item.links.feature_id ─► Feature ─► iteration.item_ids ─► run
                                              ▲                                   │
defect.affected_features ◄────────────────────┘         AgentWork.item_id ◄─────┘
item.links.defect_ids ─► defect(bug)        item.links.commit/artifacts ─► build/git
```

**Component reference map (who reads/writes what):**
| Component | Reads | Writes |
|---|---|---|
| **Intake/adapters** | adapter schemas | conversations; creates items via promotion |
| **Product Forge** (portfolio, enhance, insights) | product_forge backlog, project backlog summaries | product_forge backlog items; schedules (portfolio) |
| **Project Coordinator** (executor + iteration_planner + stage_runner + feature_tracker) | project backlog (accepted items) → plan → iterations | `backlog.py` (status), product-plan, defects, execution state |
| **Agents** | item/feature context injected per iteration | artifacts + agent_ledger (`item_id`) |
| **Dashboard (new)** | everything | **nothing** (acts only through APIs) |

Anti-drift guarantees: (a) single writer per file; (b) `backlog.py` is the only place that mutates item status;
(c) projections are regenerated, never edited; (d) bridges are idempotent (`ensure_item`) and non-fatal.

---

## 9. Where Product Forge state lives (fix: not inside the old dashboard product)

`products/pipeline_dashboard/` is a **product the Product Forge built** (the old dashboard) — it also currently doubles
as Product Forge config home (`model-tier.json`). That is the naming confusion. New layout:

```
<repo root>/
├── product-forge/                      # Product Forge's OWN state (new)
│   ├── backlog/{open.json,closed.json,counters.json,history/}
│   ├── plan.json                 # Product Forge's own plan (moved from pipeline_dashboard/docs/product-plan.md)
│   ├── docs/                     # Product Forge docs (spec/plan/state)
│   ├── insights/                 # cross-project RCCA/learnings → Product Forge items
│   └── portfolio/{registry.json,state.json,queue.db}
├── config/                       # includes model-tier.json (moved from products/pipeline_dashboard/)
├── products/<project>/           # each built product (backlog/, product-plan.json, …)
└── dashboard/                    # NEW dashboard (read-only; owns nothing)
```
- Old `products/pipeline_dashboard/` = historical product → **archive or remove** after rewrite (not Product Forge state).
- **Migration is back-compat**: readers fall back to legacy paths if the new one is missing, so nothing breaks.

---

## 10. Artifact wiring — PROJECT scope (concrete)

```
products/<project>/
├── backlog/open.json            ★TRUTH: work items (origin=intake|pipeline, type=idea|change|feature|bug|…)
│      │  links.feature_id                                   ▲ links.defect_ids (type=bug)
│      │  links.conversation_id / idea_ids / cp_ids          │
│      ▼                                                     │
├── product-plan.json  ★TRUTH: decomposition (modules[].features[])   │
│      │  feature.backlog_id  ◄─ mirror ── item.status          │
│      ▼                                                        │
├── iteration_planner → iterations(item_ids[])                  │
│      ▼                                                        │
├── pipeline-state.json / project-status.json  ★TRUTH: stage execution
│      ▼                                                        │
├── stage_runner → agents(item/feature context) → src/ tests/ artifacts/
│      │                                                        │
│      ├─ ledger/agent_ledger.json  ★TRUTH: execution evidence (work_items[].item_id)
│      └─ traceability.json         ★TRUTH: requirement↔feature↔test matrix
│                                                               │
├── test-framework/defects/<project>/defects.json  ★TRUTH: problems ──┘
└── DERIVED (regenerated, never hand-edited):
        docs/feature-status.md · docs/product-plan.md · PROJECT-STATUS.md
        qa-manifest.json · quality-metrics.json · final-report.json
```
**Project flow:** adapter → conversation → `item(origin=intake)` → triage/accept → feature(s) in plan →
iteration(`item_ids`) → agents implement/test → defect(s) (`type=bug` item) → fix → `item=done`.
**Defects are per project** — they stay at `test-framework/defects/<project>/defects.json` (one store per scope),
linked to items/features by id.

---

## 11. Artifact wiring — PRODUCT FORGE scope (concrete)

```
product-forge/                          (Product Forge's OWN scope; scope=product_forge)
├── backlog/{open,closed}.json   ★TRUTH: Product Forge items (origin=intake|pipeline)
├── plan.json                    ★TRUTH: Product Forge decomposition (was docs/product-plan.md)
├── insights/                    cross-project RCCA/learnings  ──► create items (origin=pipeline)
├── docs/                        spec/plan/state narrative (some DERIVED)
└── portfolio/{registry,state,queue.db}  ★TRUTH: scheduling across projects (references item ids)

config/  model-tier.json · capacity.json · persona.json · agent-hierarchy.json · test-matrix.json
products/<project>/*   referenced by SUMMARIES only (never copied)
dashboard/             read-only projections of everything
```
**Product Forge item sources (origin=pipeline):** recurring project defects, RCCA follow-ups, insights,
capacity/token issues, missing capabilities, tech-debt of Product Forge itself.
**Product Forge flow:** item(accepted) → `core/enhance.py` (self-enhance) runs the pipeline with
`scope=product_forge` → writes `product-forge/plan.json` + item status; portfolio schedules it like any project.

### Same components, one code path
The coordinator, agents, portfolio, and backlog are **scope-parameterized** — `scope=project:<id>|product_forge`.
There is no second implementation per scope: one registry, one status writer, one set of bridges.

| Component | project scope | Product Forge scope |
|---|---|---|
| Backlog | `products/<p>/backlog/` | `product-forge/backlog/` |
| Plan | `products/<p>/product-plan.json` | `product-forge/plan.json` |
| Defects | `test-framework/defects/<p>/` | `test-framework/defects/product-forge/` |
| Scheduler | `portfolio.enqueue(project)` | `enhance.py` self-enhance (+ portfolio) |
| Dashboard | read-only | read-only |

### Naming sweep note (Product Factory → Product Forge)
Adopted: **Product Forge** everywhere (dir `product-forge/`, `scope=product_forge`, `forge_change` intent).
Repo-wide rename must respect **persisted/legacy identifiers** (safe = docs/UI/brand strings and new code;
careful = stored enum `factory_improvement`, `core/factory_constitution.py`, `/api/factory/*` route,
adapter assets "Send to Factory") → rename with **aliases/back-compat**, in a dedicated pass.





---

## 12. Implementation status (Steps 1–12 done)

| Step | Delivered |
|---|---|
| 1 Naming | Product Forge everywhere; `forge_supervisor`/`forge_constitution`; intent enum migrated with read-alias; `wired_audit` naming gate |
| 2 Backlog v2 | `core/backlog.py` registry (BI-####, scope/origin/type/section/label/links/follow_up), single writer, history |
| Gates | `wired_audit` = naming + store-registry (hardened roots/exts + `allow` globs) + `diff_audit` + `destructive_audit`; `visibility` per store; CI + PR gate (`structure_contract`) |
| 3 B1 | `core/backlog_link.py`; `Feature.backlog_id`; status mirror (planned->accepted, completed->verifying, verified->done) |
| 4 | Agent ledgers unified (`core/agent_ledger.py` canonical; test-framework delegates by explicit path); `core/project_store.py` single writer for `project.json` |
| 5 B2 | `core/intake_adapters.py` (chatgpt/claude/gemini/generic/dashboard/file) -> conversation engine -> item; `adapters/generic/*` |
| 6 | Folds: cross_review (3->1), budget/cost (5->1 via `core/budget.py`), prompt_cache deleted, `pipeline.json` derived projection (`core/pipeline_store.py`), skills-registry spelling, Gemini model id, issues->defects (`defect_loop.route_stage_issues`) |
| 7 | `core/insights.py` single insights store + `promote_to_backlog` (Product Forge items) |
| 8 | Product Forge scope: `product-forge/plan.json` + `state.json` (`core/forge_store.py`); `config/model-tier.json` authoritative (legacy fallback); portfolio moved to `product-forge/portfolio/` |
| 9 | Iterations carry `item_ids`; `portfolio.enqueue(..., item_id=)`; `accept(now)` fixed |
| 11 APIs | `/api/v1/backlog*` aliases; `/api/forge/plan`, `/api/forge/state` |
| 12 | `scripts/dev/migrate_backlog.py` (idempotent) + `scripts/dev/e2e_backlog_check.py` (chain E2E: PASS) |

**Run the checks:**
```
python -m compileall -q core scripts dashboard
python scripts/dev/wired_audit.py          # naming + stores + diff + destructive (exit 0)
python scripts/dev/e2e_backlog_check.py    # intake -> item -> feature -> iteration -> defect -> done
python scripts/dev/migrate_backlog.py      # backfill items for existing projects (idempotent)
```

**Known limitations (documented, not defects):** the store audit is basename-based (same filename in
two dirs is allowed); `pipeline.json` remains as a derived projection until legacy readers migrate;
two skill systems (core vs test-framework) remain separate by scope.
