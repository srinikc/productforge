# Review Triage Policy

Applies to Gate 1.5 and Gate 2.5 findings for every item.

## Scope

The reviewer must review only:

- the item's acceptance criteria,
- the approved design contract,
- the declared `review_scope.files` / components,
- runtime and evidence paths named in the design.

Out-of-scope, pre-existing, or unrelated refactor suggestions are `SCOPE`, not blockers.

## Finding categories

| Finding | Action |
|---|---|
| BLOCKER in scope | Must fix |
| MAJOR in scope | Must fix |
| MINOR in scope | Must fix |
| NIT in scope | Fix, or record an evidence-backed exception |
| OUT_OF_SCOPE / pre-existing | Must be fixed or invalidated with evidence; `SCOPE` is not a disposition for B/M/m |
| False positive / stale | Invalidate with code/test/evidence reference |
| Design/evidence gap | Update the design/evidence, not the code |

`ACCEPTED`, `DEFERRED`, `SCOPE`, and `REJECTED` are not valid dispositions for
BLOCKER/MAJOR/MINOR. Those severities are closed only by `ACTIONED`/`FIXED` or a
proven-invalid finding.

## Stop rule

- Freeze the exact candidate SHA before the full review.
- One full Gate 1.5 design review and one full Gate 2.5 diff review per item/mode.
- No code changes while a review is running.
- Fix all BLOCKER/MAJOR/MINOR findings in one batched remediation pass.
- Delta fix reviews do not consume the full-review budget.
- A full re-review is allowed only for a HIL-approved material change.
- No evidence deletion.
- Repeated findings trigger RCCA, not another full review.

## Delta re-review

- The first Gate 2.5 review is the full item candidate.
- Every later Gate 2.5 review is delta-only: `--rereview --since <prior-reviewed-head>`.
- The delta must contain only finding fixes, tests, controls, and evidence.
- `fix_evidence` is mandatory: finding_sig, origin_class, regression_test, controls_rerun, result, evidence.
- No fix evidence means no re-review.
- Delta reviews continue only for remaining BLOCKER/MAJOR/MINOR findings and do not reset the full-review budget.
- `architect_review_check` accepts a full review plus its delta chain when the delta ends at the current head.
