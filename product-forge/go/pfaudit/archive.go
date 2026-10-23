package pfaudit

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"productforge/datastore"
)

// ArchiveManifest mirrors audit_archive_manifest. Actor/time/reason for a purge are recorded in the DB.
type ArchiveManifest struct {
	Month      string    `json:"month"`
	Rows       int64     `json:"rows"`
	Checksum   string    `json:"sha256"`
	Keys       []string  `json:"keys"`
	ArchivedAt time.Time `json:"archived_at"`
}

// ArchiveKey is the canonical cold-object layout: one object per month, all tenants, SSE at rest.
func ArchiveKey(month string) string { return "audit/cold/" + month + "/part-000.ndjson" }

type auditRow struct {
	ID            int64     `json:"id"`
	TenantID      string    `json:"tenant_id"`
	Actor         string    `json:"actor"`
	Action        string    `json:"action"`
	Resource      string    `json:"resource"`
	Outcome       string    `json:"outcome"`
	CorrelationID string    `json:"correlation_id"`
	At            time.Time `json:"at"`
}

// ExportMonth streams one partition to the object store as NDJSON, then records a verified manifest.
// The plaintext temp file is 0600 and removed before returning; the stored object is immutable.
func ExportMonth(ctx context.Context, pool *pgxpool.Pool, obj datastore.ObjectStore, month string) (ArchiveManifest, error) {
	var m ArchiveManifest
	m.Month = month
	m.ArchivedAt = time.Now().UTC()
	if !validMonth(month) {
		return m, fmt.Errorf("pfaudit: invalid partition %q", month)
	}
	// Export must see every tenant: a filtered read would record a short manifest and then drop the month.
	// pf_owner is the audit table owner (owner_bypass policy), NOT superuser: ownership is sufficient.
	if err := RequireUnfilteredVisibility(ctx, pool); err != nil {
		return m, err
	}
	var alreadyArchived bool
	if err := pool.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM audit_archive_manifest
		WHERE month = $1 AND archived_at IS NOT NULL)`, month).Scan(&alreadyArchived); err != nil {
		return m, err
	}
	if alreadyArchived {
		return m, fmt.Errorf("pfaudit: %s is already archived (immutable)", month)
	}
	f, err := os.CreateTemp("", "pfaudit-export-*.ndjson")
	if err != nil {
		return m, err
	}
	defer os.Remove(f.Name())
	if err := f.Chmod(0o600); err != nil {
		f.Close()
		return m, err
	}
	enc := bufio.NewWriterSize(f, 1<<20)
	rows, err := pool.Query(ctx, `SELECT id, tenant_id, actor, action, resource, outcome, correlation_id, at
		FROM `+month+` ORDER BY id, at`)
	if err != nil {
		f.Close()
		return m, err
	}
	for rows.Next() {
		var r auditRow
		if err := rows.Scan(&r.ID, &r.TenantID, &r.Actor, &r.Action, &r.Resource, &r.Outcome,
			&r.CorrelationID, &r.At); err != nil {
			rows.Close()
			f.Close()
			return m, err
		}
		b, err := json.Marshal(r)
		if err != nil {
			rows.Close()
			f.Close()
			return m, err
		}
		if _, err := enc.Write(append(b, '\n')); err != nil {
			rows.Close()
			f.Close()
			return m, err
		}
		m.Rows++
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		f.Close()
		return m, err
	}
	rows.Close()
	if err := enc.Flush(); err != nil {
		f.Close()
		return m, err
	}
	if _, err := f.Seek(0, io.SeekStart); err != nil {
		f.Close()
		return m, err
	}
	hash, size, err := SHA256(f)
	if err != nil {
		f.Close()
		return m, err
	}
	if _, err := f.Seek(0, io.SeekStart); err != nil {
		f.Close()
		return m, err
	}
	key := ArchiveKey(month)
	info, err := obj.Put(ctx, key, f, size, datastore.PutOptions{
		ContentType: "application/x-ndjson", Checksum: hash, Immutable: true,
		// Kept empty for the local adapter (it rejects SSE); cloud wiring sets PF_AUDIT_SSE (e.g. aws:kms).
		ServerSideEncryption: DefaultSSE(),
	})
	f.Close()
	if err != nil {
		return m, fmt.Errorf("pfaudit: put %s: %w", key, err)
	}
	if info.Checksum != "" && info.Checksum != hash {
		return m, fmt.Errorf("pfaudit: checksum mismatch after put (%s != %s)", info.Checksum, hash)
	}
	m.Checksum = hash
	m.Keys = []string{key}
	if err := RecordState(ctx, pool, "archived", fmt.Sprintf(`{"month":%q,"rows":%d}`, month, m.Rows)); err != nil {
		return m, fmt.Errorf("pfaudit: record archive event: %w", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_mark_archived($1, $2, $3, $4::jsonb)`,
		month, m.Rows, m.Checksum, mustJSON(m.Keys)); err != nil {
		return m, fmt.Errorf("pfaudit: record manifest: %w", err)
	}
	return m, nil
}

// RestoreMonth re-imports a cold month into a scratch partition of the live audit table (RLS applies).
func RestoreMonth(ctx context.Context, pool *pgxpool.Pool, obj datastore.ObjectStore, month string) (int64, error) {
	if !validMonth(month) {
		return 0, fmt.Errorf("pfaudit: invalid partition %q", month)
	}
	var wantRows int64
	var wantSum string
	if err := pool.QueryRow(ctx, `SELECT row_count, checksum FROM audit_archive_manifest WHERE month = $1`, month).
		Scan(&wantRows, &wantSum); err != nil {
		return 0, fmt.Errorf("pfaudit: manifest for %s: %w", month, err)
	}
	rc, _, err := obj.Get(ctx, ArchiveKey(month), "")
	if err != nil {
		return 0, fmt.Errorf("pfaudit: get %s: %w", ArchiveKey(month), err)
	}
	defer rc.Close()
	tmp, err := os.CreateTemp("", "pfaudit-restore-*.ndjson")
	if err != nil {
		return 0, err
	}
	defer os.Remove(tmp.Name())
	defer tmp.Close()
	if _, err := io.Copy(tmp, rc); err != nil {
		return 0, err
	}
	if _, err := tmp.Seek(0, io.SeekStart); err != nil {
		return 0, err
	}
	// Integrity is checked BEFORE any row reaches the live cluster.
	sum, _, err := SHA256(tmp)
	if err != nil {
		return 0, err
	}
	if wantSum == "" {
		return 0, errors.New("pfaudit: manifest has no checksum; refusing to restore unverified data")
	}
	if sum != wantSum {
		return 0, fmt.Errorf("pfaudit: archive checksum %s != manifest %s", sum, wantSum)
	}
	if _, err := tmp.Seek(0, io.SeekStart); err != nil {
		return 0, err
	}
	// Standalone scratch table, NOT a partition: attaching the archived month range would overlap the
	// canonical partition that rotation re-creates for the same month.
	scratch := "audit_restore_" + month[len(month)-6:]
	var parent string
	if err := pool.QueryRow(ctx, `SELECT audit_parent()::text`).Scan(&parent); err != nil {
		return 0, fmt.Errorf("pfaudit: audit_parent: %w", err)
	}
	if _, err := pool.Exec(ctx, fmt.Sprintf(`DROP TABLE IF EXISTS %s`, scratch)); err != nil {
		return 0, fmt.Errorf("pfaudit: reset scratch: %w", err)
	}
	if _, err := pool.Exec(ctx, fmt.Sprintf(`CREATE TABLE %s (LIKE %s INCLUDING ALL)`, scratch, parent)); err != nil {
		return 0, fmt.Errorf("pfaudit: create scratch table: %w", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_harden_partition($1)`, scratch); err != nil {
		return 0, err
	}
	// Forensic readers use the runtime role: RLS still filters per tenant.
	if _, err := pool.Exec(ctx, fmt.Sprintf(`GRANT SELECT ON %s TO pf_runtime`, scratch)); err != nil {
		return 0, err
	}
	sc := bufio.NewScanner(tmp)
	sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
	batch := make([][]any, 0, 1000)
	var n int64
	flush := func() error {
		if len(batch) == 0 {
			return nil
		}
		args := make([]any, 0, len(batch)*8)
		vals := make([]byte, 0, len(batch)*16)
		for i, row := range batch {
			if i > 0 {
				vals = append(vals, ',')
			}
			vals = append(vals, fmt.Sprintf("($%d,$%d,$%d,$%d,$%d,$%d,$%d,$%d)", i*8+1, i*8+2, i*8+3, i*8+4, i*8+5, i*8+6, i*8+7, i*8+8)...)
			args = append(args, row...)
		}
		q := fmt.Sprintf(`INSERT INTO %s (id, tenant_id, actor, action, resource, outcome, correlation_id, at)
			VALUES %s ON CONFLICT (id, at) DO NOTHING`, scratch, string(vals))
		if _, err := pool.Exec(ctx, q, args...); err != nil {
			return err
		}
		batch = batch[:0]
		return nil
	}
	for sc.Scan() {
		var r auditRow
		if err := json.Unmarshal(sc.Bytes(), &r); err != nil {
			return n, err
		}
		batch = append(batch, []any{r.ID, r.TenantID, r.Actor, r.Action, r.Resource, r.Outcome, r.CorrelationID, r.At})
		n++
		if len(batch) >= 1000 {
			if err := flush(); err != nil {
				return n, err
			}
		}
	}
	if err := sc.Err(); err != nil {
		return n, err
	}
	if err := flush(); err != nil {
		return n, err
	}
	if n != wantRows {
		return n, fmt.Errorf("pfaudit: archive has %d row(s), manifest says %d", n, wantRows)
	}
	var restored int64
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM `+scratch).Scan(&restored); err != nil {
		return n, err
	}
	if restored != wantRows {
		return n, fmt.Errorf("pfaudit: restored %d row(s), manifest says %d", restored, wantRows)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_restore_lock($1, current_user, 'cold restore')`, month); err != nil {
		return n, err
	}
	return n, nil
}

// VerifyHoldExtraction proves that every row still under an active hold in month has been copied to
// audit_legal_hold_archive before the hot partition may be dropped.
func VerifyHoldExtraction(ctx context.Context, pool *pgxpool.Pool, month string) (archived, missing int64, err error) {
	if !validMonth(month) {
		return 0, 0, fmt.Errorf("pfaudit: invalid partition %q", month)
	}
	q := `SELECT
	  (SELECT count(*) FROM audit_legal_hold_archive WHERE source_partition = $1),
	  (SELECT count(*) FROM ` + month + ` a
	     JOIN audit_legal_hold_events e ON e.month = $1 AND e.action = 'hold'
	       AND (length(e.tenant_id) = 0 OR e.tenant_id = a.tenant_id)
	    WHERE NOT EXISTS (SELECT 1 FROM audit_legal_hold_events r
	                       WHERE r.hold_id = e.hold_id AND r.action = 'release' AND r.at > e.at)
	      AND NOT EXISTS (SELECT 1 FROM audit_legal_hold_archive x
	                       WHERE x.hold_id = e.hold_id AND x.id = a.id AND x.at = a.at))`
	err = pool.QueryRow(ctx, q, month).Scan(&archived, &missing)
	if err != nil {
		return archived, missing, err
	}
	// Counts alone cannot detect swapped/tampered rows, so the archived copy is also digest-checked.
	dq := `SELECT
	  coalesce((SELECT encode(sha256(convert_to(string_agg(concat_ws('|', t.id, t.tenant_id, t.actor, t.action, t.resource, t.outcome, t.correlation_id, extract(epoch from t.at)), E'\n' ORDER BY t.id, t.at), 'UTF8')), 'hex')
	    FROM (SELECT DISTINCT x.id, x.tenant_id, x.actor, x.action, x.resource, x.outcome, x.correlation_id, x.at
	            FROM audit_legal_hold_archive x
	           WHERE x.source_partition = $1
	             AND x.hold_id IN (SELECT h.hold_id FROM audit_legal_hold_events h
	                                WHERE h.month = $1 AND h.action = 'hold'
	                                  AND NOT EXISTS (SELECT 1 FROM audit_legal_hold_events r
	                                                   WHERE r.hold_id = h.hold_id AND r.action = 'release' AND r.at > h.at))) t), ''),
	  coalesce((SELECT encode(sha256(convert_to(string_agg(concat_ws('|', t.id, t.tenant_id, t.actor, t.action, t.resource, t.outcome, t.correlation_id, extract(epoch from t.at)), E'\n' ORDER BY t.id, t.at), 'UTF8')), 'hex')
	    FROM (SELECT DISTINCT a.id, a.tenant_id, a.actor, a.action, a.resource, a.outcome, a.correlation_id, a.at
	            FROM ` + month + ` a
	            JOIN audit_legal_hold_events e ON e.month = $1 AND e.action = 'hold'
	             AND (length(e.tenant_id) = 0 OR e.tenant_id = a.tenant_id)
	           WHERE NOT EXISTS (SELECT 1 FROM audit_legal_hold_events r
	                              WHERE r.hold_id = e.hold_id AND r.action = 'release' AND r.at > e.at)) t), '')`
	var archSum, liveSum string
	if err := pool.QueryRow(ctx, dq, month).Scan(&archSum, &liveSum); err != nil {
		return archived, missing, err
	}
	if missing == 0 && archSum != liveSum {
		return archived, missing, fmt.Errorf("pfaudit: hold archive digest %s != live %s", archSum, liveSum)
	}
	return archived, missing, nil
}

// PurgeMonth deletes the archived objects and records the irreversible purge (approval must exist).
func PurgeMonth(ctx context.Context, pool *pgxpool.Pool, obj datastore.ObjectStore, month, actor, reason string) error {
	if actor == "" || reason == "" {
		return fmt.Errorf("pfaudit: purge requires actor and reason")
	}
	var active int64
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM audit_legal_hold_events h
		WHERE h.month = $1 AND h.action = 'hold' AND NOT EXISTS (
		    SELECT 1 FROM audit_legal_hold_events r
		    WHERE r.hold_id = h.hold_id AND r.action = 'release' AND r.at > h.at)`, month).Scan(&active); err != nil {
		return err
	}
	if active > 0 {
		return fmt.Errorf("pfaudit: %s has an active legal hold (%d) - purge refused", month, active)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_approve_purge($1, $2, $3)`, month, actor, reason); err != nil {
		return err
	}
	var keysJSON []byte
	if err := pool.QueryRow(ctx, `SELECT object_keys FROM audit_archive_manifest WHERE month = $1`, month).Scan(&keysJSON); err != nil {
		return err
	}
	var keys []string
	if err := json.Unmarshal(keysJSON, &keys); err != nil {
		return err
	}
	// Durable record first: a crash after this leaves only orphan cold objects (recoverable), never data
	// destruction without an audit trail.
	if _, err := pool.Exec(ctx, `SELECT audit_mark_purged($1)`, month); err != nil {
		return err
	}
	for _, k := range keys {
		// Idempotent: a partially completed purge must be resumable, not stuck on a missing object.
		if err := obj.Delete(ctx, k, ""); err != nil && !errors.Is(err, fs.ErrNotExist) {
			return fmt.Errorf("pfaudit: delete %s: %w", k, err)
		}
	}
	return RecordState(ctx, pool, "purged", fmt.Sprintf(`{"month":%q}`, month))
}

// ExtractHolds archives held rows of a month before it is dropped/archived.
func ExtractHolds(ctx context.Context, pool *pgxpool.Pool, month string) (int64, error) {
	var n int64
	if err := pool.QueryRow(ctx, `SELECT audit_hold_extract($1)`, month).Scan(&n); err != nil {
		return 0, err
	}
	if err := RecordState(ctx, pool, "holds_extracted", fmt.Sprintf(`{"month":%q,"rows":%d}`, month, n)); err != nil {
		return n, err
	}
	return n, nil
}

// RetentionCandidates lists fully-old months for export (dry-run is the caller's job).
func RetentionCandidates(ctx context.Context, pool *pgxpool.Pool, keepMonths int) ([]string, error) {
	rows, err := pool.Query(ctx, `SELECT month FROM audit_retention_candidates($1)`, keepMonths)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var m string
		if err := rows.Scan(&m); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

// Coverage reads the DB coverage function.
type Coverage struct {
	MinMonth    *time.Time
	MaxMonth    *time.Time
	GraceMonth  *time.Time
	MonthsAhead int
}

func ReadCoverage(ctx context.Context, pool *pgxpool.Pool) (Coverage, error) {
	var c Coverage
	err := pool.QueryRow(ctx, `SELECT min_month, max_month, grace_month, months_ahead FROM audit_partition_coverage()`).
		Scan(&c.MinMonth, &c.MaxMonth, &c.GraceMonth, &c.MonthsAhead)
	return c, err
}

// monthBounds returns the [from, to) dates of an audit_YYYYMM partition.
func monthBounds(partition string) (string, string) {
	if len(partition) < 6 {
		return "", ""
	}
	ym := partition[len(partition)-6:]
	y, _ := strconv.Atoi(ym[:4])
	m, _ := strconv.Atoi(ym[4:])
	from := time.Date(y, time.Month(m), 1, 0, 0, 0, 0, time.UTC)
	return from.Format("2006-01-02"), from.AddDate(0, 1, 0).Format("2006-01-02")
}

func quoteDate(d string) string { return "'" + d + "'::date" }

func mustJSON(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}
