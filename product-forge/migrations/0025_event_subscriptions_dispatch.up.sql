-- BI-PF-1269 / Epic BI-PF-1265: persisted subscriptions and delivery state.
-- One event store remains authoritative; this adds no second event table.

CREATE TABLE IF NOT EXISTS event_subscriptions (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    event_types   JSONB NOT NULL DEFAULT '[]'::jsonb,
    filter        JSONB NOT NULL DEFAULT '{}'::jsonb,
    transport     TEXT NOT NULL,
    target        TEXT NOT NULL DEFAULT '',
    auth_ref      TEXT NOT NULL DEFAULT '',
    enabled       BOOLEAN NOT NULL DEFAULT true,
    last_seq      BIGINT NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_event_subscriptions_tenant_enabled
    ON event_subscriptions (tenant_id, enabled);
ALTER TABLE event_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_subscriptions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON event_subscriptions
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

CREATE TABLE IF NOT EXISTS event_deliveries (
    subscription_id TEXT NOT NULL REFERENCES event_subscriptions(id) ON DELETE CASCADE,
    tenant_id       TEXT NOT NULL,
    event_id        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'processing'
                    CHECK (status IN ('processing','retry','delivered','failed')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    available_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error      TEXT NOT NULL DEFAULT '',
    delivered_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (subscription_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_event_deliveries_attention
    ON event_deliveries (status, available_at);
ALTER TABLE event_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_deliveries FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON event_deliveries
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

CREATE TABLE IF NOT EXISTS event_delivery_dlq (
    subscription_id TEXT NOT NULL,
    tenant_id       TEXT NOT NULL,
    event_id        TEXT NOT NULL,
    attempts        INTEGER NOT NULL,
    last_error      TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (subscription_id, event_id)
);
ALTER TABLE event_delivery_dlq ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_delivery_dlq FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON event_delivery_dlq
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
