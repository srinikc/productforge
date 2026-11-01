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
| BLOCKER in scope | Must fix before Gate 2 |
| MAJOR in scope | Fix, or explicit HIL scope decision |
| MINOR/NIT in scope | Disposition; do not force a code rewrite |
| OUT_OF_SCOPE / pre-existing | Backlog follow-up; do not expand the item |
| False positive / stale | Close with code/test/evidence reference |
| Design/evidence gap | Add evidence, not a code rewrite |

## Stop rule

- Freeze the exact candidate SHA before review.
- One Gate 2.5 review per exact SHA.
- No code changes while the review is running.
- After review, one remediation pass maximum.
- Any new major after the freeze requires HIL approval for another pass.
- No evidence deletion.
- Repeated findings trigger RCCA, not another review.

## Delta re-review

- The first Gate 2.5 review is the full item candidate.
- Every later review is delta-only: --rereview --since <prior-reviewed-head>.
- The delta must contain only finding fixes, tests, controls, and evidence.
- fix_evidence is mandatory: finding_sig, origin_class, regression_test, controls_rerun, result, evidence.
- No fix evidence means no re-review.
- One delta re-review maximum; a new blocker requires HIL approval.
