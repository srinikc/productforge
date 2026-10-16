-- EDP-19 (BI-PF-1311): grant sequence privileges to the runtime role.
-- 0004 granted DML on tables but not USAGE on sequences, so BIGSERIAL inserts (audit, ledger, derived_outputs,
-- allocations) failed for pf_app/pf_runtime. Grant now + for future sequences.

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pf_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO pf_runtime;
