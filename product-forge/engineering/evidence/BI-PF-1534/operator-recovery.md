# BI-PF-1534 operator recovery

If BACKLOG_DB_SCOPE_UNLISTED occurs:

1. Confirm the scope is not required for DB authority.
2. For a required scope: backfill, run parity, then add to PF_BACKLOG_DB_SCOPES.
3. For a legacy file scope: set PF_BACKLOG_DB=off explicitly.
4. Never bypass by reverting to silent file fallback.

Path-specific recovery:

- read: fix allowlist or set off before reads.
- write: fix allowlist or set off before writes; do not retry into files.
- delete: fix allowlist or set off; run export/reconcile before deletion.
- ID: fix allowlist or set off; do not fall back to Git/local IDs.

Test: python -m pytest test-framework/tests/pipeline/test_backlog_db_cutover.py -q
