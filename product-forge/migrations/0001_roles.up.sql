-- 0001: database role separation (ADR-0006 §5.1; EDP-08 / BI-PF-1300).
-- Roles are created idempotently. Runtime/admin are NOLOGIN by default; credentials are provisioned per
-- environment and never committed. See migrations/README.md.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_owner') THEN
        CREATE ROLE pf_owner NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_runtime') THEN
        CREATE ROLE pf_runtime NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_readonly') THEN
        CREATE ROLE pf_readonly NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_backup') THEN
        CREATE ROLE pf_backup NOLOGIN;
        GRANT pg_read_all_data TO pf_backup;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_admin') THEN
        -- break-glass cross-tenant admin; usage is audited (ADR-0006)
        CREATE ROLE pf_admin NOLOGIN BYPASSRLS;
    END IF;
END $$;
