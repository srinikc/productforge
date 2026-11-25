-- Backlog SSOT / one writer for PF-SB and PF-GP:
-- one Go/PostgreSQL item writer, one global ID allocation authority, idempotent reservations.
-- Global numeric IDs avoid collisions even when different scopes use the same tag.
-- 1508 starts above the quarantined Git counter value 1507.

CREATE TABLE IF NOT EXISTS backlog_id_allocations (
    authority TEXT PRIMARY KEY,
    next_id   BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS backlog_id_reservations (
    reservation_id TEXT PRIMARY KEY,
    scope          TEXT NOT NULL,
    project_id     TEXT NOT NULL DEFAULT '',
    start_id       BIGINT NOT NULL,
    end_id         BIGINT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO backlog_id_allocations(authority, next_id)
VALUES ('global', 1508)
ON CONFLICT (authority) DO NOTHING;

GRANT SELECT, INSERT, UPDATE ON backlog_id_allocations TO pf_runtime;
GRANT SELECT, INSERT, DELETE ON backlog_id_reservations TO pf_runtime;
