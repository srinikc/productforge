-- EDP Slice C (BI-PF-1408): the remaining planned domain tables from the store mapping.
-- Tenant-scoped tables carry RLS (same pattern as 0003); append-only tables (audit, ledger) get a trigger
-- that denies UPDATE/DELETE. Port-backed tables reconcile to the datastore interfaces:
--   jobs -> JobStore.Job, audit -> AuditStore.AuditEvent, memory -> MemoryRepository.MemoryEntry,
--   secrets -> SecretStore (metadata only; the value lives in a secret manager).

-- jobs (datastore.JobStore.Job)
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    priority        INTEGER NOT NULL DEFAULT 0,
    attempt         INTEGER NOT NULL DEFAULT 0,
    lease_id        TEXT NOT NULL DEFAULT '',
    expires_at      TIMESTAMPTZ,
    idempotency_key TEXT NOT NULL DEFAULT '',
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_claim ON jobs (status, priority DESC, created_at);
CREATE UNIQUE INDEX uq_jobs_idem ON jobs (tenant_id, idempotency_key) WHERE idempotency_key <> '';

-- audit (datastore.AuditStore.AuditEvent) - append-only
CREATE TABLE audit (
    id             BIGSERIAL PRIMARY KEY,
    tenant_id      TEXT NOT NULL,
    actor          TEXT NOT NULL DEFAULT '',
    action         TEXT NOT NULL,
    resource       TEXT NOT NULL DEFAULT '',
    outcome        TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_tenant_at ON audit (tenant_id, at DESC);

-- memory (datastore.MemoryRepository.MemoryEntry)
CREATE TABLE memory (
    id         TEXT PRIMARY KEY,
    tenant_id  TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    kind       TEXT NOT NULL DEFAULT '',
    object_ref TEXT NOT NULL DEFAULT '',
    acl_scope  TEXT NOT NULL DEFAULT '',
    payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_memory_tenant ON memory (tenant_id);
CREATE INDEX idx_memory_kind ON memory (tenant_id, kind);

-- secrets (datastore.SecretStore): metadata only; never the secret value
CREATE TABLE secrets (
    ref        TEXT PRIMARY KEY,
    tenant_id  TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- backlog_items (BI-PF-1399 owns the full backlog SoR; minimal here, extended there)
CREATE TABLE backlog_items (
    id         TEXT PRIMARY KEY,
    tenant_id  TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'feature',
    status     TEXT NOT NULL DEFAULT 'new',
    title      TEXT NOT NULL DEFAULT '',
    body       TEXT NOT NULL DEFAULT '',
    data       JSONB NOT NULL DEFAULT '{}'::jsonb,
    revision   BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_backlog_items_tenant_status ON backlog_items (tenant_id, status);

-- ledger - append-only
CREATE TABLE ledger (
    id        BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    kind      TEXT NOT NULL DEFAULT '',
    entry     JSONB NOT NULL DEFAULT '{}'::jsonb,
    at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ledger_tenant_at ON ledger (tenant_id, at DESC);

-- generic tenant-scoped registries / state (minimal shape; refined per consumer)
CREATE TABLE products (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE providers (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kind TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE registries (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kind TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE traceability (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, item_id TEXT NOT NULL DEFAULT '',
    ref        TEXT NOT NULL DEFAULT '', data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE problems (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE insights (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE decomposition (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, source_id TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE control_state (
    tenant_id  TEXT NOT NULL, key TEXT NOT NULL, value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (tenant_id, key));
CREATE TABLE state (
    tenant_id  TEXT NOT NULL, key TEXT NOT NULL, value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (tenant_id, key));
CREATE TABLE tool_settings (
    tenant_id  TEXT NOT NULL, key TEXT NOT NULL, value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (tenant_id, key));
CREATE TABLE data (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kind TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE allocations (
    id         TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, session TEXT NOT NULL DEFAULT '',
    block      JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now());

-- RLS for every tenant-scoped table (audit/ledger included).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['jobs','audit','memory','secrets','backlog_items','ledger','products','providers',
                           'registries','traceability','problems','insights','decomposition','control_state',
                           'state','tool_settings','data','allocations']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
    EXECUTE format('CREATE POLICY tenant_isolation ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))', t);
  END LOOP;
END $$;

-- Append-only enforcement (audit, ledger): deny UPDATE/DELETE.
CREATE OR REPLACE FUNCTION deny_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit
    FOR EACH ROW EXECUTE FUNCTION deny_mutation();
CREATE TRIGGER ledger_append_only BEFORE UPDATE OR DELETE ON ledger
    FOR EACH ROW EXECUTE FUNCTION deny_mutation();
