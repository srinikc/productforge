-- BI-PF-1271 / Epic BI-PF-1265: Alert policy rules and sliding throttle state.
-- Provides tenant-isolated alert rules and deduplication state with RLS.

CREATE TABLE IF NOT EXISTS alert_rules (
    id                      TEXT PRIMARY KEY,
    tenant_id               TEXT NOT NULL,
    name                    TEXT NOT NULL DEFAULT '',
    event_types             JSONB NOT NULL DEFAULT '[]'::jsonb,
    min_severity            TEXT NOT NULL DEFAULT 'low'
                            CHECK (min_severity IN ('low', 'medium', 'high', 'critical')),
    channels                JSONB NOT NULL DEFAULT '[]'::jsonb,
    throttle_window_seconds INTEGER NOT NULL DEFAULT 0,
    escalate                BOOLEAN NOT NULL DEFAULT false,
    escalate_channel        TEXT NOT NULL DEFAULT '',
    enabled                 BOOLEAN NOT NULL DEFAULT true,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_tenant_enabled
    ON alert_rules (tenant_id, enabled);

ALTER TABLE alert_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_rules FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON alert_rules
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

CREATE TABLE IF NOT EXISTS alert_throttle_state (
    tenant_id          TEXT NOT NULL,
    rule_id            TEXT NOT NULL,
    fingerprint        TEXT NOT NULL,
    first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    suppressed_count   BIGINT NOT NULL DEFAULT 0,
    window_expires_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, rule_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_alert_throttle_expires
    ON alert_throttle_state (tenant_id, window_expires_at);

ALTER TABLE alert_throttle_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_throttle_state FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON alert_throttle_state
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
