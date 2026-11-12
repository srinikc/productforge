# BI-PF-1534 operator recovery

If BACKLOG_DB_SCOPE_UNLISTED occurs:
1. Confirm scope is not required for DB authority.
2. For required scope: backfill + parity, then add to PF_BACKLOG_DB_SCOPES.
3. For legacy file scope: set PF_BACKLOG_DB=off explicitly.
4. Never bypass by reverting to silent file fallback.

Test: python -m pytest test-framework/tests/pipeline/test_backlog_db_cutover.py -q
