# bi-pf-1534 operator recovery

if backlog_db_scope_unlisted occurs:

1. confirm the scope is not required for db authority.
2. for a required scope: backfill, run parity, then add to pf_backlog_db_scopes.
3. for a legacy file scope: set pf_backlog_db=off explicitly.
4. never bypass by reverting to silent file fallback.

path-specific recovery:

- read: fix allowlist or set off before reads.
- write: fix allowlist or set off before writes; do not retry into files.
- delete: fix allowlist or set off; run export/reconcile before deletion.
- id: fix allowlist or set off; do not fall back to git/local ids.

test: python -m pytest test-framework/tests/pipeline/test_backlog_db_cutover.py -q

Metric: backlog_db_scope_unlisted_total via PF_BACKLOG_METRICS_FILE; alert ProductForgeBacklogScopeUnlisted.
