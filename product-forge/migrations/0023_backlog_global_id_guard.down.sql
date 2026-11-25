BEGIN;
SET lock_timeout = '5s';
SET statement_timeout = '60s';
DROP TRIGGER IF EXISTS backlog_global_id_guard ON backlog_items;
DROP FUNCTION IF EXISTS backlog_global_id_guard();
DROP INDEX IF EXISTS uq_backlog_items_new_global_id;
ALTER TABLE backlog_items DROP COLUMN IF EXISTS legacy_duplicate;
COMMIT;
