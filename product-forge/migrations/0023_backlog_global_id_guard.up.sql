BEGIN;
SET lock_timeout = '5s';
SET statement_timeout = '60s';
-- Legacy duplicates stay marked; new rows default false and are globally unique.
ALTER TABLE backlog_items ADD COLUMN IF NOT EXISTS legacy_duplicate boolean NOT NULL DEFAULT false;
UPDATE backlog_items b SET legacy_duplicate=true
 WHERE EXISTS (SELECT 1 FROM backlog_items x WHERE x.id=b.id AND x.tenant_id<>b.tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_backlog_items_new_global_id
  ON backlog_items(id) WHERE legacy_duplicate=false;
CREATE OR REPLACE FUNCTION backlog_global_id_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.legacy_duplicate THEN RETURN NEW; END IF;
  IF EXISTS (SELECT 1 FROM backlog_items WHERE id=NEW.id AND tenant_id<>NEW.tenant_id AND legacy_duplicate=false) THEN
    RAISE EXCEPTION 'global backlog id already belongs to another tenant: %', NEW.id;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS backlog_global_id_guard ON backlog_items;
CREATE TRIGGER backlog_global_id_guard BEFORE INSERT OR UPDATE OF id,tenant_id ON backlog_items
  FOR EACH ROW EXECUTE FUNCTION backlog_global_id_guard();
COMMIT;
