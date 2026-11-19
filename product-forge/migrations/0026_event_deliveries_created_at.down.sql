-- Destructive: requires verified backup before rollback.
ALTER TABLE event_deliveries DROP COLUMN IF EXISTS created_at;
