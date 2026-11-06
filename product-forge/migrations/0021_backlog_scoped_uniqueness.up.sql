SET lock_timeout = '5s';
-- 0021: allow legacy duplicate backlog IDs across tenants while preserving global new-ID allocation.
ALTER TABLE traceability DROP CONSTRAINT IF EXISTS fk_traceability_item;
ALTER TABLE backlog_items DROP CONSTRAINT IF EXISTS backlog_items_pkey;
ALTER TABLE backlog_items ADD CONSTRAINT backlog_items_pkey PRIMARY KEY (tenant_id, id);
ALTER TABLE traceability ADD CONSTRAINT fk_traceability_item
  FOREIGN KEY (tenant_id, item_id) REFERENCES backlog_items(tenant_id, id) ON DELETE CASCADE;
