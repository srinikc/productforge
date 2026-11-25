-- BI-PF-1546: retention timestamp for event deliveries.
ALTER TABLE event_deliveries ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
