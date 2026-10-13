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

## Standards (binding)
Follow **`docs/ENGINEERING_OPERATING_STANDARD.md` (EOS)** for every change: feature branch (never commit to
`develop`/`main` directly), 360° dependency analysis, fail-closed gates (unknown ⇒ blocked), run-bound evidence,
atomic single-writer state, authorization at the boundary, tests that can fail, and the Definition of Done.
Root-cause every defect via **`docs/RCCA_productForge.md`** (5-Why + a new guard).

1. **One truth per concern, one writer per file.** Only the owning module writes a store.
2. **Work items live in the backlog** (`core/backlog.py`) — one backlog per scope
   (`products/<project>/backlog/`, `product-forge/backlog/`). Never create a new file for work.
   **Every item belongs to an epic.** If none fits, **ask and create the epic first**. Automated creators
   (intake/issues/insights/ops) attach to the best-matching epic, else the **`Unscoped`** holding epic;
   **grooming re-homes `Unscoped` children** into real epics (create or move). Enforced by the baseline-aware
   gate `scripts/dev/backlog_epic_audit.py` (fatal for NEW items) + the advisory `epic-coverage` in
   `wired_audit`. BI-PF-1250.
3. **Reference by id:** artifacts carry `item_id` (`BI-<TAG>-<nnn>`; legacy `BI-####`) and `feature_id` (`F-x`) where technical.
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
  (`core/backlog.reciprocity_warnings()` via `wired_audit`, non-fatal). **Suspended** while
  `config/pf-review-scope.json` marks the dashboard legacy (`dashboard_reciprocity.active=false`) —
  scopes listed under `legacy_scopes` are excluded from reciprocity/duplicates/api_impact checks
  (retained in the backlog, never deleted); the rule re-activates when the new dashboard lands.
- **One working tree per session (IS-PF-0036):** never run two concurrent sessions in the **same**
  folder — git `HEAD`/branch state is global to the working directory, so one session's checkout/commit
  races the other's and a commit can land on `develop` directly. Give each session its **own clone or
  `git worktree`**. This is how a worker session must be run (see `docs/WORKER-SCHEDULER-OPERATIONS.md`).
- **Sync `develop` often, per worker (BI-PF-1290 / BI-PF-1318):** git state is per working directory, so sync is
  **per session** — there is no background job that could cover all sessions. Fold the integration branch in
  frequently so merges stay small: run `python scripts/dev/sync_develop.py` when you **start** a task
  (**merge** `origin/develop` into your branch — **never** rebase/reset); the **pre-commit and pre-push hooks**
  run it automatically. The derived backlog files (history / indexes / counters + the generated docs)
  auto-resolve via the `merge=pf-derived` driver; a **source** conflict aborts cleanly and is resolved by hand.

## Review & communication standard (binding)

Applies to EVERY review, Gate (**Gate 1** = approve the plan before coding; **Gate 2** = approve delivery),
360-degree reconciliation, and status report.

1. **Explain in context.** On FIRST mention of any term, code, or abbreviation (e.g., item codes like `A2`;
   feature groups `G1`–`G10`; `AC` = acceptance criterion; `FEATURE_PR`; `REL-0`; `HMAC`; `Ed25519`;
   "locked baseline"; "fail-closed"), give its plain-language meaning in the same sentence. No bare codes;
   keep a short glossary when several appear.
2. **Decision-ready.** Every approval must plainly say whether it is OK to approve or needs attention:
   **Why** · **What changes** · **How** · detailed **Acceptance criteria** (what proves each) · **Scope** ·
   360-degree reconciliation · **Impact review + risks split into MITIGATED vs OPEN (needs explicit operator
   sign-off)** · technical details (files/tests) · a **Recommendation** banner (APPROVE / APPROVE WITH
   ATTENTION / NEEDS REVIEW) · the exact decisions requested.
3. **Language-rule assessment at take-up.** During backlog review / Gate 1 (BEFORE implementing), run
   `python scripts/dev/language_rule_review.py <item>` and cite the verdict: new logic in **Go** vs **edits**
   to existing shipped Python (allowed) vs **new shipped Python needing an allowlist entry** (needs approval).
   This is the SAME policy precheck enforces (`scripts/dev/language_rule_check.py`, fast band) — decide it once,
   up front, so it is not re-asked during implementation.

## Reconciliation before implementation (binding — any change)
Before designing or implementing **anything**, produce a **RECONCILIATION** block and keep it with the work
item / review. It reconciles the change against what has **already been decided** and what **already exists**:

```
PRIOR DECISIONS — every recorded decision this change touches (quote + id/source).
EXISTING PATH   — per capability: does it already exist? owner + file:line.
ASSUMPTIONS     — every assumption NOT backed by a recorded decision or by the code.
DIVERGENCES     — anywhere this would differ from a prior decision or an existing owner.
OPEN QUESTIONS  — what the user must confirm.
```

Rules:
1. **No assumption is implemented unconfirmed** — every `ASSUMPTIONS` row needs an explicit user yes/no first.
2. **No silent divergence** — re-scoping / re-deciding **amends the decision record first**; never reconverge
   silently later.
3. **Decisions are an append-only ledger cited by implementations** — an item carries `decisions[]`; a change
   that contradicts a ledger entry **stops**.
4. **Unknowns are investigated, never extrapolated** — if `PRIOR DECISIONS` / `EXISTING PATH` are not known,
   grep/read the code (file:line) before proposing.
5. **Do not build scope-/context-agnostically** unless the user has explicitly signed off for each scope.

This sits **before** the pre-implementation review below; `DIVERGENCES` are adjudicated in its IMPACT REVIEW.

## Pre-implementation architecture review (mandatory)
Before implementing **any** new design, flow, review recommendation, or external document:
1. Restate the proposed change in one line.
2. Check it against the governing plan
   (`docs/PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md`), the canonical
   owners (`config/store-registry.json`), the authoritative API surface (`api/`), and the fixed decisions
   (one writer per concern; no duplicate engines/stores; legacy dashboard frozen; OpenCode is an adapter, not a
   dependency; the two independent entry paths).
3. Produce an **IMPACT REVIEW** table:
   `claim | verdict (aligned | violates | new-path | derails | stale) | evidence (file:line) | recommendation`.
4. If **any** verdict is not `aligned`: **STOP** — highlight the conflict to the user and ask **yes/no** before
   writing code.
5. After approval, **record the accepted work as backlog item(s) BEFORE coding** (`origin=review`,
   `source`, a `source_ref`, and artifact/test descriptors in `links.backend_capability`). Work lives in the
   backlog, never only in a doc. Idempotent by `external_id` so re-ingesting a doc does not duplicate.
6. Implement, then **link the real artifacts/tests on the item** and verify against the same authority; report.
Never implement an un-audited external prescription. A **new path** always requires explicit user approval.

Tooling that supports this rule:
- `python scripts/dev/design_review_check.py <doc.md>` — extracts claims, searches the code/architecture, prints
  the IMPACT REVIEW table and the claims needing a decision.
- `python scripts/dev/design_review_check.py <doc.md> --record --accept 1,2,3` — records ACCEPTED claims as
  review-origin backlog items with artifact/test descriptors.
- `python scripts/dev/intent_trace_check.py` (in precheck, advisory) — verifies those recorded descriptors still
  resolve (catches "intended but not actually implemented" / since-removed drift).

## Definition of Done & merge policy (binding)
Applies to **every backlog item in any scope** — Product Forge itself (`product_forge`, integration branch
`develop`) **and the products Product Forge generates** (`project` scope, each with its own repo → its own
integration branch). The engineering flow is identical for generated products; only the repo/scope differs
(`core.backlog`, `core.task_contract`, `core.worker`, `core.github` all take `scope`+`project`).
For every item, before merge:
1. Work on a **feature branch** off that repo's integration branch (`develop`) — never commit to `develop`/`main` directly.
2. **Code review** the diff (self/agent review; findings fixed).
3. **Lint/static** — `python scripts/dev/lint_check.py` clean (ruff, scoped to changed files). It is **advisory**
   today because the legacy tree predates lint; it flips to `--strict` (fatal) once the changed-file debt is
   cleared, and is part of `precheck` either way.
4. **Gates + e2e** — `python scripts/dev/precheck.py` **PASS** (fast default; `--full` at merge/CI; `--release`
   for the periodic full-tree secret sweep — the per-merge secret scan is diff-scoped, BI-PF-0385) (compile,
   wired-audit, api-contract/governance,
   engineering-flow/task-contract/scheduler/vcs-worktree/worker/github/intent-trace, backlog-e2e, docs-fresh,
   secret-scan, pipeline tests).
5. **Link evidence** on the backlog item (artifact/test descriptors) so `intent_trace_check` verifies it.
6. **Merge to `develop`** with a controlled merge **immediately** after green — do not leave completed work
   stranded on a side branch.
7. **Record delivery provenance** on the item (`core.backlog.set_delivery`): `branch`, `merge_sha`, optional
   `commits`, `pr` (#) and `pr_url`. The traceability loop is **not** closed until the item shows how it was
   delivered (branch → merge → PR).

ENG-6 (Common Validation Engine) + ENG-7 (FEATURE_PR) will automate steps 2–4 as the FEATURE_PR profile.

## Safety (state)
- **Never recursively delete shared state.** Tests and scripts may only delete their own
  uniquely-named scratch path (`products/_test_<name>/`); deleting `product-forge/`,
  `products/<p>/backlog/`, `products/.conversations/`, `products/ledger/` or `products/inbox/`
  is forbidden. Enforced by `wired_audit.destructive_audit()` (fatal).
