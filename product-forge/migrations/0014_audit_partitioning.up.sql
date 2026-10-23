-- EDP-20 / BI-PF-1312: monthly RANGE(at) partitioning for the append-only audit log.
--
-- Phase 1 (this file) is DDL ONLY and transactional: shadow table + partitions + primitives.
-- Phase 2 (go/pfaudit) copies, verifies and swaps outside this transaction. Retention/export/purge are
-- primitives here; all object-storage I/O and orchestration live in Go (single writer).
--
-- Canonical names: the live partitioned sequence is audit_id_seq; the legacy sequence is renamed
-- audit_legacy_id_seq. --down swaps the names back. No other name is used.

-- ---- 1. sequence handoff (canonical names) -------------------------------------------------------
-- Re-entry guard: after a committed swap the substrate is live under its final names. Re-creating a
-- shadow then would be unsafe, so refuse early (the runner's transaction rolls back cleanly).
DO $$
BEGIN
    IF to_regclass('public.audit_legacy') IS NOT NULL
       AND to_regclass('public.audit_partitioned') IS NULL THEN
        RAISE EXCEPTION '0014: swap already committed (audit is partitioned); nothing to apply';
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('audit_id_seq') IS NOT NULL
       AND to_regclass('audit_legacy_id_seq') IS NULL THEN
        ALTER SEQUENCE audit_id_seq RENAME TO audit_legacy_id_seq;
    END IF;
END $$;

CREATE SEQUENCE IF NOT EXISTS audit_id_seq;

-- ---- 2. config (single source for horizon/thresholds) ---------------------------------------------
CREATE TABLE IF NOT EXISTS audit_partition_config (
    id               BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),
    horizon_months   INTEGER NOT NULL DEFAULT 3  CHECK (horizon_months BETWEEN 1 AND 36),
    lead_months      INTEGER NOT NULL DEFAULT 2  CHECK (lead_months >= 1),
    batch_rows       INTEGER NOT NULL DEFAULT 10000 CHECK (batch_rows > 0),
    max_delta_rows   INTEGER NOT NULL DEFAULT 5000  CHECK (max_delta_rows > 0),
    rollback_days    INTEGER NOT NULL DEFAULT 14,
    purge_grace_days INTEGER NOT NULL DEFAULT 90,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO audit_partition_config (id) VALUES (TRUE) ON CONFLICT (id) DO NOTHING;

CREATE OR REPLACE FUNCTION audit_config_touch() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS audit_partition_config_touch ON audit_partition_config;
CREATE TRIGGER audit_partition_config_touch BEFORE UPDATE ON audit_partition_config
    FOR EACH ROW EXECUTE FUNCTION audit_config_touch();

-- ---- 3. shadow partitioned table ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_partitioned (
    id             BIGINT NOT NULL DEFAULT nextval('audit_id_seq'),
    tenant_id      TEXT NOT NULL,
    actor          TEXT NOT NULL DEFAULT '',
    action         TEXT NOT NULL,
    resource       TEXT NOT NULL DEFAULT '',
    outcome        TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, at)
) PARTITION BY RANGE (at);

CREATE INDEX IF NOT EXISTS idx_audit_partitioned_tenant_at
    ON audit_partitioned (tenant_id, at DESC);

-- ---- 4. operational state (pf_owner only; projection of the events table) -------------------------
CREATE TABLE IF NOT EXISTS audit_migration_state (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_migration_state_events (
    seq        BIGSERIAL PRIMARY KEY,
    actor      TEXT NOT NULL DEFAULT '',
    from_state TEXT NOT NULL DEFAULT '',
    to_state   TEXT NOT NULL,
    detail     JSONB NOT NULL DEFAULT '{}'::jsonb,
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- 5. legal holds (row level; append-only) ------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_legal_hold_events (
    seq        BIGSERIAL PRIMARY KEY,
    hold_id    TEXT NOT NULL,
    tenant_id  TEXT NOT NULL DEFAULT '',
    month      TEXT NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('hold', 'release')),
    actor      TEXT NOT NULL DEFAULT '',
    reason     TEXT NOT NULL DEFAULT '',
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_hold_events_month
    ON audit_legal_hold_events (month, action);


CREATE TABLE IF NOT EXISTS audit_legal_hold_archive (
    hold_id          TEXT NOT NULL,
    id               BIGINT NOT NULL,
    tenant_id        TEXT NOT NULL,
    actor            TEXT NOT NULL DEFAULT '',
    action           TEXT NOT NULL,
    resource         TEXT NOT NULL DEFAULT '',
    outcome          TEXT NOT NULL DEFAULT '',
    correlation_id   TEXT NOT NULL DEFAULT '',
    at               TIMESTAMPTZ NOT NULL,
    reason           TEXT NOT NULL DEFAULT '',
    source_partition TEXT NOT NULL,
    held_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hold_id, id, at)
);
CREATE INDEX IF NOT EXISTS idx_audit_hold_archive_source
    ON audit_legal_hold_archive (source_partition);

-- Spoliation guard: a hold cannot be recorded against a month whose archive was already purged.
CREATE OR REPLACE FUNCTION audit_hold_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    IF NEW.action = 'hold' AND EXISTS (
        SELECT 1 FROM audit_archive_manifest m WHERE m.month = NEW.month AND m.purged_at IS NOT NULL) THEN
        INSERT INTO audit_migration_state_events(actor, from_state, to_state, detail)
        VALUES (current_user, 'hold_after_purge', 'hold_after_purge',
                jsonb_build_object('month', NEW.month, 'hold_id', NEW.hold_id));
        RAISE EXCEPTION 'audit_hold_guard: % was purged; cannot place hold % (spoliation attempt recorded)',
            NEW.month, NEW.hold_id;
    END IF;
    RETURN NEW;
END $$;

-- ---- 6. archive manifest (cold objects + purge approval, actor/time/reason recorded) --------------
CREATE TABLE IF NOT EXISTS audit_archive_manifest (
    month           TEXT PRIMARY KEY,
    row_count       BIGINT NOT NULL DEFAULT 0,
    checksum        TEXT NOT NULL DEFAULT '',
    object_keys     JSONB NOT NULL DEFAULT '[]'::jsonb,
    archived_at     TIMESTAMPTZ,
    purged_at       TIMESTAMPTZ,
    approved_by     TEXT NOT NULL DEFAULT '',
    approval_reason TEXT NOT NULL DEFAULT ''
);

-- ---- 7. coverage / rotation (holiday-proof date math) ---------------------------------------------
CREATE OR REPLACE FUNCTION audit_month_start(ts TIMESTAMPTZ) RETURNS DATE
LANGUAGE sql IMMUTABLE AS $$
    SELECT (date_trunc('month', ts AT TIME ZONE 'UTC'))::date
$$;

CREATE OR REPLACE FUNCTION audit_partition_name(month DATE) RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
    SELECT 'audit_' || to_char(month, 'YYYYMM')
$$;

-- Partition bounds are UTC instants, never server-local dates.
CREATE OR REPLACE FUNCTION audit_month_ts(month DATE) RETURNS TIMESTAMPTZ
LANGUAGE sql IMMUTABLE AS $$
    SELECT (month::timestamp AT TIME ZONE 'UTC')
$$;

-- ---- 7b. live parent resolution (pre-swap shadow, post-swap audit) --------------------------------
CREATE OR REPLACE FUNCTION audit_parent() RETURNS regclass
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT CASE
        WHEN to_regclass('public.audit') IS NOT NULL
             AND (SELECT relkind = 'p' FROM pg_class WHERE oid = to_regclass('public.audit'))
        THEN to_regclass('public.audit')
        ELSE to_regclass('public.audit_partitioned')
    END
$$;

-- ---- 8. hardening + enforce-by-privilege ----------------------------------------------------------
CREATE OR REPLACE FUNCTION audit_harden_partition(p_name TEXT) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    v_reg regclass := to_regclass(CASE WHEN p_name LIKE '%.%' THEN p_name ELSE 'public.' || p_name END);
BEGIN
    IF v_reg IS NULL THEN
        RAISE EXCEPTION 'audit_harden_partition: % does not exist', p_name;
    END IF;
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', v_reg);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', v_reg);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %s', v_reg);
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON %s USING (tenant_id = current_setting(''app.tenant_id'', true)) ' ||
        'WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))', v_reg);
    -- FORCE RLS also applies to the owner: without this policy pf_owner sees 0 rows in a leaf.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_owner') THEN
        EXECUTE format('DROP POLICY IF EXISTS owner_bypass ON %s', v_reg);
        EXECUTE format('CREATE POLICY owner_bypass ON %s TO pf_owner USING (true) WITH CHECK (true)', v_reg);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
                   WHERE tgrelid = v_reg AND tgname = p_name || '_append_only') THEN
        EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %s '
                       'FOR EACH ROW EXECUTE FUNCTION deny_mutation()',
                       p_name || '_append_only', v_reg);
    END IF;
    -- deliberately NO app/tenant grants on leaves: access flows through the parent.
END $$;

CREATE OR REPLACE FUNCTION audit_attach_partition(p_month DATE) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    v_name TEXT := audit_partition_name(p_month);
    v_from TIMESTAMPTZ := audit_month_ts(p_month);
    v_to   TIMESTAMPTZ := audit_month_ts((p_month + interval '1 month')::date);
BEGIN
    IF audit_parent() IS NULL THEN
        RAISE EXCEPTION 'audit_attach_partition: no audit parent (run migration 0014)';
    END IF;
    IF to_regclass('public.' || v_name) IS NULL THEN
        BEGIN
            EXECUTE format('CREATE TABLE public.%I PARTITION OF %s FOR VALUES FROM (%L) TO (%L)',
                           v_name, audit_parent(), v_from, v_to);
        EXCEPTION WHEN exclusion_violation THEN
            -- The grace partition already owns this range; the insert is covered, no canonical leaf needed.
            IF to_regclass('public.' || v_name) IS NULL THEN
                RETURN v_name;
            END IF;
        END;
    END IF;
    PERFORM audit_harden_partition(v_name);
    RETURN v_name;
END $$;

CREATE OR REPLACE FUNCTION audit_assert_hardened() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT c.relname
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        WHERE i.inhparent = audit_parent()
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE n.nspname = 'public' AND c.relname = r.relname
                         AND c.relrowsecurity AND c.relforcerowsecurity) THEN
            RAISE EXCEPTION 'audit_assert_hardened: leaf % has no FORCE RLS', r.relname;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_policies
                       WHERE schemaname = 'public' AND tablename = r.relname AND policyname = 'tenant_isolation'
                         AND qual LIKE '%app.tenant_id%') THEN
            RAISE EXCEPTION 'audit_assert_hardened: leaf % has no tenant_isolation policy', r.relname;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_trigger
                       WHERE tgrelid = to_regclass('public.' || r.relname) AND tgname LIKE '%append_only') THEN
            RAISE EXCEPTION 'audit_assert_hardened: leaf % has no append-only trigger', r.relname;
        END IF;
    END LOOP;
END $$;

-- ---- 9. ensure (bounded: never creates more than horizon months ahead) ----------------------------
CREATE OR REPLACE FUNCTION audit_ensure_partitions(p_through DATE DEFAULT NULL) RETURNS INTEGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    v_horizon INTEGER;
    v_cur DATE := audit_month_start(now());
    v_target DATE;
    v_n INTEGER := 0;
BEGIN
    SELECT horizon_months INTO v_horizon FROM audit_partition_config WHERE id;
    PERFORM audit_advisory_lock('AUDP');  -- serialise with the insert fast path before creating leaves
    -- A late event can reference a past month (Append heal): create exactly that month, never a horizon.
    IF p_through IS NOT NULL AND (audit_month_start(p_through) < v_cur - interval '24 months'
                                   OR audit_month_start(p_through) > v_cur + make_interval(months => v_horizon)) THEN
        RAISE EXCEPTION 'audit_ensure_partitions: % is outside the provisionable window', p_through;
    END IF;
    IF p_through IS NOT NULL AND audit_month_start(p_through) < v_cur THEN
        IF to_regclass('public.' || audit_partition_name(audit_month_start(p_through))) IS NULL THEN
            PERFORM audit_attach_partition(audit_month_start(p_through));
            RETURN 1;
        END IF;
        RETURN 0;
    END IF;
    v_target := COALESCE(audit_month_start(p_through), v_cur) + make_interval(months => v_horizon) - interval '1 month';
    WHILE v_cur <= v_target::date LOOP
        IF to_regclass('public.' || audit_partition_name(v_cur)) IS NULL THEN
            PERFORM audit_attach_partition(v_cur);
            v_n := v_n + 1;
        END IF;
        v_cur := (v_cur + interval '1 month')::date;
    END LOOP;
    RETURN v_n;
END $$;

-- Advisory lock namespaces (must match go/pfaudit): AUDP insert provisioning, AUSW swap, AURE retention.
CREATE OR REPLACE FUNCTION audit_advisory_lock(p_ns TEXT) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF p_ns NOT IN ('AUDP', 'AUSW', 'AURE') THEN
        RAISE EXCEPTION 'audit_advisory_lock: unknown namespace %', p_ns;
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext(p_ns));
END $$;

-- ---- 10. insert-path provisioning: lock-free fast path --------------------------------------------
CREATE OR REPLACE FUNCTION audit_provision() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    v_month DATE := audit_month_start(NEW.at);
    v_name  TEXT := audit_partition_name(v_month);
BEGIN
    -- The trigger is cloned onto every leaf; only the parent insert path may provision. A leaf insert (e.g.
    -- cold restore into a scratch partition) must never try to attach the canonical month alongside it.
    IF TG_TABLE_NAME <> audit_parent()::text THEN
        RETURN NEW;
    END IF;
    IF to_regclass('public.' || v_name) IS NOT NULL THEN
        RETURN NEW;  -- fast path: existing leaves accept backdated rows (prestage/backfill)
    END IF;
    IF v_month < audit_month_start(now()) - interval '24 months'
       OR v_month > audit_month_start(now()) + make_interval(months => (SELECT horizon_months FROM audit_partition_config WHERE id)) THEN
        -- Keep the documented out-of-range contract: SQLSTATE 23514 + the stable partition message.
        RAISE EXCEPTION 'no partition of relation "audit" found for row (%)', NEW.at USING ERRCODE = '23514';
    END IF;
    PERFORM audit_advisory_lock('AUDP');  -- insert-path namespace
    BEGIN
        PERFORM audit_attach_partition(v_month);
    EXCEPTION WHEN duplicate_table OR unique_violation OR exclusion_violation THEN
        NULL;  -- 42P07 race, or the grace partition already covers the range
    END;
    RETURN NEW;
END $$;

-- ---- 11. coverage ---------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION audit_partition_coverage()
RETURNS TABLE(min_month DATE, max_month DATE, grace_month DATE, months_ahead INTEGER)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    v_lead INTEGER;
BEGIN
    SELECT lead_months INTO v_lead FROM audit_partition_config WHERE id;
    RETURN QUERY
    WITH leaves AS (
        SELECT (regexp_match(c.relname, '^audit_(\d{6})$'))[1] AS ym
        FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
        WHERE i.inhparent = audit_parent()
    ), m AS (
        SELECT to_date(ym, 'YYYYMM') AS mon FROM leaves WHERE ym IS NOT NULL
    )
    SELECT min(mon), max(mon),
           COALESCE((SELECT to_date(substr(c.relname, 13, 6), 'YYYYMM')
                       FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
                      WHERE i.inhparent = audit_parent() AND c.relname LIKE 'audit_grace_%'
                      ORDER BY c.relname DESC LIMIT 1),
                    (min(mon) - interval '1 month')::date),
           COALESCE((EXTRACT(YEAR FROM max(mon)) * 12 + EXTRACT(MONTH FROM max(mon)))
                  - (EXTRACT(YEAR FROM audit_month_start(now())) * 12 + EXTRACT(MONTH FROM audit_month_start(now()))), 0)::int
    FROM m;
END $$;

-- ---- 12. late evidence (bounded ad-hoc month; excluded from coverage) -----------------------------
CREATE OR REPLACE FUNCTION audit_append_late(
    p_tenant TEXT, p_actor TEXT, p_action TEXT, p_resource TEXT, p_outcome TEXT,
    p_correlation TEXT, p_at TIMESTAMPTZ, p_reason TEXT) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    v_month DATE := audit_month_start(p_at);
    v_covered TEXT := audit_partition_name(v_month);
    v_id BIGINT;
BEGIN
    IF v_month < audit_month_start(now()) - interval '24 months' THEN
        RAISE EXCEPTION 'audit_append_late: % is older than the 24-month lookback', p_at;
    END IF;
    -- Archived/purged months are immutable: a late row would invalidate the manifest or resurrect a purge.
    IF EXISTS (SELECT 1 FROM audit_archive_manifest
               WHERE month = v_covered AND (archived_at IS NOT NULL OR purged_at IS NOT NULL)) THEN
        RAISE EXCEPTION 'audit_append_late: % is archived; restore it before appending', v_covered;
    END IF;
    -- A late row in a held month must not bypass the hold archive (it would be dropped unextracted).
    IF EXISTS (SELECT 1 FROM audit_legal_hold_events h
               WHERE h.month = audit_partition_name(v_month) AND h.action = 'hold'
                 AND NOT EXISTS (SELECT 1 FROM audit_legal_hold_events r
                                  WHERE r.hold_id = h.hold_id AND r.action = 'release' AND r.at > h.at)) THEN
        RAISE EXCEPTION 'audit_append_late: % has an active legal hold; use the hold workflow', p_at;
    END IF;
    -- Always use the canonical month partition: a separate audit_late_* range would overlap the month
    -- partition that rotation later tries to attach (23P01) and could never be dropped by retention.
    IF to_regclass('public.' || v_covered) IS NULL THEN
        PERFORM audit_attach_partition(v_month);
    END IF;
    EXECUTE format('INSERT INTO public.%I (tenant_id, actor, action, resource, outcome, correlation_id, at) '
                   'VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id', v_covered)
        INTO v_id USING p_tenant, p_actor, p_action, p_resource, p_outcome, p_correlation, p_at;
    INSERT INTO audit_migration_state_events(actor, from_state, to_state, detail)
        VALUES (current_user, 'late_insert', 'late_insert',
                jsonb_build_object('id', v_id, 'month', v_covered, 'reason', p_reason));
    RETURN v_id;
END $$;

-- ---- 13. retention primitives (SQL only; Go owns object I/O) ---------------------------------------
CREATE OR REPLACE FUNCTION audit_retention_candidates(p_keep_months INTEGER)
RETURNS TABLE(month TEXT, month_start DATE) LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
    SELECT c.relname, to_date((regexp_match(c.relname, '^audit_(\d{6})$'))[1], 'YYYYMM')
    FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
    WHERE i.inhparent = audit_parent()
      AND c.relname ~ '^audit_[0-9]{6}$'
      AND to_date((regexp_match(c.relname, '^audit_(\d{6})$'))[1], 'YYYYMM')
          <= audit_month_start(now()) - make_interval(months => GREATEST(p_keep_months, 1))
    ORDER BY 2;
$$;

CREATE OR REPLACE FUNCTION audit_mark_archived(
    p_month TEXT, p_rows BIGINT, p_checksum TEXT, p_keys JSONB) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    INSERT INTO audit_archive_manifest (month, row_count, checksum, object_keys, archived_at)
    VALUES (p_month, p_rows, p_checksum, p_keys, now())
    ON CONFLICT (month) DO UPDATE
      SET row_count = EXCLUDED.row_count, checksum = EXCLUDED.checksum,
          object_keys = EXCLUDED.object_keys, archived_at = now();
END $$;

CREATE OR REPLACE FUNCTION audit_drop_partition(p_month TEXT) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    IF p_month LIKE 'audit_grace_%' THEN
        RAISE EXCEPTION 'audit_drop_partition: % is the grace partition', p_month;
    END IF;
    IF p_month !~ '^audit_[0-9]{6}$' THEN
        RAISE EXCEPTION 'audit_drop_partition: refusing %', p_month;
    END IF;
    IF to_date(substr(p_month, 7, 6), 'YYYYMM') >= audit_month_start(now()) THEN
        RAISE EXCEPTION 'audit_drop_partition: % is current/future (never dropped)', p_month;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM audit_archive_manifest WHERE month = p_month AND archived_at IS NOT NULL) THEN
        RAISE EXCEPTION 'audit_drop_partition: % has no verified archive', p_month;
    END IF;
    -- Cross-check the live rows against the recorded manifest: a filtered/partial export must not drop data.
    -- The exclusive lock closes the race with audit_append_late writers between the count and the DROP.
    EXECUTE format('LOCK TABLE public.%I IN ACCESS EXCLUSIVE MODE', p_month);
    DECLARE
        v_actual BIGINT;
        v_expected BIGINT;
    BEGIN
        EXECUTE format('SELECT count(*) FROM public.%I', p_month) INTO v_actual;
        SELECT row_count INTO v_expected FROM audit_archive_manifest WHERE month = p_month;
        IF v_actual <> v_expected THEN
            RAISE EXCEPTION 'audit_drop_partition: % has % row(s) but the manifest recorded % - refusing',
                p_month, v_actual, v_expected;
        END IF;
    END;
    IF EXISTS (SELECT 1 FROM audit_legal_hold_events WHERE month = p_month AND action = 'hold'
               AND hold_id NOT IN (SELECT hold_id FROM audit_legal_hold_events e
                                   WHERE e.month = p_month AND e.action = 'release'
                                     AND e.at > audit_legal_hold_events.at)) THEN
        RAISE EXCEPTION 'audit_drop_partition: % has an active hold', p_month;
    END IF;
    EXECUTE format('DROP TABLE public.%I', p_month);
END $$;

CREATE OR REPLACE FUNCTION audit_purge_candidates(p_grace_days INTEGER)
RETURNS TABLE(month TEXT, archived_at TIMESTAMPTZ) LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
    SELECT month, archived_at FROM audit_archive_manifest
    WHERE archived_at IS NOT NULL AND purged_at IS NULL
      AND archived_at < now() - make_interval(days => GREATEST(p_grace_days, 0))
    ORDER BY archived_at;
$$;

CREATE OR REPLACE FUNCTION audit_restore_lock(p_month TEXT, p_actor TEXT, p_reason TEXT) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    INSERT INTO audit_migration_state_events(actor, from_state, to_state, detail)
    VALUES (p_actor, 'restore', 'restore', jsonb_build_object('month', p_month, 'reason', p_reason));
END $$;

CREATE OR REPLACE FUNCTION audit_approve_purge(p_month TEXT, p_actor TEXT, p_reason TEXT) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    -- Resumable: a crash after mark_purged must not wedge the month; deleting objects again is idempotent.
    IF EXISTS (SELECT 1 FROM audit_archive_manifest WHERE month = p_month AND purged_at IS NOT NULL) THEN
        RETURN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM audit_purge_candidates(
        (SELECT purge_grace_days FROM audit_partition_config WHERE id)) WHERE month = p_month) THEN
        RAISE EXCEPTION 'audit_approve_purge: % is not a purge candidate', p_month;
    END IF;
    IF EXISTS (SELECT 1 FROM audit_legal_hold_events WHERE month = p_month AND action = 'hold'
               AND hold_id NOT IN (SELECT hold_id FROM audit_legal_hold_events e
                                   WHERE e.month = p_month AND e.action = 'release' AND e.at > audit_legal_hold_events.at)) THEN
        RAISE EXCEPTION 'audit_approve_purge: % has an active hold', p_month;
    END IF;
    UPDATE audit_archive_manifest
       SET approved_by = p_actor, approval_reason = p_reason
     WHERE month = p_month;
END $$;

CREATE OR REPLACE FUNCTION audit_mark_purged(p_month TEXT) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM audit_archive_manifest
                   WHERE month = p_month AND approved_by <> '') THEN
        RAISE EXCEPTION 'audit_mark_purged: % has no recorded approval', p_month;
    END IF;
    UPDATE audit_archive_manifest SET purged_at = now() WHERE month = p_month;
END $$;

-- ---- 14. hold extract (row level) -----------------------------------------------------------------
CREATE OR REPLACE FUNCTION audit_hold_extract(p_month TEXT) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    v_rows BIGINT := 0;
BEGIN
    IF p_month !~ '^audit_[0-9]{6}$' THEN
        RAISE EXCEPTION 'audit_hold_extract: refusing %', p_month;
    END IF;
    EXECUTE format(
      'INSERT INTO audit_legal_hold_archive
         (hold_id, id, tenant_id, actor, action, resource, outcome, correlation_id, at, reason, source_partition)
       SELECT e.hold_id, a.id, a.tenant_id, a.actor, a.action, a.resource, a.outcome, a.correlation_id, a.at,
              e.reason, %L
       FROM public.%I a
       JOIN audit_legal_hold_events e ON e.month = %L AND e.action = ''hold''
         AND (length(e.tenant_id) = 0 OR e.tenant_id = a.tenant_id)
       WHERE NOT EXISTS (SELECT 1 FROM audit_legal_hold_events r
                         WHERE r.hold_id = e.hold_id AND r.action = ''release'' AND r.at > e.at)
         AND NOT EXISTS (SELECT 1 FROM audit_legal_hold_archive x
                         WHERE x.hold_id = e.hold_id AND x.id = a.id AND x.at = a.at)
       ON CONFLICT DO NOTHING', p_month, p_month, p_month);
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    RETURN v_rows;
END $$;

-- ---- 15. RLS / append-only for the new tables -----------------------------------------------------
ALTER TABLE audit_partitioned ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_partitioned FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON audit_partitioned;
CREATE POLICY tenant_isolation ON audit_partitioned
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
-- Owner bypass is scoped TO pf_owner only, so it never widens access for app/tenant roles.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_owner') THEN
    EXECUTE 'DROP POLICY IF EXISTS owner_bypass ON audit_partitioned';
    EXECUTE 'CREATE POLICY owner_bypass ON audit_partitioned TO pf_owner USING (true) WITH CHECK (true)';
  END IF;
END $$;

DROP TRIGGER IF EXISTS audit_partitioned_append_only ON audit_partitioned;
CREATE TRIGGER audit_partitioned_append_only BEFORE UPDATE OR DELETE ON audit_partitioned
    FOR EACH ROW EXECUTE FUNCTION deny_mutation();

-- Row triggers do not fire on TRUNCATE, and owners ignore REVOKE: a statement trigger is the only guard.
CREATE OR REPLACE FUNCTION audit_deny_truncate() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit: TRUNCATE is not permitted on append-only journals';
END $$;
DROP TRIGGER IF EXISTS audit_migration_state_events_no_truncate ON audit_migration_state_events;
CREATE TRIGGER audit_migration_state_events_no_truncate BEFORE TRUNCATE ON audit_migration_state_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_deny_truncate();
DROP TRIGGER IF EXISTS audit_legal_hold_events_no_truncate ON audit_legal_hold_events;
CREATE TRIGGER audit_legal_hold_events_no_truncate BEFORE TRUNCATE ON audit_legal_hold_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_deny_truncate();
DROP TRIGGER IF EXISTS audit_provision_trg ON audit_partitioned;
CREATE TRIGGER audit_provision_trg BEFORE INSERT ON audit_partitioned
    FOR EACH ROW EXECUTE FUNCTION audit_provision();

DROP TRIGGER IF EXISTS audit_legal_hold_guard ON audit_legal_hold_events;
CREATE TRIGGER audit_legal_hold_guard BEFORE INSERT ON audit_legal_hold_events
    FOR EACH ROW EXECUTE FUNCTION audit_hold_guard();

ALTER TABLE audit_legal_hold_archive ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_legal_hold_archive FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON audit_legal_hold_archive;
CREATE POLICY tenant_isolation ON audit_legal_hold_archive
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_owner') THEN
    EXECUTE 'DROP POLICY IF EXISTS owner_bypass ON audit_legal_hold_archive';
    EXECUTE 'CREATE POLICY owner_bypass ON audit_legal_hold_archive TO pf_owner USING (true) WITH CHECK (true)';
  END IF;
END $$;

-- append-only by mechanism even for the owner
CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME; END $$;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['audit_migration_state_events', 'audit_legal_hold_events']
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I_immutable ON %I', t, t);
    EXECUTE format('CREATE TRIGGER %I_immutable BEFORE UPDATE OR DELETE ON %I '
                   'FOR EACH ROW EXECUTE FUNCTION audit_events_immutable()', t, t);
  END LOOP;
END $$;

-- ---- 16. grants (only if the runtime roles exist; test DBs may not have them) ----------------------
DO $$
DECLARE r RECORD;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_app') THEN
    EXECUTE 'REVOKE ALL ON audit_partitioned FROM pf_app';
    EXECUTE 'REVOKE ALL ON audit_legal_hold_archive FROM pf_app';
    EXECUTE 'REVOKE ALL ON audit_migration_state, audit_migration_state_events, audit_archive_manifest, '
            'audit_legal_hold_events, audit_partition_config FROM pf_app';
    -- The shadow is migration-owned pre-swap; app writes stay on the legacy table until the rename.
    EXECUTE 'GRANT SELECT ON audit_partitioned TO pf_app';
    EXECUTE 'GRANT SELECT ON audit_legal_hold_archive TO pf_app';
    -- The append-only journal must not be erasable by the runtime (row triggers do not fire on TRUNCATE).
    EXECUTE 'REVOKE TRUNCATE ON audit_migration_state_events, audit_legal_hold_events FROM pf_app, pf_runtime';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_owner') THEN
    EXECUTE 'GRANT ALL ON audit_partitioned, audit_legal_hold_archive, audit_migration_state, '
            'audit_migration_state_events, audit_archive_manifest, audit_legal_hold_events, '
            'audit_partition_config TO pf_owner';
    EXECUTE 'REVOKE TRUNCATE ON audit_migration_state_events, audit_legal_hold_events FROM pf_owner';
    EXECUTE 'REVOKE TRUNCATE ON audit_partitioned, audit_legal_hold_archive FROM pf_owner';
  END IF;
  EXECUTE 'REVOKE ALL ON audit_partitioned FROM PUBLIC';
  EXECUTE 'REVOKE TRUNCATE ON audit_partitioned, audit_legal_hold_archive FROM PUBLIC';
  EXECUTE 'REVOKE TRUNCATE ON audit_migration_state_events, audit_legal_hold_events FROM PUBLIC';
  -- SECURITY DEFINER primitives are owner-only: PUBLIC EXECUTE would let pf_app forge archives/purges.
  FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname LIKE 'audit\_%'
  LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', r.sig);
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_app') THEN
    EXECUTE 'GRANT EXECUTE ON FUNCTION audit_ensure_partitions(date) TO pf_app';
    EXECUTE 'GRANT EXECUTE ON FUNCTION audit_month_start(timestamptz) TO pf_app';
    EXECUTE 'GRANT EXECUTE ON FUNCTION audit_partition_name(date) TO pf_app';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_runtime') THEN
    EXECUTE 'GRANT EXECUTE ON FUNCTION audit_ensure_partitions(date) TO pf_runtime';
    EXECUTE 'GRANT EXECUTE ON FUNCTION audit_month_start(timestamptz) TO pf_runtime';
    EXECUTE 'GRANT EXECUTE ON FUNCTION audit_partition_name(date) TO pf_runtime';
  END IF;
END $$;

-- ---- 17. initial partitions (legacy_min .. current+horizon, plus one grace month) -----------------
DO $$
DECLARE
    v_min DATE;
    v_cur DATE := audit_month_start(now());
    v_horizon INTEGER;
    v_grace DATE;
BEGIN
    -- Fresh install: there is no legacy table to seed from; rotation starts with the first insert.
    IF to_regclass('public.audit') IS NULL THEN
        RETURN;
    END IF;
    EXECUTE 'SELECT COALESCE(audit_month_start(min(at)), audit_month_start(now())) FROM audit' INTO v_min;
    SELECT horizon_months INTO v_horizon FROM audit_partition_config WHERE id;
    v_grace := (v_min - interval '1 month')::date;
    EXECUTE format('CREATE TABLE IF NOT EXISTS public.%I PARTITION OF %s FOR VALUES FROM (%L) TO (%L)',
                   'audit_grace_' || to_char(v_grace, 'YYYYMM'), audit_parent(), audit_month_ts(v_grace), audit_month_ts(v_min));
    PERFORM audit_harden_partition('audit_grace_' || to_char(v_grace, 'YYYYMM'));
    WHILE v_min <= (v_cur + make_interval(months => v_horizon) - interval '1 month')::date LOOP
        PERFORM audit_attach_partition(v_min);
        v_min := (v_min + interval '1 month')::date;
    END LOOP;
    PERFORM setval('audit_id_seq', GREATEST(
        (SELECT COALESCE(max(id), 0) FROM audit), (SELECT last_value FROM audit_legacy_id_seq)) + 1, false);
    PERFORM audit_assert_hardened();
END $$;
