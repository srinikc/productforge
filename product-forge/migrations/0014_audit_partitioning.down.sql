-- EDP-20 / BI-PF-1312 down: drop the partitioning substrate.
--
-- Safe on a database where the swap has NOT run (audit is still the legacy table). When the swap HAS run,
-- go/pfaudit --down must be used instead (it is gated on archives/holds and restores the sequence names);
-- this SQL migration then only removes the (now empty) shadow objects.
--
-- Canonical names: before the swap, audit_id_seq is the shadow sequence and audit_legacy_id_seq is the
-- live one; the names are restored here.

-- Post-swap the live partitioned table is named audit: refuse rather than half-apply.
DO $$
BEGIN
    IF to_regclass('public.audit_partitioned') IS NULL AND to_regclass('public.audit_legacy') IS NOT NULL THEN
        RAISE EXCEPTION '0014 down: swap is committed; run pfaudit-swap --down first';
    END IF;
    -- Legally held rows must not disappear with a schema rollback.
    IF to_regclass('public.audit_legal_hold_archive') IS NOT NULL
       AND EXISTS (SELECT 1 FROM audit_legal_hold_archive) THEN
        RAISE EXCEPTION '0014 down: legal hold archive is not empty; resolve holds before dropping the substrate';
    END IF;
END $$;

DROP TABLE IF EXISTS audit_partitioned CASCADE;

DROP TABLE IF EXISTS audit_legal_hold_archive;
DROP TABLE IF EXISTS audit_legal_hold_events;
DROP TABLE IF EXISTS audit_archive_manifest;
DROP TABLE IF EXISTS audit_migration_state_events;
DROP TABLE IF EXISTS audit_migration_state;
DROP TABLE IF EXISTS audit_partition_config;

DROP FUNCTION IF EXISTS audit_hold_extract(TEXT);
DROP FUNCTION IF EXISTS audit_approve_purge(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS audit_mark_purged(TEXT);
DROP FUNCTION IF EXISTS audit_purge_candidates(INTEGER);
DROP FUNCTION IF EXISTS audit_mark_archived(TEXT, BIGINT, TEXT, JSONB);
DROP FUNCTION IF EXISTS audit_drop_partition(TEXT);
DROP FUNCTION IF EXISTS audit_retention_candidates(INTEGER);
DROP FUNCTION IF EXISTS audit_restore_lock(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS audit_append_late(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT);
DROP FUNCTION IF EXISTS audit_partition_coverage();
DROP FUNCTION IF EXISTS audit_advisory_lock(TEXT);
DROP FUNCTION IF EXISTS audit_provision();
DROP FUNCTION IF EXISTS audit_ensure_partitions(DATE);
DROP FUNCTION IF EXISTS audit_assert_hardened();
DROP FUNCTION IF EXISTS audit_parent();
DROP FUNCTION IF EXISTS audit_attach_partition(DATE);
DROP FUNCTION IF EXISTS audit_harden_partition(TEXT);
DROP FUNCTION IF EXISTS audit_partition_name(DATE);
DROP FUNCTION IF EXISTS audit_month_ts(DATE);
DROP FUNCTION IF EXISTS audit_month_start(TIMESTAMPTZ);
DROP FUNCTION IF EXISTS audit_events_immutable();

-- restore the canonical sequence names if the shadow one exists
DO $$
BEGIN
    IF to_regclass('audit_legacy_id_seq') IS NOT NULL THEN
        DROP SEQUENCE IF EXISTS audit_id_seq;  -- the shadow sequence (pre-swap only)
        ALTER SEQUENCE audit_legacy_id_seq RENAME TO audit_id_seq;
    END IF;
END $$;
