CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_traceability_tenant_item ON traceability (tenant_id, item_id);
