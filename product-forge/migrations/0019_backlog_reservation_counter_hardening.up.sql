-- Surface counter drift without blocking legitimate reservation deletion.
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
        SET reservation_count = reservation_count - 1
        WHERE authority = 'global' AND reservation_count > 0;
        IF NOT FOUND THEN
            RAISE WARNING 'backlog reservation counter drift: delete with zero counter; clamping to zero';
            UPDATE backlog_id_allocations
            SET reservation_count = 0
            WHERE authority = 'global';
        END IF;
        RETURN OLD;
    END IF;
    RETURN NEW;
END $$;
