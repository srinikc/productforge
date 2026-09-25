# Tracking / SSOT Audit — naming + status-bearing stores

Scope: repo-wide scan of code/config/adapters (excl. `products/**`, `build/**`, `.backups`).
Answers: (1) is `feature_id` the shared key? (2) rename `factory`→Product Forge everywhere (nothing stored as "factory");
(3) does every component follow one-SSOT? (4) other tracking items to streamline.

---

## 1. Naming inventory — "factory" (must become Product Forge)
**690 occurrences across 112 files.** Nothing internal may be *stored/surfaced* as "factory"; discussion only.

| Kind | Occurrences | Action |
|---|---|---|
| Prose/docs/UI strings | bulk | → "Product Forge" (safe) |
| `core/factory_supervisor.py` (40) | module name | → `core/forge_supervisor.py` + import alias |
| `core/factory_constitution.py` (5 refs) | module name | → `core/forge_constitution.py` + alias |
| `core/conversation_models.py`, `core/intent_router.py`, `core/code_analyzer.py` (37/17/…) | **stored enum** `factory_improvement` / `FACTORY_IMPROVEMENT` | new value `product_forge_improvement`; **read alias** for old; migrate stored JSON |
| `pipeline_dashboard/api/router.py`, `dashboard.html` | route `/api/factory/*` | → `/api/forge/*` (keep old route as alias) |
| `adapters/{chatgpt,claude,gemini}/*` | brand text, `send-to-factory.user.js`, OpenAPI title | → Product Forge / `send-to-product-forge.user.js` |
| `pipeline_dashboard/**` | old dashboard product | handle during **rewrite** (not patched) |

**Staged plan (P0-Naming):** (a) new identifiers (dirs `product-forge/`, `scope=product_forge`, `forge_change`);
(b) module renames + import aliases; (c) enum rename + read-alias + one-shot migration; (d) route alias;
(e) adapters/brand strings; (f) docs sweep; (g) `wired_audit` rule that fails on new "factory" in core/scripts/dashboard.

---

## 2. Answer to (1): is `feature_id` referenced everywhere?
**Partly today, and not consistently.** Target = **two keys, clear roles:**

| Key | Role | Stored where |
|---|---|---|
| **`item_id` (`BI-####`)** | cross-cutting reference for *work* (plan, defects, tests, iterations, agents, builds, commits, QA, notifications) | `backlog/*.json` (truth) |
| **`feature_id` (`F-x`)** | technical sub-key inside the plan/tests/traceability | `product-plan.json` |

Canonical link: `item.links.feature_id` **and** reverse index `feature.backlog_id`.
Derived docs (`product-plan.md`, `feature-status.md`) gain an `Item` column (generated, not edited).
`defect.affected_features[]` stays, **plus** `defect.item_id` for bug items.

---

## 3. Tracking inventory (all status-bearing stores) + decision

### A. Work-item truth → **fold into backlog**
| Store | Owner | Decision |
|---|---|---|
| `core/change_registry.ChangeRequest{type,priority,status,approved_by,rollback}` + `ImpactAnalysis` | `change_registry.py` | **Fold** → `BacklogItem(type=change)`; keep `ImpactAnalysis` attached to item |
| `.conversations/ideas.json` | `conversation_models.py` | **Staging** → promote to items (keep as raw) |
| `.conversations/change_packages.json`, `implementation_plans.json` | same | link `item.links.cp_ids`; plans stay execution detail |
| `products/<p>/product-plan.json` features | `product_plan.py` | **Linked** (not folded) — technical decomposition |
| `agent_requirements.json` | `agent_requirements.py` | keep (agent capability matrix ≠ work items) |

### B. Execution / quality status → **separate concern, must reference `item_id`**
`pipeline-state.json`, `project-status.json`, `qa-manifest.json`, `qir.json`, `go-no-go.json`,
`spec-review.json`, `insights.json`, `cycles.json`, `build-info.json`, `build-manifest.json`, `version.json`,
`traceability.json`, `agent_ledger.json`, `agent-audit-log.json`, `metrics.json`, `quality-metrics.json`.

### C. Ops / control → separate concern (no item link needed)
`control.json`, `circuit-breakers.json`, `budget-tracking.json`, `ports.json`, `notifications.json`,
`messages.json`, `queue.json`, `state.json` (state machine), locks.

### D. Config / registries → not status
`model-tier.json`, `model_registry.json`, `pipeline-definition.json`, `index.json`, `projects.yaml`,
`integration_choices.json`, `tech-stack.json`, `feature_flags`.

### E. Derived reports → **regenerate, never edit**
`feature-status.md`, `PROJECT-STATUS.md`, `final-report.json`, `pipeline-execution-report.json`,
`agent-audit.md`, `docs/*.md` summaries, `footprint.md`, `BOM.md`, `README` sections.

---

## 4. Duplications to fold (the "same status in many files" cases)
| # | Duplicate | Resolution |
|---|---|---|
| U1 | `change_registry.ChangeRequest` vs `BacklogItem(type=change)` | fold → one item registry |
| U2 | `issues/<stage>-*.json` vs `test-framework/defects/*/defects.json` | fold → DefectTracker (issues become defect entries) |
| U3 | `cross_project_learning.ProjectInsight` vs `qa_intelligence insights.json` vs Product Forge `insights/` | one **insights** store, `insight.kind`; Forge items generated from it |
| U4 | `state.json`(state_machine) vs `pipeline-state.json` vs `project-status.json` | `pipeline-state.json` = truth; others **derived** |
| U5 | `version.json` / release state vs `build-info.json` vs `build-manifest.json` | version truth + build truth; manifest **derived** |
| U6 | `agent-audit-log.json` vs `audit-trail.json` vs `agent_ledger.json` | split by purpose: audit-trail = governance events; ledger = work evidence (`item_id`) |
| U7 | `.conversations/` exists twice (`products/` and `pipeline_dashboard/products/`) | single location |
| U8 | `requirements.json` (conversation) vs `product-plan.requirements_index` vs `traceability.matrix` | req staging vs plan mapping vs trace — link by `REQ-*`/`F-*` id, no third copy |

---

## 5. Enforcement (so it stays one truth)
1. **Single writer per file** (table in §8 of BACKLOG-UNIFICATION-ANALYSIS).
2. **Reference rule:** any artifact about work carries `item_id` (and `feature_id` where technical).
3. **Derived files** carry `"generated": true` / banner header; generators only.
4. **`wired_audit` extensions:** (a) fail on `factory` in core/scripts/dashboard; (b) assert no module writes
   `backlog/*.json` except `core/backlog.py`; (c) assert `item_id` present in defect/plan/iteration writers.
5. **Migration** `scripts/dev/migrate_backlog.py`: idempotent; builds items from features + change requests +
   open defects + ideas; normalizes `.conversations` location; renames stored enum values.

---

## 6. Impact on the P0–P9 plan
- **P0** now includes **naming** (module/alias/enum/route) and the `wired_audit` rules.
- **P3** absorbs U2 (issues→defects).
- **P4** absorbs U1 (change_registry→items) and U6 (agent attribution + audit split).
- **P5/P6** absorb U3 (single insights store → Forge items).
- **P7** absorbs U4/U5 (derived state/build reports).
- **P9** migration absorbs U7 (conversations path) and the enum-value rewrite.
