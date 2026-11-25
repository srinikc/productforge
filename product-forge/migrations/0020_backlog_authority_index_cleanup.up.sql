SET LOCAL lock_timeout = '5s';
DROP INDEX IF EXISTS idx_backlog_items_tenant_count;
CREATE INDEX IF NOT EXISTS idx_backlog_items_tenant_count
    ON backlog_items (tenant_id);
