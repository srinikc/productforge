# Senior Enterprise Architect & Staff Principal Engineer Operating Standard

Every agent, subagent, and pair-programming session in this repository must operate under these **19 Mandatory Senior Enterprise Architect Guidelines**. These rules are binding, non-negotiable, and must be followed rigorously for every backlog item.

---

## The 19 Mandatory Operating Guidelines

### 1. Guiding Principle: Think → Design → 360° Check → Backlog (API-Only)
- **Sequence:** Think through implications → Design solution → 360° systems check across stores, schemas, and language boundaries.
- **Epic Assignment:** Every item must belong to a valid Epic (`BI-PF-####`).
- **Context & Acceptance Criteria:** Item must have complete context, brief, and detailed AC (each >= 40 characters) defining verifiable conditions.
- **Strict API-Only Backlog Operations:** All backlog queries and mutations must use the backlog API (`core.backlog` or HTTP REST) with `$env:PF_EDP_TOKEN` set. **Direct manual edits to backlog JSON files are strictly forbidden.**

### 2. Feature Branch Isolation (Strict 1 Item = 1 Branch)
- **One Item Per Branch:** Work strictly on `feat/<ITEM-ID>-<slug>`. Never combine multiple backlog items into a single feature branch.
- **Separate Tooling / Process Changes:** Tooling, process, or infrastructure changes must be done in a separate branch, separate backlog item, and separate PR.
- **No Shortcuts:** Code must be fully stitched, wired into the runtime path, and exercised. Any runtime drift must be recorded and approved.

### 3. Modular, Scalable & API-First Strategy
- Evaluate upfront if an API is required. Design and implement API endpoints following the canonical schema.
- Verification E2E against AC is mandatory before declaring Definition of Done (DoD).
- Dedicated contract tests must be added and pass (`pytest` / `go test`) before proceeding to merge or push. All code must pass lint and coding standards.

### 4. Framework Agnostic & No Legacy Dashboard References
- Product Forge is framework-agnostic. **Never reference OpenCode** or external runner specifics in production code.
- The existing dashboard is **legacy/frozen**. Do not add dependencies on it or reference it in new capabilities.

### 5. Systemic RCCA (No Band-Aids / No Shortcuts)
- Any defect or friction encountered: Raise issue → Conduct 5-Why Root Cause Corrective Action (RCCA) → Log/update backlog item.
- Extend existing functionality cleanly; if new components are required, design them and obtain approval with complete architectural rationale.

### 6. Plain-Language Review Package Before Implementation
- Summarize functionality in plain language:
  - **Epic # & Backlog #:** Citing parent epic and item ID.
  - **Title:** Clear concise title.
  - **What & Why:** Exactly what changes and why the change is necessary.
  - **Impact-Review Table:** Must include rows for `LANGUAGE CHECK`, `API CHECK`, and `AC CHECK`.
- **Take explicit user approval BEFORE proceeding to implementation.**

### 7. Delivery Lane Integrity
- Delivery must follow the canonical lane (`docs/REVIEW-GATES-LIFECYCLE.md` and `scripts/dev/deliver.py`).
- Merge to `develop` via `--no-ff` and push cleanly with delivery provenance recorded on the backlog item.

### 8–13. Binding Pre-Implementation Reconciliation Ledger
Before designing or implementing **any** change, produce and record the **RECONCILIATION** block:
- **`PRIOR DECISIONS`:** Every prior decision touched (with quote and id/source).
- **`EXISTING PATH`:** Per capability, exact existing file:line citations.
- **`ASSUMPTIONS`:** Unbacked assumptions (**Rule 10: No assumption is implemented unconfirmed**).
- **`DIVERGENCES`:** Any deviation from prior decisions or existing owners (**Rule 11: No divergence is silent**; amend decision record first).
- **`OPEN QUESTIONS`:** Clarifications needed from operator before coding.
- **Rule 12:** Decisions are an append-only ledger cited by implementations.
- **Rule 13:** Unknowns are investigated in code (`file:line`), never extrapolated.

### 14. Explicit Risk & Mitigation Review
- Every review package must explicitly split risks into **Mitigated** vs **Open** risks, detailing concrete mitigation options for each.

### 15. Reuse & Simplicity (Before, During, and After)
- **Before:** Reuse existing module owners first (no duplicate logic or shadow stores). Choose the simplest sufficient solution.
- **During:** Scope strictly to your change. Do NOT drive-by refactor unrelated debt (raise separate backlog items for pre-existing debt).
- **After:** Self-review your diff and ruthlessly delete unneeded additions introduced by your change (dead code, unused imports, duplicate logic, redundant complexity).

### 16. Stay Close to Develop (Sync Often)
- Run `python scripts/dev/sync_develop.py` when starting a task (and `--check` anytime).
- Always merge `origin/develop` into the feature branch (never rebase or reset). Auto-resolve derived backlog files and resolve source conflicts immediately.

### 17. Binding Language Rule
- **New shipped / sensitive core logic** (`core/`, `api/`, `go/`, worker scheduling, encryption) → **Go by default**.
- **Extending existing shipped Python** (edits to existing modules) → **Python OK** (subject to 60-line edit growth threshold in `config/language-rule.json`).
- **Tooling / CI / tests / config / docs** (`scripts/`, `config/`, `docs/`, `test-framework/`) → **Python OK**.

### 18. Provide 1-Line Plain Language Context Before Every Execution
- Before running any shell command, gate, or action, state a clear 1-line plain language context (e.g. *"Designing the system"*, *"Implementing contract tests"*, *"Running precheck quality gates"*, *"Merging feature branch to develop"*). Avoid silent or opaque command bursts.

### 19. Strict Tooling Discipline
1. **Read** the file first.
2. **Edit** the exact block using structured edit tools (or **Write** for new files). Do not blind-overwrite.
3. **Shell** is reserved strictly for running tests, precheck gates, and git operations.
4. Show `git diff --stat` after changes to verify clean, expected diffs.
