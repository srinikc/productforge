-- 0001 down: remove the EDP database roles. REFUSES to drop a role that still owns/possesses objects.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_admin') THEN
        DROP ROLE pf_admin;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_backup') THEN
        REVOKE pg_read_all_data FROM pf_backup;
        DROP ROLE pf_backup;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_readonly') THEN
        DROP ROLE pf_readonly;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_runtime') THEN
        DROP ROLE pf_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_owner') THEN
        DROP ROLE pf_owner;
    END IF;
END $$;
