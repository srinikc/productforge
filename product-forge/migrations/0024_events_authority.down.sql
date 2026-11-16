-- Destructive: require verified PostgreSQL PITR/base backup + object manifest before running.
DROP TABLE IF EXISTS events_outbox;
DROP TABLE IF EXISTS events;
