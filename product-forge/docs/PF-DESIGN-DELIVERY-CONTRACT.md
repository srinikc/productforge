# PF Design & Delivery Contract

**Status:** mandatory for items created on/after the date in `config/design-contract.json`.
**Purpose:** replace capability narratives with executable implementation contracts.

## 1. Design contract

Every item design pack must contain:

- `standards`: explicitly cite `AGENTS.md`, `docs/ENGINEERING_OPERATING_STANDARD.md` (EOS),
  `docs/REVIEW-GATES-LIFECYCLE.md`, and `docs/DESIGN-QUALITY-RCCA.md`.
- `brief`: problem, what it adds, why, and who feels it.
- `code_guidelines`: the language/database/API/test guidelines selected from `config/coding-guidelines.json` for every affected file type.
- `requirements`: the acceptance criteria.
- `coverage`: one row per AC:
  - AC id
  - runtime entrypoint
  - exact call site/file/function
  - production adapter
  - contract and failure behavior
  - failing end-to-end test
  - evidence path
- `runtime_contract`: trigger, entrypoint, call-site chain, adapter, contract, failure behavior, observable result.
- `proof_plan`: failing test, red evidence, green evidence.
- `scope` and `non_goals`: explicit; one runtime capability per item.
- `failure_matrix`: auth, tenant/RLS, missing schema/row, timeout, concurrency, limits, exhaustion.
- `test_matrix`: real entrypoint/runtime tests, not helper/fake-only proof.
- `observability`: metrics/logs/alerts that the code emits.
- `rollout`/`rollback`: migration order and recovery.
- `review.impact_review`: claim/verdict/evidence/recommendation rows.
- `risks`: risk plus mitigation.
- `stop_conditions`: unresolved blockers stop the item.

No placeholders (`TBD`, `none`, `candidate`, `unspecified`, `not specified`) are allowed in mandatory fields.

## 2. Evidence rules

- Red proof is written first: the test must fail against the real entrypoint before implementation.
- Green proof must exercise the real mux/process/adapter/DB; fakes and dry-runs are not closure evidence.
- `ACTIONED` requires a code, test, doc, or evidence reference. No evidence means `PENDING`.
- Reviews are append-only in the item `review_ledger`; files are not the counter.
- One design and one diff review per item. Additional reviews require an explicit HIL `MATERIAL_CHANGE`.
- Deleting evidence is forbidden and is not a reset.

## 3. Scope rules

- One runtime capability per item. Split broader work before Gate 1.
- Allowlists come from the item’s `affected_files`, not a ticket-specific CI constant.
- Full-candidate review is required before Gate 2. Delta review is only for fixes.
- The first unresolved blocker stops the item; do not patch around missing wiring.

## 4. Ownership rules

- Every changed file must have an owner in `config/ownership.json`.
- Every runtime route/namespace must resolve to one owner.
- A design that cannot state where it is called is not approvable.

## 5. Enforcement

- `scripts/dev/design_contract_check.py` — design completeness, coverage, placeholders, file/test/evidence existence.
- `scripts/dev/ownership_check.py` — file/route ownership.
- `scripts/dev/review_ledger.py` — append-only review ledger and budget.
- `scripts/dev/pf_process_check.py` — validates the framework itself.
- Gate 0 / 1.5 / 1 / 2.5 / 2 and precheck call these checks.
- Root CI workflow runs the framework checks and tests.

## 6. Corrections

Every HIL correction is recorded in `config/correction-ledger.json` as a rule plus an enforcement point. Corrections are injected into task context; recurring corrections must become checks, not prose.

## 7. Executable controls

Every required design dimension must map to a control in design_pack.controls:

- id, dimension, applies_to, check, evidence, failure_behavior, owner.
- `control_runner.py` executes controls and appends current-SHA evidence.
- `control_gate.py` fails missing/failed/stale controls.
- Gate 1 requires control-matrix completeness; Gate 2 requires current-SHA PASS evidence.
- A fix requires `fix_evidence` with finding ID, origin class, regression test, controls rerun, and PASS.
