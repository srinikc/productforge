# Fix Impact Contract

Every BLOCKER/MAJOR fix must add a `fix_impact` row on the item before it can pass Gate 1/precheck.

Required fields:

- `sig` / `finding` / `severity`
- `origin_class`: IMPLEMENTATION_GAP, DESIGN_GAP, VERIFICATION_GAP, FIX_INDUCED, PRE_EXISTING, FIX_DEFECT
- `reproducer`
- `regression_test`
- `evidence` (existing path)
- `files` (existing paths)
- `rollback` (or explicit no-data impact)
- `artifacts_updated` including affected_files, tests, evidence
- `status: ACTIONED`

Enforced by `scripts/dev/fix_guard.py` in Gate 1 and precheck.

Rules:

1. Reproduce before fixing.
2. Change only declared files.
3. Add a permanent regression test.
4. Update scope, tests, evidence, and conformance in the same batch.
5. Review only the fix delta against frozen functional/design scope.
6. If a fix expands scope, split it into a new item.
