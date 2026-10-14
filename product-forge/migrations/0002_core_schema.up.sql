-- 0002: EDP-17 canonical core schema (PostgreSQL system of record, ADR-0006).
-- Core tables owned by EDP-17. Domain tables owned by later items attach by FK:
--   artifacts(EDP-15), audit(EDP-20), jobs/outbox(EDP-19), memory(EDP-21), events(EDP-19/eventing),
--   backlog(EDP-18). Every mutable row carries a monotonic `version` (optimistic concurrency) and
--   created_at/updated_at; RLS policies are added by EDP-09 on these tenant-scoped tables.

CREATE TABLE tenants (
    id          TEXT PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    region      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'active',
    version     BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    principal   TEXT NOT NULL,
    role        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    version     BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, principal)
);
CREATE INDEX idx_memberships_tenant ON memberships (tenant_id);

CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    version     BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, slug)
);
CREATE INDEX idx_projects_tenant ON projects (tenant_id);

CREATE TABLE runs (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'queued',
    spec        JSONB NOT NULL DEFAULT '{}'::jsonb,
    version     BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX idx_runs_tenant_status ON runs (tenant_id, status);
CREATE INDEX idx_runs_project ON runs (project_id);

CREATE TABLE stages (
    id          TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    ordinal     INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending',
    version     BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_stages_run ON stages (run_id, ordinal);

CREATE TABLE attempts (
    id          TEXT PRIMARY KEY,
    stage_id    TEXT NOT NULL REFERENCES stages(id) ON DELETE CASCADE,
    attempt     INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'running',
    error       TEXT NOT NULL DEFAULT '',
    version     BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_attempts_stage ON attempts (stage_id, attempt);

CREATE TABLE usage (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id   TEXT,
    metric       TEXT NOT NULL,
    quantity     NUMERIC NOT NULL DEFAULT 0,
    period_start TIMESTAMPTZ NOT NULL,
    period_end   TIMESTAMPTZ NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, metric, period_start)
);
CREATE INDEX idx_usage_tenant_metric ON usage (tenant_id, metric, period_start);

CREATE TABLE quotas (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    metric      TEXT NOT NULL,
    limit_value NUMERIC NOT NULL DEFAULT 0,
    hard        BOOLEAN NOT NULL DEFAULT false,
    version     BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, metric)
);
