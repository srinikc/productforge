SET LOCAL lock_timeout = '5s';

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
