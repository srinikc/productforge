BEGIN;
SET lock_timeout = '5s';
SET statement_timeout = '60s';
DROP INDEX IF EXISTS idx_traceability_tenant_item;
COMMIT;
