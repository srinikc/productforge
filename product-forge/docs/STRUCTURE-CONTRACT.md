# Structure Contract (Product Forge)

**Purpose:** every new feature/module/store added to Product Forge or a project follows ONE structure —
so nothing is ever again created as a file/instance-specific island. This document is *enforced*, not advisory.

## 1. Golden rules
1. **One truth per concern.** One authoritative store per concern; everything else links by id.
2. **One writer per file.** Only the owning module writes it; others read.
3. **References are ids only** — never copies. Work artifacts carry `item_id` (`BI-####`) and,
   where technical, `feature_id` (`F-x`).
4. **Derived files are generated** (never hand-edited) and marked as derived in the registry.
5. **Placement:** per-scope stores live under `products/<project>/` or `product-forge/`;
   global config under `config/`. Never invent a new top-level directory.
6. **Naming:** it is **Product Forge** — the token `factory` must not appear in code/config surfaced data
   (legacy read-compat shims are allowlisted in the audit).

## 2. Where things live
| Concern | Store (truth) | Owner module |
|---|---|---|
| Work items (intake + pipeline) | `<scope>/backlog/{open,closed}.json` | `core/backlog.py` |
| Raw intake | `.conversations/*` | `core/conversation_models.py` |
| Technical decomposition | `product-plan.json` | `core/product_plan.py` |
| Execution state | `pipeline-state.json` | `core/pipeline_executor.py` |
| Problems | `defects/<scope>/defects.json` | `test-framework/core/defect_tracker.py` |
| Evidence | `ledger/agent_ledger.json` | `core/agent_ledger.py` |
| Insights (single store) | `insights.json` | `core/cross_project_learning.py` |
| Scheduling | `product-forge/portfolio/*` | `core/portfolio.py` |
| Config | `config/*.json` | per-module |
| Derived reports | `docs/*.md`, `qa-manifest.json`, `qir.json`, `go-no-go.json`, `*-report.json` | generators |

Full machine-readable list: **`config/store-registry.json`** (every store declares `visibility`).

### Visibility tiers — SSOT is per-concern, not blanket
| `visibility` | Meaning | Obligations |
|---|---|---|
| **`shared`** | used across modules/scopes (31) | strict SSOT: one writer, referenced by id, never copied (e.g. backlog, `project.json`, `product-plan.json`, defects, insights) |
| **`scope-local`** | one scope (a project or Product Forge), several readers (42) | one writer per file; ids referenced; not duplicated across scopes (e.g. `pipeline-state.json`, `qa-manifest.json`, `agent_ledger.json`) |
| **`module-local`** | one module's own state/cache/report (36) | only: declared, single writer, derived/local, **not** referenced across modules (e.g. caches, alerts, logs) |

Rule of thumb: keep a concern **module-local** until ≥2 modules need it; only then promote it
(and update `visibility`). Don't merge different concerns just to reduce file count.

## 3. Adding something new — decision tree
```
Is it WORK (something someone wants done)?
├── yes → create it as a BacklogItem via core/backlog.py (add_epic/ensure_item).
│         Do NOT create a new file. Links: item.links.{feature_id,defect_ids,...}
└── no  → is it DETAIL/evidence of existing work?
          ├── yes → attach to the existing owner store + set item_id/feature_id.
          └── no  → is it a NEW CONCERN?
                    ├── reuse an existing concern if at all possible
                    └── else: (1) register it in config/store-registry.json
                              (owner, kind, scope) (2) single writer (3) link item_id
                              if work-related (4) mark derived if generated
                              (5) run scripts/dev/wired_audit.py
```
**New module that tracks status?** It must either read the registry-owned store or add itself to the registry — never write another module's file.

## 4. How it is enforced (not remembered)
| Gate | What it does |
|---|---|
| `scripts/dev/wired_audit.py` | (a) **naming** — fails on `factory`; (b) **store advisory** — lists data files missing from `store-registry.json`; (c) unwired modules |
| `templates/ci/{github-actions,gitlab-ci}.yml` | runs the audit in CI (build fails on violations) |
| **PR merge gate** (`core/pr_gate.py`) | checklist item `structure_contract` — runs the audit; merge blocked on fail/HIL-only override |
| **Spec-review gate (3a)** | spec reviewer must confirm the change respects this contract |
| **Code-review stage** | reviewer checks: no new unregistered store, ids not copies, derived files marked |
| **Agent context** | `AGENTS.md` (root) states the rules for every agent/contributor |
| **Registry** | `config/store-registry.json` is the SSOT of stores; adding drift shows up in CI output |

## 5. Author checklist (copy-paste into a PR/change)
- [ ] Is this work? → registered as a BacklogItem (`BI-####`), not a new file.
- [ ] Store I write is in `config/store-registry.json` and I am its declared owner.
- [ ] My records reference `item_id` (and `feature_id` where technical) — no duplicated status.
- [ ] Generated/derived files carry a `generated` marker and are not hand-edited.
- [ ] Files live under `products/<project>/`, `product-forge/` or `config/` — no new top-level dirs.
- [ ] `python scripts/dev/wired_audit.py` exits 0.
- [ ] No `factory` token in code/config (Product Forge naming).

## 6. Scope note
This is a **one-time migration** (naming + unification). From here on, the gates above keep it aligned;
new features are added *into* the structure rather than beside it.
