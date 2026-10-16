-- Rollback EDP Slice C domain tables (BI-PF-1408).

DROP TRIGGER IF EXISTS ledger_append_only ON ledger;
DROP TRIGGER IF EXISTS audit_append_only ON audit;
DROP FUNCTION IF EXISTS deny_mutation();

DROP TABLE IF EXISTS allocations;
DROP TABLE IF EXISTS data;
DROP TABLE IF EXISTS tool_settings;
DROP TABLE IF EXISTS state;
DROP TABLE IF EXISTS control_state;
DROP TABLE IF EXISTS decomposition;
DROP TABLE IF EXISTS insights;
DROP TABLE IF EXISTS problems;
DROP TABLE IF EXISTS traceability;
DROP TABLE IF EXISTS registries;
DROP TABLE IF EXISTS providers;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS ledger;
DROP TABLE IF EXISTS backlog_items;
DROP TABLE IF EXISTS secrets;
DROP TABLE IF EXISTS memory;
DROP TABLE IF EXISTS audit;
DROP TABLE IF EXISTS jobs;
