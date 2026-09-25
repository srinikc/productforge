# Adding Anything to Product Forge — Playbook

**Read this before adding any file, store, module, agent, stage, endpoint, config, test, or artifact.**
Companion docs: `docs/STRUCTURE-CONTRACT.md` (rules) · `config/store-registry.json` (the truth registry) ·
`AGENTS.md` (binding rules).

---

## 0. Before you start
1. **Present a plan/options and get confirmation** — including re-iterations. No silent coding.
2. Ask: *does this already exist?* Reuse before you create (grep `config/store-registry.json`, `core/`, `docs/`).
3. Decide **scope**: `project` (`products/<project>/`), `product_forge` (`product-forge/`), or `global` (`config/`).

## 1. What am I adding? (route by kind)
| I'm adding… | Goes where | Read recipe |
|---|---|---|
| A feature / bug / idea / change request | **backlog item** (`core/backlog.py`) — *never a new file* | A |
| A new module | `core/<name>.py` | B |
| Something that stores data | registered store in `config/store-registry.json` | C |
| A setting / tunable | `config/<name>.json` | D |
| An agent | `agents/<id>.agent.json` + `config/agent-hierarchy.json` | E |
| A skill | skill registry (`core/skills_registry.py` / test-framework) | F |
| A pipeline stage | `pipeline-definition.json` | G |
| An API endpoint | `dashboard/server.py` (new) / `pipeline_dashboard/api/router.py` (legacy) | H |
| A test | `test-framework/` (categories/matrix) | I |
| A report/artifact | generated only | J |
| A data migration | `scripts/dev/migrate_*.py` | K |

## 2. Common steps (every change)
1. Branch from the working branch (`core/vcs.py`: `feature_branch`).
2. Implement **one concern**; single writer.
3. **Wire it** — must be invoked on the runtime path (import + call), not just defined.
4. Add/extend tests; run the project test cycle.
5. Run the required checks:
   ```
   python -m compileall -q core scripts dashboard
   python scripts/dev/wired_audit.py      # naming + store registry + unwired
   ```
6. End the task with an explicit **wiring update** (what now invokes it, when).
7. Update the relevant doc (`docs/*`) and, if it's a store, `config/store-registry.json`.

---

## A. Work item (feature / bug / idea / change)
**Never** create a file for work. Create a BacklogItem:
```python
from core import backlog
item = backlog.add_epic("project", "<project>", title="Add CSV export", type_="change",
                        origin="intake", value=4, effort=2, risk=2, moscow="Should")
```
- Link technical detail by id (never copy): `backlog.link(scope, project, item["id"], feature_id="F-9")`
- Status flows: `new → triaged → accepted → queued → scheduled → executing → verifying → done` (single writer = `core/backlog.py`).
- Parked/explore items: `backlog.set_follow_up(...)` (weekly review, snoozable).
- From the pipeline/insights: `backlog.ensure_item(..., external_id="defect:D-3", origin="pipeline")` (idempotent).

**Requirement context (the `body`).** A work item must be understandable WITHOUT reading code.
`title` is a one-line summary; `body` carries the full requirement context. Use these sections
(omit the N/A ones), so every item answers the same questions:
```
## Problem / why
## Goal & value
## In scope / Out of scope
## User flow
## Backend flow (consumed, by id)
## Acceptance criteria (testable G/W/T)
## Data model (what is stored, where, owner)
## API contract (endpoints + payloads)
## UX (screens / elements / states)
## Edge cases & errors
## Dependencies & links (by id)
## Open questions
## Verification / test plan
```
Heavy artifacts (design doc, mockups, specs) stay in their **owner store** and are referenced by
`item_id` — never copied into the body. Unknowns are recorded under **Open questions**, not omitted.
Reference example: dashboard `BI-0132` (Agents window: edit agent card + model browser + stop/re-run).

## B. New module
1. `core/<name>.py`, module docstring stating the **single concern** and its **owner store** (if any).
2. Naming: **Product Forge** (no `factory` token anywhere).
3. Expose a small API; no import-time side effects (no writes at import).
4. **Wire it** into the runtime path (executor / orchestrator / portfolio / dashboard) — the audit fails otherwise.
5. If it writes data → recipe C. If it's a status-bearing thing → it must reference `item_id`.
6. Add a test; update `docs/IMPLEMENTED-FEATURES-WIRING.md`.

## C. New data store
1. Add an entry to `config/store-registry.json`:
   ```json
   "mystore.json": {"owner": "core/mymodule.py", "kind": "work-items|execution|derived|config|control|evidence|insights|problems|scheduling|intake-raw",
                    "scope": "project|product_forge|global", "concern": "one sentence"}
   ```
2. **One writer**: only the owner module writes it (read-only for everyone else).
3. Placement: `products/<project>/…`, `product-forge/…`, or `config/…`. No new top-level dirs.
4. If work-related → carry `item_id` (+ `feature_id` where technical).
5. If generated → `kind: derived`, mark output (`"generated": true` / header banner), never hand-edit.
6. Fixtures/templates/external files → add a glob to the registry `allow` list (not a fake store).
7. Re-run `wired_audit` → store advisory must not list it.

## C2. When the audit flags a NEW file (triage → decide → wire)
`wired_audit` only *detects*. A flag is not yet a store — convert it with these decisions, in order:

1. **Is it even a store?**
   - generated report / artifact → `kind: derived` (must be regenerated, never edited)
   - fixture / template / external tool file / schema / deploy descriptor for a built product
     → add an `allow` glob in `config/store-registry.json` (it is not a truth)
   - JSON Schema, CI file, stack file (`pubspec.yaml`, `tauri.conf.json`, …) → `allow`
2. **Does the concern already exist?** → **fold** into the existing store (never a second truth).
   If folding needs code changes → raise a **backlog item** (`core/backlog.py`, `origin=pipeline`).
3. **Decide the owner = the single writer.** Exactly one module writes it; everyone else reads.
   *If more than one module must write → that is a design smell: introduce a facade*
   (like the planned `core/budget.py`, `core/project_store.py`).
4. **Decide `kind`** (`work-items | intake-raw | decomposition | execution | problems | evidence |
   insights | scheduling | control | config | derived | audit`) and **`scope`**
   (`project | product_forge | global`).
5. **Decide placement** — `products/<project>/…`, `product-forge/…`, or `config/…`. If it is in the
   wrong place, move it (back-compat read for one release).
6. **If it represents work** → it carries `item_id` (`BI-####`), and `feature_id` where technical.
7. **Wire it** — confirm it is actually written/updated on the runtime path and read by its consumers;
   update `docs/IMPLEMENTED-FEATURES-WIRING.md`. Unwired stores get deleted, not registered.
8. **Register it** in `config/store-registry.json` (owner, kind, scope, concern) and run:
   ```
   python scripts/dev/wired_audit.py        # must exit 0 (naming + stores + diff)
   ```
   Only after a reviewed change: `python scripts/dev/wired_audit.py --snapshot` to refresh the
   new-file baseline (`config/file-manifest.json`).

**Rule of thumb:** if steps 1–2 don't clearly identify an existing owner and concern,
you are probably about to create a duplicate — stop and fold instead.

## D. New config
1. `config/<name>.json` + a loader (`core/<module>.py:load()`), sane defaults when missing.
2. Precedence must be explicit: HIL > project > choices > recommendation > env > default (see `core/feature_flags.py`).
3. Register in `store-registry.json` (`kind: config`, `scope: global|project`).
4. Document the keys in `docs/`.

## E. New agent
1. `agents/<id>.agent.json` (`AgentSpec`) — id, role, deliverable, `enable_tools`, `enable_delegation` (OFF unless needed).
2. Parent link in `config/agent-hierarchy.json` (sub inherits parent model — universal rule).
3. Stage wiring in `pipeline-definition.json` (which stage invokes it) + artifact outputs.
4. Add the compliance checklist (`core/compliance_check.py` `AGENT_CHECKLISTS`) and output checklist if it produces markdown.
5. Regenerate cards: `python scripts/dev/generate_agent_cards.py`; verify `.opencode/agent/*.md`.
6. QA/verify role → must appear in the QA matrix if it gates quality.

## F. New skill
1. Implement under the skills registry (`core/skills_registry.py` / `test-framework`), declare inputs/outputs.
2. Register it; reference it from the agent that uses it.
3. Add a smoke test.

## G. New pipeline stage
1. Add to `pipeline-definition.json`: id, deps (must be satisfiable), agent, inputs, outputs.
2. Artifacts go to `products/<p>/artifacts/<stage-id>/` by convention.
3. Gates: if it can block, define the gate + HIL override rule (mirror `10a`/`3a`).
4. Update `docs/ORCHESTRATION.md` + the stage list in `docs/IMPLEMENTED-FEATURES-WIRING.md`.

## H. New API endpoint
1. Prefer the **new dashboard** (`dashboard/server.py`); legacy router only for adapter-visible contracts.
2. Read-only over the truths; **actions go through core modules** (e.g. backlog actions call `core/backlog.py`).
3. Scope-parameterized: `?scope=project:<id>|product_forge`.
4. Never write a store from the API layer directly.
5. Document in `docs/` + keep adapter contracts stable (add aliases, don't break).

## I. New test
1. Follow the location convention (project tests under the project; framework helpers in `test-framework/`).
2. Pick the category from `config/test-matrix.json` (unit/api/db/ui/e2e/nfr/security/…).
3. Wire it so the cycle actually runs it; keep it deterministic (no network/flake).
4. Update the matrix if a new category is needed.

## J. New report / artifact
1. It is **derived** — write it in a generator, mark it, register `kind=derived`.
2. Never source-of-truth: it must be reconstructible from the registered stores.
3. Add it to the dashboard as a read-only view if it matters.

## K. Migration (new/renamed store or field)
1. `scripts/dev/migrate_<thing>.py` — **idempotent**, dry-run flag, logs actions.
2. Readers must keep **back-compat fallback** to the legacy path/name.
3. Run the audit after; keep the legacy shim allowlisted (do not leave it nameless).

---

## 3. Never do this
- ❌ Create a new file to track work (features, ideas, changes, bugs) — use the backlog.
- ❌ Write another module's store, or duplicate a status that already has an owner.
- ❌ Copy data between stores instead of linking by `item_id` / `feature_id`.
- ❌ Hand-edit a derived file.
- ❌ Add a top-level directory, or a store outside `products/`, `product-forge/`, `config/`.
- ❌ Use the token `factory` (it's **Product Forge**).
- ❌ Add a module that is never invoked.
- ❌ **Recursively delete shared state** in a script/test (`rmtree`/`Remove-Item -Recurse` on
  `product-forge/`, `products/<p>/backlog/`, `products/.conversations/`, `products/ledger/`,
  `products/inbox/`). Use your own scratch path `products/_test_<name>/`.
  Enforced by `wired_audit.destructive_audit()`.

## 4. Copy-paste checklists
**Small change**
- [ ] No new file for work; links by id
- [ ] `compileall` + `wired_audit` exit 0
- [ ] wiring update written; docs updated if behavior changed

**New module/store/config/agent/stage**
- [ ] Plan confirmed before coding
- [ ] Registered in `config/store-registry.json` (owner/kind/scope/concern)
- [ ] Single writer; `item_id` where work-related; derived marked
- [ ] Wired on the runtime path; invoked at a named point
- [ ] Tests added; audit exit 0; CI + `pr_gate.structure_contract` green
- [ ] `docs/` updated (contract/registry/wiring/orchestration as applicable)

## 5. Where to look
| Need | File |
|---|---|
| Rules | `docs/STRUCTURE-CONTRACT.md` |
| Truth registry | `config/store-registry.json` |
| Binding agent rules | `AGENTS.md` |
| Wiring inventory | `docs/IMPLEMENTED-FEATURES-WIRING.md` |
| Orchestration/stages | `docs/ORCHESTRATION.md`, `pipeline-definition.json` |
| Gates | `core/pr_gate.py` (`structure_contract`), `core/qa_report.py` (Go/No-Go) |
| Checks | `python -m compileall -q core scripts dashboard` · `python scripts/dev/wired_audit.py` |
