-- BI-PF-1268 / ADR-0011: PostgreSQL event authority + transactional outbox.
-- Requires a verified backup/PITR checkpoint before apply. Down is destructive.

CREATE TABLE IF NOT EXISTS events (
    tenant_id     TEXT NOT NULL,
    seq           BIGINT NOT NULL,
    event_id      TEXT NOT NULL,
    occurred_at   TIMESTAMPTZ NOT NULL,
    type          TEXT NOT NULL,
    version       TEXT NOT NULL DEFAULT '1',
    payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_ref   TEXT NOT NULL DEFAULT '',
    payload_sha256 TEXT NOT NULL DEFAULT '',
    size_bytes    BIGINT NOT NULL DEFAULT 0,
    content_type  TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    causation_id  TEXT NOT NULL DEFAULT '',
    actor         TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, seq),
    UNIQUE (event_id)
);
CREATE INDEX IF NOT EXISTS idx_events_tenant_type_seq ON events (tenant_id, type, seq);
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE events FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON events
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

CREATE TABLE IF NOT EXISTS events_outbox (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    event_id     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    attempts     INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_outbox_claim ON events_outbox (status, available_at);
ALTER TABLE events_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE events_outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON events_outbox
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
