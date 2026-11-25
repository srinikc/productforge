-- EDP-09 (BI-PF-1407): a non-superuser runtime role so row-level security actually enforces.
--
-- pf_owner is SUPERUSER and bypasses RLS even under FORCE ROW LEVEL SECURITY. pf_app is a LOGIN role that
-- inherits pf_runtime (NOSUPERUSER NOBYPASSRLS), so the RLS policies from 0003 apply to it. Grants give it
-- DML on the system-of-record tables; default privileges extend that to tables created later (EDP-15+).
--
-- No password is set here (secrets are never committed): the local/dev bootstrap sets it out-of-band.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_app') THEN
        CREATE ROLE pf_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE INHERIT;
    END IF;
END $$;
GRANT pf_runtime TO pf_app;

GRANT USAGE ON SCHEMA public TO pf_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pf_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pf_runtime;
