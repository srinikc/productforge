# AGENTS.md — Product Forge (repo root)

Rules for every agent and contributor working in this repository.

## Identity
- This product is **Product Forge**. The token `factory` must never be stored or surfaced
  (legacy read-compat shims are allowlisted in the audit only).

## Structure (binding)
Read and follow `docs/STRUCTURE-CONTRACT.md` + `config/store-registry.json`.
**Before adding anything (feature, module, store, config, agent, skill, stage, API, test, report): follow
`docs/ADDING-TO-PRODUCT-FORGE.md` — it has the per-kind recipes and checklists.**

Route every addition by kind:
- work (feature/bug/idea/change) → **backlog item** (`core/backlog.py`), never a new file
- detail/evidence → attach to the owner store and reference `item_id`
- new concern → register in `config/store-registry.json` with a single writer

1. **One truth per concern, one writer per file.** Only the owning module writes a store.
2. **Work items live in the backlog** (`core/backlog.py`) — one backlog per scope
   (`products/<project>/backlog/`, `product-forge/backlog/`). Never create a new file for work.
3. **Reference by id:** artifacts carry `item_id` (`BI-####`) and `feature_id` (`F-x`) where technical.
   Never duplicate status/logic in a second store.
4. **Derived files are generated**, never hand-edited (`feature-status.md`, reports, manifests).
5. **Placement:** `products/<project>/`, `product-forge/`, or `config/`. No new top-level directories.
6. **New concern?** Register it in `config/store-registry.json` (owner, kind, scope) and add a single writer.

## Required checks before completing any task
Run from repo root:
```
python -m compileall -q core scripts dashboard
python scripts/dev/wired_audit.py
```
Both must pass (0 unwired, 0 naming violations). The same audit runs in CI and in the
**PR merge gate** (`structure_contract` checklist item).

## Working agreement
- Present a plan/options and get confirmation **before** coding, including re-iterations.
- Build a thing → wire it (invoked on the runtime path) → end the task with an explicit wiring update.
- This is a **product, not a prototype**: full quality gates apply (compliance, spec review,
  build/versioning, boot + category tests, coverage, Go/No-Go, RCCA).
- **Dedup-before-add:** before adding ANY backlog item, run
  `python -m core.backlog --similar "<title/description>"` and EXTEND/MERGE an existing item
  instead of creating a new one (backlog bloat is a compounding cost). Near-duplicate open
  item pairs are surfaced by `wired_audit` (`backlog_duplicate_audit`, advisory) and the
  add path warns when `find_similar` sees a likely duplicate.
- **Dashboard reciprocity review:** every backend-scope item records a `dashboard_impact`
  decision (`needs_dashboard` + reason); create a dashboard item only when needed, cross-link
  it reciprocally with `links.paired_with`, and rely on the advisory validator
  (`core/backlog.reciprocity_warnings()` via `wired_audit`, non-fatal).

## Safety (state)
- **Never recursively delete shared state.** Tests and scripts may only delete their own
  uniquely-named scratch path (`products/_test_<name>/`); deleting `product-forge/`,
  `products/<p>/backlog/`, `products/.conversations/`, `products/ledger/` or `products/inbox/`
  is forbidden. Enforced by `wired_audit.destructive_audit()` (fatal).
