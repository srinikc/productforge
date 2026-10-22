package pfaudit

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"productforge/migrate"
	"productforge/objstore"
	"productforge/store"
)

// TestAuditPartitioningIntegration exercises the real substrate against PostgreSQL. It self-skips unless
// PF_DB_DSN is set, so offline/CI stays green.
func TestAuditPartitioningIntegration(t *testing.T) {
	dsn := os.Getenv("PF_DB_DSN")
	if dsn == "" {
		t.Skip("PF_DB_DSN not set - skipping PostgreSQL integration test")
	}
	ctx := context.Background()
	pool := setup(t)

	if st, err := DetectState(ctx, pool); err != nil || st != StatePrestage {
		t.Fatalf("state = %v, %v; want prestage", st, err)
	}
	if _, _, err := CheckConfig(ctx, pool); err != nil {
		t.Fatalf("config: %v", err)
	}

	tenant := fmt.Sprintf("it-audit-%d", time.Now().UnixNano())
	other := tenant + "-other"
	now := time.Now().UTC()
	for i := 0; i < 25; i++ {
		if _, err := pool.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, resource, outcome, correlation_id, at)
			VALUES ($1,'actor','act','res','ok','corr',$2)`, tenant, now.Add(-time.Duration(i)*time.Minute)); err != nil {
			t.Fatalf("seed audit: %v", err)
		}
	}
	if _, err := pool.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, at) VALUES ($1,'a','b',$2)`,
		other, now); err != nil {
		t.Fatalf("seed other tenant: %v", err)
	}

	// prestage is idempotent: run it twice
	for round := 0; round < 2; round++ {
		var cursor int64
		for {
			r, err := CopyBatch(ctx, pool, cursor, 10)
			if err != nil {
				t.Fatalf("copy batch: %v", err)
			}
			cursor = r.LastID
			if r.Done {
				break
			}
		}
	}
	if problems, err := Verify(ctx, pool); err != nil {
		t.Fatalf("verify: %v (%v)", err, problems)
	}

	drained, err := Swap(ctx, pool, DefaultMaxDeltaRows)
	if err != nil {
		t.Fatalf("swap: %v", err)
	}
	if drained != 0 {
		t.Fatalf("drained = %d, want 0 after prestage", drained)
	}
	if st, err := DetectState(ctx, pool); err != nil || st != StateSwapped {
		t.Fatalf("post-swap state = %v, %v", st, err)
	}
	// Crash-after-rename resume path: a re-run must not re-swap, only verify.
	if err := PostVerify(ctx, pool); err != nil {
		t.Fatalf("post-swap verify: %v", err)
	}

	// the canonical sequence continues above both tables' max id
	var id int64
	if err := pool.QueryRow(ctx, `INSERT INTO audit (tenant_id, actor, action, at)
		VALUES ($1,'a','post-swap',now()) RETURNING id`, tenant).Scan(&id); err != nil {
		t.Fatalf("post-swap insert: %v", err)
	}
	var maxID int64
	if err := pool.QueryRow(ctx, `SELECT max(id) FROM audit_legacy`).Scan(&maxID); err != nil {
		t.Fatal(err)
	}
	if id <= maxID {
		t.Fatalf("post-swap id %d reused legacy range (max %d)", id, maxID)
	}

	// row-level hold extraction, then two-stage retention (export -> manifest -> drop) on an OLD month:
	// retention must never touch the current/future month or the grace partition.
	old := now.AddDate(0, -20, 0)
	month := AuditMonthName(old)
	from := time.Date(old.Year(), old.Month(), 1, 0, 0, 0, 0, time.UTC)
	to := from.AddDate(0, 1, 0)
	if _, err := pool.Exec(ctx, fmt.Sprintf(
		`CREATE TABLE public.%s PARTITION OF audit FOR VALUES FROM ('%s') TO ('%s')`,
		month, from.Format("2006-01-02 15:04:05+00"), to.Format("2006-01-02 15:04:05+00"))); err != nil {
		t.Fatalf("create old partition: %v", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_harden_partition($1)`, month); err != nil {
		t.Fatalf("harden old partition: %v", err)
	}
	for i := 0; i < 3; i++ {
		if _, err := pool.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, at) VALUES ($1,'a','cold',$2)`,
			tenant, from.Add(time.Duration(i)*time.Hour)); err != nil {
			t.Fatalf("seed cold month: %v", err)
		}
	}
	if cands, err := RetentionCandidates(ctx, pool, 13); err != nil {
		t.Fatalf("candidates: %v", err)
	} else {
		for _, c := range cands {
			if c == AuditMonthName(now) {
				t.Fatalf("current month %s is a retention candidate", c)
			}
		}
	}
	if _, err := pool.Exec(ctx, `INSERT INTO audit_legal_hold_events(hold_id, tenant_id, month, action, actor, reason)
		VALUES ('hold-it', $1, $2, 'hold', 'tester', 'legal')`, tenant, month); err != nil {
		t.Fatalf("hold event: %v", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_hold_extract($1)`, month); err != nil {
		t.Fatalf("hold extract: %v", err)
	}
	if archived, missing, err := VerifyHoldExtraction(ctx, pool, month); err != nil || missing != 0 || archived == 0 {
		t.Fatalf("hold verify: archived=%d missing=%d err=%v", archived, missing, err)
	}
	var held int64
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM audit_legal_hold_archive WHERE hold_id='hold-it'`).Scan(&held); err != nil {
		t.Fatal(err)
	}
	if held == 0 {
		t.Fatal("hold extract archived no rows")
	}
	if _, err := pool.Exec(ctx, `SELECT audit_drop_partition($1)`, month); err == nil {
		t.Fatal("drop with an active hold must be refused")
	}
	if _, err := pool.Exec(ctx, `INSERT INTO audit_legal_hold_events(hold_id, tenant_id, month, action, actor, reason)
		VALUES ('hold-it', $1, $2, 'release', 'tester', 'released')`, tenant, month); err != nil {
		t.Fatalf("release hold: %v", err)
	}

	obj, err := objstore.NewLocalStore(t.TempDir(), 1<<30)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE audit_partition_config SET purge_grace_days = 0`); err != nil {
		t.Fatal(err)
	}
	man, err := ExportMonth(ctx, pool, obj, month)
	if err != nil {
		t.Fatalf("export: %v", err)
	}
	if man.Rows == 0 || man.Checksum == "" {
		t.Fatalf("manifest = %+v", man)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_drop_partition($1)`, month); err != nil {
		t.Fatalf("drop: %v", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_drop_partition($1)`, month); err == nil {
		t.Fatal("second drop must fail (partition gone)")
	}
	// Round-trip restore before purge: cold data re-imports into an RLS-protected scratch leaf.
	if n, err := RestoreMonth(ctx, pool, obj, month); err != nil {
		t.Fatalf("restore: %v", err)
	} else if n != man.Rows {
		t.Fatalf("restored %d rows, manifest says %d", n, man.Rows)
	}
	if err := PurgeMonth(ctx, pool, obj, month, "tester", "retention policy"); err != nil {
		t.Fatalf("purge: %v", err)
	}
	if _, err := RestoreMonth(ctx, pool, obj, month); err == nil {
		t.Fatal("restore of a purged month must fail")
	}
	// Spoliation guard: a hold cannot be recorded against an already-purged month.
	if _, err := pool.Exec(ctx, `INSERT INTO audit_legal_hold_events(hold_id, tenant_id, month, action, actor, reason)
		VALUES ('hold-late', $1, $2, 'hold', 'tester', 'after purge')`, tenant, month); err == nil {
		t.Fatal("hold on a purged month must be refused")
	}
}

// TestVerifyDetectsDivergence proves an extra/divergent shadow row (the shape an ON CONFLICT id reuse would
// take) aborts the swap instead of being masked.
func TestVerifyDetectsDivergence(t *testing.T) {
	if os.Getenv("PF_DB_DSN") == "" {
		t.Skip("PF_DB_DSN not set - skipping PostgreSQL integration test")
	}
	ctx := context.Background()
	pool := setup(t)
	tenant := fmt.Sprintf("it-div-%d", time.Now().UnixNano())
	now := time.Now().UTC()
	for i := 0; i < 3; i++ {
		if _, err := pool.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, at) VALUES ($1,'a','x',$2)`,
			tenant, now.Add(-time.Duration(i)*time.Minute)); err != nil {
			t.Fatalf("seed: %v", err)
		}
	}
	var cursor int64
	for {
		r, err := CopyBatch(ctx, pool, cursor, 2)
		if err != nil {
			t.Fatalf("copy: %v", err)
		}
		cursor = r.LastID
		if r.Done {
			break
		}
	}
	if problems, err := Verify(ctx, pool); err != nil || len(problems) != 0 {
		t.Fatalf("baseline verify: %v %v", problems, err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO audit_partitioned (tenant_id, actor, action, at)
		VALUES ($1,'a','intruder',now())`, tenant); err != nil {
		t.Fatalf("inject divergence: %v", err)
	}
	if problems, _ := Verify(ctx, pool); len(problems) == 0 {
		t.Fatal("verify missed a divergent shadow row")
	}
}

// TestDownCopiesBackPostSwapRows proves --down does not strand events written after the swap.
func TestDownCopiesBackPostSwapRows(t *testing.T) {
	if os.Getenv("PF_DB_DSN") == "" {
		t.Skip("PF_DB_DSN not set - skipping PostgreSQL integration test")
	}
	ctx := context.Background()
	pool := setup(t)
	tenant := fmt.Sprintf("it-down-%d", time.Now().UnixNano())
	if _, err := pool.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, at) VALUES ($1,'a','pre',now())`, tenant); err != nil {
		t.Fatalf("seed: %v", err)
	}
	var cursor int64
	for {
		r, err := CopyBatch(ctx, pool, cursor, 10)
		if err != nil {
			t.Fatalf("copy: %v", err)
		}
		cursor = r.LastID
		if r.Done {
			break
		}
	}
	if _, err := Swap(ctx, pool, DefaultMaxDeltaRows); err != nil {
		t.Fatalf("swap: %v", err)
	}
	for i := 0; i < 2; i++ {
		if _, err := pool.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, at) VALUES ($1,'a','post',now())`,
			tenant); err != nil {
			t.Fatalf("post-swap insert: %v", err)
		}
	}
	if err := Down(ctx, pool, false, ""); err != nil {
		t.Fatalf("down: %v", err)
	}
	if st, err := DetectState(ctx, pool); err != nil || st != StatePrestage {
		t.Fatalf("post-down state = %v, %v; want prestage (flat audit + retained shadow)", st, err)
	}
	var n int64
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM audit WHERE tenant_id = $1`, tenant).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 3 {
		t.Fatalf("flat audit has %d row(s) for tenant, want 3 (down stranded data)", n)
	}
}

// TestReapplyAfterSwapIsRefused proves migration 0014 will not recreate an empty shadow on a swapped DB.
func TestReapplyAfterSwapIsRefused(t *testing.T) {
	dsn := os.Getenv("PF_DB_DSN")
	if dsn == "" {
		t.Skip("PF_DB_DSN not set - skipping PostgreSQL integration test")
	}
	ctx := context.Background()
	pool := setup(t)
	tenant := fmt.Sprintf("it-reapply-%d", time.Now().UnixNano())
	if _, err := pool.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, at) VALUES ($1,'a','x',now())`, tenant); err != nil {
		t.Fatalf("seed: %v", err)
	}
	var cursor int64
	for {
		r, err := CopyBatch(ctx, pool, cursor, 10)
		if err != nil {
			t.Fatalf("copy: %v", err)
		}
		cursor = r.LastID
		if r.Done {
			break
		}
	}
	if _, err := Swap(ctx, pool, DefaultMaxDeltaRows); err != nil {
		t.Fatalf("swap: %v", err)
	}
	if _, err := pool.Exec(ctx, `DELETE FROM schema_migrations WHERE version = 14`); err != nil {
		t.Fatalf("forget migration: %v", err)
	}
	pg, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	defer pg.Close()
	migs, err := migrate.LoadDir(filepath.Join("..", "..", "migrations"))
	if err != nil {
		t.Fatalf("load migrations: %v", err)
	}
	if _, err := migrate.Up(ctx, pg, migs); err == nil {
		t.Fatal("re-applying 0014 after the swap must be refused")
	}
	var shadow bool
	if err := pool.QueryRow(ctx, `SELECT to_regclass('audit_partitioned') IS NOT NULL`).Scan(&shadow); err != nil {
		t.Fatal(err)
	}
	if shadow {
		t.Fatal("re-apply created an empty shadow table next to the live partitioned audit")
	}
}
