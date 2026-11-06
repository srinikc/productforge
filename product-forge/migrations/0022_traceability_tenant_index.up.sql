BEGIN;
SET lock_timeout = '5s';
-- Support the composite FK added by 0021 and tenant-scoped traceability lookups.
CREATE INDEX IF NOT EXISTS idx_traceability_tenant_item ON traceability (tenant_id, item_id);
COMMIT;
