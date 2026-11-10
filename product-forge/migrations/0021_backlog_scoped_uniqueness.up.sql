BEGIN;
SET lock_timeout = '5s';
SET statement_timeout = '60s';
-- 0021: allow legacy duplicate backlog IDs across tenants while preserving global new-ID allocation.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM backlog_items WHERE tenant_id IS NULL) THEN
    RAISE EXCEPTION '0021 blocked: backlog_items rows have NULL tenant_id';
  END IF;
  IF EXISTS (SELECT 1 FROM traceability WHERE tenant_id IS NULL) THEN
    RAISE EXCEPTION '0021 blocked: traceability rows have NULL tenant_id';
  END IF;
  IF EXISTS (SELECT 1 FROM traceability t LEFT JOIN backlog_items b
             ON b.id=t.item_id AND b.tenant_id=t.tenant_id WHERE b.id IS NULL) THEN
    RAISE EXCEPTION '0021 blocked: traceability rows lack a tenant-matched backlog item';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE confrelid='backlog_items'::regclass
             AND contype='f' AND conname <> 'fk_traceability_item') THEN
    RAISE EXCEPTION '0021 blocked: unknown FK references backlog_items';
  END IF;
END $$;
ALTER TABLE traceability DROP CONSTRAINT IF EXISTS fk_traceability_item;
ALTER TABLE backlog_items DROP CONSTRAINT IF EXISTS backlog_items_pkey;
ALTER TABLE backlog_items ADD CONSTRAINT backlog_items_pkey PRIMARY KEY (tenant_id, id);
ALTER TABLE traceability ADD CONSTRAINT fk_traceability_item
  FOREIGN KEY (tenant_id, item_id) REFERENCES backlog_items(tenant_id, id) ON DELETE CASCADE;

COMMIT;
