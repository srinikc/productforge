SET lock_timeout = '5s';
SET statement_timeout = '60s';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_traceability_tenant_item ON traceability (tenant_id, item_id);
