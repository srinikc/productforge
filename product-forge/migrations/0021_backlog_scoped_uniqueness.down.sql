DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM backlog_items GROUP BY id HAVING count(*) > 1) THEN
    RAISE EXCEPTION 'cannot restore global backlog id primary key while legacy cross-tenant duplicates exist';
  END IF;
END $$;
ALTER TABLE traceability DROP CONSTRAINT IF EXISTS fk_traceability_item;
ALTER TABLE backlog_items DROP CONSTRAINT IF EXISTS backlog_items_pkey;
ALTER TABLE backlog_items ADD CONSTRAINT backlog_items_pkey PRIMARY KEY (id);
ALTER TABLE traceability ADD CONSTRAINT fk_traceability_item
  FOREIGN KEY (item_id) REFERENCES backlog_items(id) ON DELETE CASCADE;
