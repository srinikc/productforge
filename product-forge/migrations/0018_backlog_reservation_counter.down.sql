SET LOCAL lock_timeout = '5s';

DROP TRIGGER IF EXISTS backlog_reservation_counter_truncate ON backlog_id_reservations;
DROP FUNCTION IF EXISTS backlog_reservation_counter_truncate();
DROP TRIGGER IF EXISTS backlog_reservation_counter_row ON backlog_id_reservations;
DROP FUNCTION IF EXISTS backlog_reservation_counter();
DROP INDEX IF EXISTS idx_backlog_items_tenant_count;
ALTER TABLE backlog_id_allocations DROP COLUMN IF EXISTS reservation_count;
