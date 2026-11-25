# Baseline Gate Remediation Design - BI-PF-1611

## RECONCILIATION

### PRIOR DECISIONS
- One backlog item per branch; baseline repairs must not be mixed into BI-PF-1567.
- Rejected items are terminal and must not be reopened merely to satisfy design/spec gates.
- Gate checks are diff-scoped and must remain fail-closed for new and in-progress work.

### EXISTING PATH
- `scripts/dev/design_pack.py:42` and `:44` decide enforcement by status.
- `scripts/dev/functional_spec.py:50` and `:52` decide enforcement by status.
- `scripts/dev/spec_pack.py:37` and `:39` decide enforcement by status.
- `scripts/dev/conformance_check.py:24` delegates to functional-spec enforcement.
- Precheck calls these gates with `--changed`, `--all`, and `--check`.

### ASSUMPTIONS
- The rejected status is terminal and will not be used for work that should still be reviewed.
- The three tooling scripts are the only enforcement entry points for these gates.
- No production runtime behavior changes.

### DIVERGENCES
- Rejected items will be skipped by design/spec/conformance gates; they remain in the backlog and audit history.
- Completed and in-progress items continue to be enforced exactly as before.

### OPEN QUESTIONS
- None. Scope is limited to terminal rejected-status handling.

## Design

### Runtime contract

| Field | Value |
|---|---|
| Trigger | precheck design-pack/functional-spec/spec-pack/conformance gates |
| Entrypoint | `scripts/dev/design_pack.py:should_enforce`, `functional_spec.py:should_enforce`, `spec_pack.py:should_enforce` |
| Call sites | precheck fast tier; explicit script invocations |
| Adapter | filesystem backlog item JSON plus backlog API reads |
| Contract | rejected status returns not-enforced; new/draft/triaged and all other statuses keep existing behavior |
| Failure behavior | fail closed for non-rejected items; never silently skip unknown states |
| Observable result | gate output names checked item count; regression test fails on behavior drift |

### Change

Add one shared predicate in `scripts/dev/gate_status.py:should_skip` and call it from design-pack, functional-spec, and spec-pack enforcement. Conformance inherits the functional-spec decision.

### Tests

- `test-framework/tests/test_gates_skip_rejected.py:test_rejected_status_skips_design_and_spec_gates`
- `test-framework/tests/test_gates_skip_rejected.py:test_live_statuses_still_enforced`
- `test-framework/tests/test_gates_skip_rejected.py:test_unknown_status_still_enforced`

### Controls

| ID | Kind | Control | Test |
|---|---|---|---|
| C-1 | failure | rejected skipped by design-pack | `test_rejected_status_skips_design_and_spec_gates` |
| C-2 | config | rejected skipped by functional/spec pack | same |
| C-3 | security | non-rejected and unknown statuses stay enforced | `test_live_statuses_still_enforced`, `test_unknown_status_still_enforced` |
| C-4 | observability | gate output reports checked count | precheck output |

### Rollback

Revert the three tooling edits and the regression test. No data or schema migration.

### Risks

- Over-broad skip: mitigated by testing live and unknown statuses.
- Inconsistent gates: mitigated by applying the same predicate to design, functional, and spec pack.
- Hidden rejected work: rejected items remain visible in the backlog with history and reason.


## Guardrail checklist

- Reversibility: revert the shared predicate and three imports; no data change.
- Availability: read-only predicate; no single point of failure introduced.
- Authorization: no auth boundary touched; unknown statuses fail closed.
- Blast radius: only terminal rejected/cancelled/won-t-do/wont-do statuses skip.
- Invariants: live and unknown statuses remain enforced.
- Tests/rollback: pytest covers terminal, live, and unknown states; revert restores enforcement.
- Language rule: Python tooling only.
- API: no API change.
- Data/tenant: no tenant data access or store change.
- Reuse/observability: one shared predicate, not three copies; gate output reports checked counts.
