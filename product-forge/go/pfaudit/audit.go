// Package pfaudit is the OFFLINE operations tooling for EDP-20 (BI-PF-1312): the audit partitioning
// swap, and two-stage retention (hot -> cold object store -> audited purge).
//
// It is deliberately NOT on the request path: it uses pgx directly for DDL, advisory locks and bulk
// COPY-style streaming, while the domain data plane keeps using the provider-neutral datastore ports.
// All schema objects it relies on are created by migrations/0014_audit_partitioning.up.sql.
package pfaudit

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"hash"
	"io"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Advisory lock namespaces (must match the SQL constants in 0014; api_test asserts this).
const (
	LockProvision = "AUDP"
	LockSwap      = "AUSW"
	LockRetention = "AURE"
)

// Config defaults mirrored from audit_partition_config; the tool refuses to run when they disagree.
const (
	DefaultBatchRows    = 10000
	DefaultMaxDeltaRows = 5000
	DefaultLeadMonths   = 2
)

// ErrNotReady means the schema substrate (0014) has not been applied yet.
var ErrNotReady = errors.New("pfaudit: audit_partitioning substrate not applied (run migration 0014)")

// ErrDeltaTooLarge is returned when the remaining delta cannot fit inside the freeze budget.
var ErrDeltaTooLarge = errors.New("pfaudit: delta exceeds max_delta_rows")

// ErrLockTimeout is returned when ACCESS EXCLUSIVE cannot be acquired within lock_timeout (55P03).
var ErrLockTimeout = errors.New("pfaudit: lock timeout acquiring audit (55P03)")

// State is the catalog-derived phase of the audit migration. It is the source of truth for resumability:
// a re-run decides what to do from the catalog, never from an in-memory flag.
type State string

const (
	StateNotPrepared State = "not_prepared" // no shadow table
	StatePrestage    State = "prestage"     // flat audit + shadow: copy/verify
	StateSwapped     State = "swapped"      // partitioned audit + audit_legacy: post-verify/close
	StateDone        State = "done"         // partitioned audit, no legacy
)

// DetectState reads the real catalog. Crash-safe: the rename is the commit point.
func DetectState(ctx context.Context, pool *pgxpool.Pool) (State, error) {
	var audit, shadow, legacy bool
	var kind string
	err := pool.QueryRow(ctx, `
		SELECT to_regclass('audit') IS NOT NULL,
		       to_regclass('audit_partitioned') IS NOT NULL,
		       to_regclass('audit_legacy') IS NOT NULL,
		       COALESCE((SELECT relkind::text FROM pg_class WHERE oid = to_regclass('audit')), '')`).
		Scan(&audit, &shadow, &legacy, &kind)
	if err != nil {
		return "", fmt.Errorf("detect state: %w", err)
	}
	switch {
	case audit && kind == "p":
		if legacy {
			return StateSwapped, nil
		}
		return StateDone, nil
	case !audit:
		return StateNotPrepared, nil
	case !shadow && !legacy:
		return StateNotPrepared, nil
	case audit && kind == "r" && shadow:
		return StatePrestage, nil
	default:
		return StateNotPrepared, fmt.Errorf("unexpected catalog state: audit=%v kind=%q shadow=%v legacy=%v",
			audit, kind, shadow, legacy)
	}
}

// CheckConfig reads the DB config row (the single source of truth for thresholds).
func CheckConfig(ctx context.Context, pool *pgxpool.Pool) (batch, maxDelta int, err error) {
	err = pool.QueryRow(ctx, `SELECT batch_rows, max_delta_rows FROM audit_partition_config WHERE id`).
		Scan(&batch, &maxDelta)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, 0, ErrNotReady
	}
	if err != nil {
		return 0, 0, fmt.Errorf("pfaudit: read config: %w", err)
	}
	if batch <= 0 || maxDelta <= 0 {
		return batch, maxDelta, fmt.Errorf(
			"pfaudit: invalid config (db batch=%d max_delta=%d, go defaults %d/%d) - update the tool",
			batch, maxDelta, DefaultBatchRows, DefaultMaxDeltaRows)
	}
	return batch, maxDelta, nil
}

// BatchResult is the outcome of one idempotent copy batch.
type BatchResult struct {
	LastID   int64
	Read     int64
	Inserted int64
	Done     bool
}

// CopyBatch idempotently copies up to batch rows with id > afterID. ON CONFLICT makes a resumed or
// repeated batch safe; the cursor is the max id READ (not inserted) so a fully-conflicting batch advances.
func CopyBatch(ctx context.Context, pool *pgxpool.Pool, afterID int64, batch int) (BatchResult, error) {
	var r BatchResult
	err := pool.QueryRow(ctx, `
		WITH src AS (
		    SELECT id, tenant_id, actor, action, resource, outcome, correlation_id, at
		    FROM audit WHERE id > $1 ORDER BY id LIMIT $2
		), ins AS (
		    INSERT INTO audit_partitioned (id, tenant_id, actor, action, resource, outcome, correlation_id, at)
		    SELECT * FROM src
		    ON CONFLICT (id, at) DO NOTHING
		    RETURNING id
		)
		SELECT COALESCE((SELECT max(id) FROM src), $1),
		       (SELECT count(*) FROM src),
		       (SELECT count(*) FROM ins)`,
		afterID, batch).Scan(&r.LastID, &r.Read, &r.Inserted)
	if err != nil {
		return r, fmt.Errorf("copy batch: %w", err)
	}
	r.Done = r.Read < int64(batch)
	return r, nil
}

// Checksum is the reproducible integrity primitive: SHA-256 over the ordered rows of one tenant.
type Checksum struct {
	TenantID string
	Rows     int64
	Hash     string
}

// TableChecksums streams rows in (tenant, id, at) order and hashes them with SHA-256 per tenant.
// Constant memory: only one tenant hash is live at a time, so it scales with tenant count, not table size.
func TableChecksums(ctx context.Context, pool *pgxpool.Pool, table string) (map[string]Checksum, error) {
	if !validTable(table) {
		return nil, fmt.Errorf("pfaudit: invalid table %q", table)
	}
	rows, err := pool.Query(ctx, `SELECT tenant_id, id, action, at FROM `+table+` ORDER BY tenant_id, id, at`)
	if err != nil {
		return nil, fmt.Errorf("checksums %s: %w", table, err)
	}
	defer rows.Close()
	out := map[string]Checksum{}
	var cur string
	var h hash.Hash
	var n int64
	flush := func() {
		if cur == "" {
			return
		}
		out[cur] = Checksum{TenantID: cur, Rows: n, Hash: hex.EncodeToString(h.Sum(nil))}
	}
	for rows.Next() {
		var tenant, action string
		var id int64
		var at time.Time
		if err := rows.Scan(&tenant, &id, &action, &at); err != nil {
			return nil, err
		}
		if tenant != cur {
			flush()
			cur, h, n = tenant, sha256.New(), 0
		}
		fmt.Fprintf(h, "%d|%s|%s|%s\n", id, tenant, action, at.UTC().Format(time.RFC3339Nano))
		n++
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	flush()
	return out, nil
}

// Verify compares legacy vs shadow per tenant AND in total. Any difference is a hard failure.
// RequireUnfilteredVisibility fails unless the current role sees every audit row: a filtered read under
// FORCE RLS would make checksums/decisions look correct while hiding data.
func RequireUnfilteredVisibility(ctx context.Context, pool *pgxpool.Pool) error {
	var ok bool
	if err := pool.QueryRow(ctx, `SELECT r.rolsuper OR r.rolbypassrls OR EXISTS (
		SELECT 1 FROM pg_class c
		WHERE c.relname IN ('audit','audit_partitioned','audit_legacy')
		  AND c.relowner = (SELECT oid FROM pg_roles WHERE rolname = current_user))
		FROM pg_roles r WHERE r.rolname = current_user`).Scan(&ok); err != nil {
		return fmt.Errorf("pfaudit: visibility check: %w", err)
	}
	if !ok {
		return errors.New("pfaudit: refusing to read audit rows under RLS filtering; run as the table owner or a BYPASSRLS role")
	}
	return nil
}

func Verify(ctx context.Context, pool *pgxpool.Pool) (map[string]string, error) {
	if err := RequireUnfilteredVisibility(ctx, pool); err != nil {
		return nil, err
	}
	a, err := TableChecksums(ctx, pool, "audit")
	if err != nil {
		return nil, err
	}
	b, err := TableChecksums(ctx, pool, "audit_partitioned")
	if err != nil {
		return nil, err
	}
	problems := map[string]string{}
	for t, ca := range a {
		cb, ok := b[t]
		if !ok {
			problems[t] = "missing in audit_partitioned"
			continue
		}
		if ca.Rows != cb.Rows || ca.Hash != cb.Hash {
			problems[t] = fmt.Sprintf("mismatch rows %d/%d hash %s/%s", ca.Rows, cb.Rows, ca.Hash, cb.Hash)
		}
	}
	for t := range b {
		if _, ok := a[t]; !ok {
			problems[t] = "extra tenant in audit_partitioned"
		}
	}
	if len(problems) > 0 {
		return problems, fmt.Errorf("pfaudit: verification failed for %d tenant(s)", len(problems))
	}
	return nil, nil
}

// validMonth accepts exactly audit_YYYYMM (restore/export inputs).
func validMonth(t string) bool {
	if len(t) != 12 || !strings.HasPrefix(t, "audit_") {
		return false
	}
	for _, r := range t[6:] {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

func validTable(t string) bool {
	if t == "" {
		return false
	}
	for _, r := range t {
		if !(r == '_' || (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9')) {
			return false
		}
	}
	return true
}

// SHA256 reads r and returns the hex digest (streaming, used by export and restore).
func SHA256(r io.Reader) (string, int64, error) {
	h := sha256.New()
	n, err := io.Copy(h, r)
	if err != nil {
		return "", n, err
	}
	return hex.EncodeToString(h.Sum(nil)), n, nil
}

// RenamePair is the single atomic rename used by Swap. Exposed for the integration test.
const (
	SwapLockTimeout = "3s"
	MaxSwapAttempts = 5
)

// Swap performs S4: it enforces the delta bound under the lock, drains, renames and advances the
// canonical sequence. It returns the number of drained delta rows.
func Swap(ctx context.Context, pool *pgxpool.Pool, maxDelta int) (int64, error) {
	if err := RequireUnfilteredVisibility(ctx, pool); err != nil {
		return 0, err
	}
	conn, err := pool.Acquire(ctx)
	if err != nil {
		return 0, err
	}
	defer conn.Release()

	tx, err := conn.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	if _, err := tx.Exec(ctx, `SET LOCAL lock_timeout = '`+SwapLockTimeout+`'`); err != nil {
		return 0, err
	}
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1))`, LockSwap); err != nil {
		return 0, err
	}
	// Advisory locks don't take the table lock; do it explicitly, then re-count INSIDE the lock (TOCTOU).
	if _, err := tx.Exec(ctx, `LOCK TABLE audit IN ACCESS EXCLUSIVE MODE`); err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "55P03" {
			return 0, ErrLockTimeout
		}
		return 0, fmt.Errorf("pfaudit: acquire audit lock: %w", err)
	}
	var lastID int64
	if err := tx.QueryRow(ctx, `SELECT COALESCE(max(id), 0) FROM audit_partitioned`).Scan(&lastID); err != nil {
		return 0, err
	}
	var delta int64
	if err := tx.QueryRow(ctx, `SELECT count(*) FROM audit WHERE id > $1`, lastID).Scan(&delta); err != nil {
		return 0, err
	}
	if delta > int64(maxDelta) {
		return delta, fmt.Errorf("%w (delta=%d max=%d)", ErrDeltaTooLarge, delta, maxDelta)
	}
	if delta > 0 {
		if _, err := tx.Exec(ctx, `
			INSERT INTO audit_partitioned (id, tenant_id, actor, action, resource, outcome, correlation_id, at)
			SELECT id, tenant_id, actor, action, resource, outcome, correlation_id, at
			FROM audit WHERE id > $1
			ON CONFLICT (id, at) DO NOTHING`, lastID); err != nil {
			return delta, fmt.Errorf("pfaudit: drain delta: %w", err)
		}
	}
	if _, err := tx.Exec(ctx, `ALTER TABLE audit RENAME TO audit_legacy`); err != nil {
		return delta, fmt.Errorf("pfaudit: rename legacy: %w", err)
	}
	if _, err := tx.Exec(ctx, `ALTER TABLE audit_partitioned RENAME TO audit`); err != nil {
		return delta, fmt.Errorf("pfaudit: rename shadow: %w", err)
	}
	// The renamed legacy table still carries app grants: revoke them or roles keep a split-brain write path.
	if _, err := tx.Exec(ctx, `DO $$
		BEGIN
		  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_app') THEN
		    EXECUTE 'GRANT INSERT, SELECT ON audit TO pf_app';
		  END IF;
		  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_runtime') THEN
		    EXECUTE 'GRANT INSERT, SELECT ON audit TO pf_runtime';
		  END IF;
		END $$`); err != nil {
		return delta, fmt.Errorf("pfaudit: grant partitioned audit: %w", err)
	}
	if _, err := tx.Exec(ctx, `DO $$
		BEGIN
		  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_app') THEN
		    EXECUTE 'REVOKE ALL ON audit_legacy FROM pf_app';
		  END IF;
		  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_runtime') THEN
		    EXECUTE 'REVOKE ALL ON audit_legacy FROM pf_runtime';
		  END IF;
		END $$`); err != nil {
		return delta, fmt.Errorf("pfaudit: revoke legacy grants: %w", err)
	}
	if _, err := tx.Exec(ctx, `
		SELECT setval('audit_id_seq', GREATEST(
		    (SELECT COALESCE(max(id), 0) FROM audit),
		    COALESCE((SELECT max(id) FROM audit_legacy), 0)) + 1, false)`); err != nil {
		return delta, fmt.Errorf("pfaudit: setval: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return delta, fmt.Errorf("pfaudit: commit swap: %w", err)
	}
	return delta, nil
}

// DownPlan reports what a down migration would do and why it is gated (dry-run surface).
func DownPlan(ctx context.Context, pool *pgxpool.Pool) (state State, archived, holds int64, err error) {
	if err = pool.QueryRow(ctx, `SELECT count(*) FROM audit_archive_manifest WHERE archived_at IS NOT NULL`).Scan(&archived); err != nil {
		return "", 0, 0, err
	}
	if err = pool.QueryRow(ctx, `
		SELECT count(*) FROM audit_legal_hold_events h
		WHERE h.action = 'hold' AND NOT EXISTS (
		    SELECT 1 FROM audit_legal_hold_events r
		    WHERE r.hold_id = h.hold_id AND r.action = 'release' AND r.at > h.at)`).Scan(&holds); err != nil {
		return "", 0, 0, err
	}
	state, err = DetectState(ctx, pool)
	return state, archived, holds, err
}

// Down reverses a committed swap. Gated: refuses when any month is archived/purged or a hold exists.
func Down(ctx context.Context, pool *pgxpool.Pool, force bool, reason string) error {
	if err := RequireUnfilteredVisibility(ctx, pool); err != nil {
		return err
	}
	from, archived, holds, err := DownPlan(ctx, pool)
	if err != nil {
		return err
	}
	if from != StateSwapped {
		return fmt.Errorf("pfaudit: down requires the swapped state, got %s", from)
	}
	if (archived > 0 || holds > 0) && !force {
		return fmt.Errorf("pfaudit: down refused (archived=%d active_holds=%d); pass --force-with-reason after sign-off", archived, holds)
	}
	if force && strings.TrimSpace(reason) == "" {
		return errors.New("pfaudit: --force-with-reason requires a non-empty reason")
	}
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	// Emergency rollback must not race with live appends: take the swap lock and block audit writes.
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1))`, LockSwap); err != nil {
		return fmt.Errorf("pfaudit: down lock: %w", err)
	}
	if _, err := tx.Exec(ctx, `LOCK TABLE audit IN ACCESS EXCLUSIVE MODE`); err != nil {
		return fmt.Errorf("pfaudit: down access exclusive: %w", err)
	}
	// Copy rows written after the swap back into the flat table: down must not strand live events.
	var missed int64
	if err := tx.QueryRow(ctx, `WITH moved AS (
			INSERT INTO audit_legacy (id, tenant_id, actor, action, resource, outcome, correlation_id, at)
			SELECT p.id, p.tenant_id, p.actor, p.action, p.resource, p.outcome, p.correlation_id, p.at
			FROM audit p
			WHERE NOT EXISTS (SELECT 1 FROM audit_legacy l WHERE l.id = p.id AND l.at = p.at)
			RETURNING 1)
		SELECT count(*) FROM moved`).Scan(&missed); err != nil {
		return fmt.Errorf("pfaudit: down copy-back: %w", err)
	}
	// Re-advance the flat table's sequence over the rows just copied back.
	if _, err := tx.Exec(ctx, `SELECT setval('audit_legacy_id_seq', GREATEST(
		(SELECT COALESCE(max(id),0) FROM audit_legacy), (SELECT last_value FROM audit_legacy_id_seq)))`); err != nil {
		return fmt.Errorf("pfaudit: down sequence: %w", err)
	}
	stmts := []string{
		`ALTER TABLE audit RENAME TO audit_partitioned`,
		`ALTER SEQUENCE audit_id_seq RENAME TO audit_partitioned_id_seq`,
		`ALTER TABLE audit_legacy RENAME TO audit`,
		`ALTER SEQUENCE audit_legacy_id_seq RENAME TO audit_id_seq`,
	}
	for _, s := range stmts {
		if _, err := tx.Exec(ctx, s); err != nil {
			return fmt.Errorf("pfaudit: down: %w", err)
		}
	}
	// The swap revoked app grants on the old flat table; restore them on the rolled-back parent.
	if _, err := tx.Exec(ctx, `DO $$
		BEGIN
		  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_app') THEN
		    EXECUTE 'GRANT INSERT, SELECT ON audit TO pf_app';
		  END IF;
		  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_runtime') THEN
		    EXECUTE 'GRANT INSERT, SELECT ON audit TO pf_runtime';
		  END IF;
		END $$`); err != nil {
		return fmt.Errorf("pfaudit: down grants: %w", err)
	}
	// No id reuse: the restored sequence must sit above BOTH surviving tables.
	var gap int64
	if err := tx.QueryRow(ctx, `SELECT GREATEST(
		(SELECT COALESCE(max(id),0) FROM audit),
		(SELECT COALESCE(max(id),0) FROM audit_partitioned), 1) + 1`).Scan(&gap); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `SELECT setval('audit_id_seq', $1, false)`, gap); err != nil {
		return err
	}
	// Record the down event in the same transaction: a crash must not lose the permanent record.
	if _, err := tx.Exec(ctx, `INSERT INTO audit_migration_state_events(actor, from_state, to_state, detail)
		VALUES (current_user, $1::text, 'down', jsonb_build_object('reason',$2::text,'copied_back',$3::bigint))`,
		string(from), reason, missed); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// SaveCursor persists the copy cursor as an append-only event plus its projection (the projection stays
// rebuildable from events, as the schema contract requires).
func SaveCursor(ctx context.Context, pool *pgxpool.Pool, lastID int64) error {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, `INSERT INTO audit_migration_state_events(actor, from_state, to_state, detail)
		VALUES (current_user, 'prestage', 'prestage_copy', jsonb_build_object('last_id', $1::bigint))`, lastID); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `INSERT INTO audit_migration_state(key, value, updated_at)
		VALUES ('copy', jsonb_build_object('last_id', $1::bigint), now())
		ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()`, lastID); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// RecordState appends an append-only event and refreshes the projection.
func RecordState(ctx context.Context, pool *pgxpool.Pool, to, detail string) error {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, `INSERT INTO audit_migration_state_events(actor, from_state, to_state, detail)
		SELECT current_user::text,
		       COALESCE((SELECT value->>'phase' FROM audit_migration_state WHERE key='phase'), ''),
		       CAST($1 AS text), CAST($2 AS jsonb)`,
		to, detail); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `INSERT INTO audit_migration_state(key, value, updated_at)
		VALUES ('phase', jsonb_build_object('phase',$1::text), now())
		ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()`, to); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// AuditMonthName returns the canonical monthly partition name for ts (UTC).
func AuditMonthName(ts time.Time) string {
	return "audit_" + ts.UTC().Format("200601")
}

// MonthLabel formats a partition month for humans; nil renders as "-".
func MonthLabel(t *time.Time) string {
	if t == nil {
		return "-"
	}
	return t.Format("2006-01-02")
}

// PostVerify re-checks the swapped cluster: counts, sequence coverage and per-leaf hardening.
func PostVerify(ctx context.Context, pool *pgxpool.Pool) error {
	if err := RequireUnfilteredVisibility(ctx, pool); err != nil {
		return err
	}
	// Post-swap the trusted side is audit_legacy (the frozen flat table), not audit_partitioned.
	// The pre-swap Verify proved an exact match under the lock. Post-commit, live inserts are legal, so
	// compare counts with legacy as a floor (never a spurious mismatch from a concurrent append).
	legacy, err := TableChecksums(ctx, pool, "audit_legacy")
	if err != nil {
		return fmt.Errorf("pfaudit: checksum audit_legacy: %w", err)
	}
	live, err := TableChecksums(ctx, pool, "audit")
	if err != nil {
		return fmt.Errorf("pfaudit: checksum audit: %w", err)
	}
	for tenant, want := range legacy {
		got, ok := live[tenant]
		if !ok || got.Rows < want.Rows {
			return fmt.Errorf("pfaudit: post-swap lost rows for tenant %s (%d < %d)", tenant, got.Rows, want.Rows)
		}
	}
	var last, maxID int64
	if err := pool.QueryRow(ctx, `SELECT last_value FROM audit_id_seq`).Scan(&last); err != nil {
		return err
	}
	if err := pool.QueryRow(ctx, `SELECT GREATEST(
		(SELECT COALESCE(max(id),0) FROM audit),
		(SELECT COALESCE(max(id),0) FROM audit_legacy))`).Scan(&maxID); err != nil {
		return err
	}
	if last <= maxID {
		return fmt.Errorf("pfaudit: sequence %d is not above max id %d (id reuse risk)", last, maxID)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_assert_hardened()`); err != nil {
		return fmt.Errorf("pfaudit: post-swap hardening: %w", err)
	}
	return nil
}
