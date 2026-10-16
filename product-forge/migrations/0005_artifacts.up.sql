-- EDP-15 (BI-PF-1307) sub-slice C1a: artifact metadata + content-addressed stored objects, tenant-scoped
-- with RLS (same pattern as 0003). Bytes live in the object store; this DB holds metadata + integrity.
--
-- Decisions (architect): identity = stable logical artifacts.id + content-addressed stored_objects.checksum
-- (sha256); versioning = immutable/append-only (monotonic `version`); signed-URL-vs-streaming is decided by
-- the object-store Capabilities (EDP-13/14). Retention/expiry is EDP-16.

CREATE TABLE stored_objects (
    tenant_id    TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    checksum     TEXT NOT NULL,                         -- sha256 (content-addressed, per tenant)
    size         BIGINT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, checksum)
);

CREATE TABLE artifacts (
    id           TEXT PRIMARY KEY,                      -- stable logical id (tenant-scoped)
    tenant_id    TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id   TEXT REFERENCES projects(id) ON DELETE SET NULL,
    run_id       TEXT REFERENCES runs(id) ON DELETE SET NULL,
    name         TEXT NOT NULL DEFAULT '',
    version      BIGINT NOT NULL DEFAULT 0,             -- monotonic per (tenant, name); immutable versions
    checksum     TEXT NOT NULL,                         -- FK to stored_objects(tenant_id, checksum)
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size         BIGINT NOT NULL,
    deleted_at   TIMESTAMPTZ,                           -- soft delete (tombstone)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, checksum) REFERENCES stored_objects(tenant_id, checksum)
);

CREATE INDEX idx_artifacts_tenant ON artifacts (tenant_id);
CREATE INDEX idx_artifacts_project ON artifacts (project_id);
CREATE INDEX idx_artifacts_run ON artifacts (run_id);
CREATE UNIQUE INDEX uq_artifacts_name_version ON artifacts (tenant_id, name, version);

ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON artifacts
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE stored_objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE stored_objects FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON stored_objects
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
