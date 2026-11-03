-- O(1) reservation counter for the admin backlog-authority readiness endpoint.
-- The counter is maintained by DB triggers, including out-of-band INSERT/DELETE/UPDATE/TRUNCATE.
SET LOCAL lock_timeout = '5s';

ALTER TABLE backlog_id_allocations
    ADD COLUMN IF NOT EXISTS reservation_count BIGINT NOT NULL DEFAULT 0;

UPDATE backlog_id_allocations
SET reservation_count = (SELECT count(*) FROM backlog_id_reservations)
WHERE authority = 'global';

-- Count(*) for a tenant can use a narrow index-only scan.
CREATE INDEX IF NOT EXISTS idx_backlog_items_tenant_count
    ON backlog_items (tenant_id) INCLUDE (id);

CREATE OR REPLACE FUNCTION backlog_reservation_counter() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE backlog_id_allocations
        SET reservation_count = reservation_count + 1
        WHERE authority = 'global';
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE backlog_id_allocations
        SET reservation_count = GREATEST(reservation_count - 1, 0)
        WHERE authority = 'global';
        RETURN OLD;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS backlog_reservation_counter_row ON backlog_id_reservations;
CREATE TRIGGER backlog_reservation_counter_row
    AFTER INSERT OR UPDATE OR DELETE ON backlog_id_reservations
    FOR EACH ROW EXECUTE FUNCTION backlog_reservation_counter();

CREATE OR REPLACE FUNCTION backlog_reservation_counter_truncate() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE backlog_id_allocations
    SET reservation_count = 0
    WHERE authority = 'global';
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS backlog_reservation_counter_truncate ON backlog_id_reservations;
CREATE TRIGGER backlog_reservation_counter_truncate
    AFTER TRUNCATE ON backlog_id_reservations
    FOR EACH STATEMENT EXECUTE FUNCTION backlog_reservation_counter_truncate();
