-- EDP-19 (BI-PF-1311): transactional outbox - at-least-once async effects, one owner boundary.
-- Append MUST be in the same tx as the state change; workers claim batches and mark delivered/failed.

CREATE TABLE outbox (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT '',
    payload      BYTEA,
    at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       TEXT NOT NULL DEFAULT 'pending',   -- pending | claimed | delivered | failed
    attempts     INTEGER NOT NULL DEFAULT 0,
    reason       TEXT NOT NULL DEFAULT '',
    delivered_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_outbox_claim ON outbox (status, at);

ALTER TABLE outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON outbox
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
