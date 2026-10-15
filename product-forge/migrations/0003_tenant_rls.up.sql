-- EDP-09 (BI-PF-1301): tenant isolation via Postgres Row-Level Security.
--
-- A row is visible/writable only when its tenant key equals the transaction-local setting
-- app.tenant_id (set with SET LOCAL / set_config(..., true)). Unset -> no rows (fail closed).
-- FORCE ROW LEVEL SECURITY so the table OWNER is also subject (migrations run as pf_owner; the
-- runtime connects as pf_runtime; pf_admin has BYPASSRLS for admin/ops).
--
-- The identity/authorization table `memberships` is intentionally NOT put under RLS here: the
-- tenant-context service must read it to verify a principal's membership before any tenant
-- context exists (chicken-and-egg). See docs/EDP-17-SCHEMA.md.

ALTER TABLE tenants  ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants  FORCE  ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenants;
CREATE POLICY tenant_isolation ON tenants
    USING (id = current_setting('app.tenant_id', true))
    WITH CHECK (id = current_setting('app.tenant_id', true));

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE  ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON projects;
CREATE POLICY tenant_isolation ON projects
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs FORCE  ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON runs;
CREATE POLICY tenant_isolation ON runs
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage FORCE  ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON usage;
CREATE POLICY tenant_isolation ON usage
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotas FORCE  ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON quotas;
CREATE POLICY tenant_isolation ON quotas
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
