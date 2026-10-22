package pfaudit

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
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
	pg, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatalf("open store: %v", err)
	}
	defer pg.Close()
	migs, err := migrate.LoadDir(filepath.Join("..", "..", "migrations"))
	if err != nil {
		t.Fatalf("load migrations: %v", err)
	}
	if _, err := migrate.Up(ctx, pg, migs); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	// 0014 must be re-applicable (idempotent) after months have elapsed.
	if _, err := migrate.Up(ctx, pg, migs); err != nil {
		t.Fatalf("second migrate (idempotency): %v", err)
	}

	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("pool: %v", err)
	}
	defer pool.Close()

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

	// row-level hold extraction, then two-stage retention (export -> manifest -> drop)
	month := AuditMonthName(now)
	if _, err := pool.Exec(ctx, `INSERT INTO audit_legal_hold_events(hold_id, tenant_id, month, action, actor, reason)
		VALUES ('hold-it', $1, $2, 'hold', 'tester', 'legal')`, tenant, month); err != nil {
		t.Fatalf("hold event: %v", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_hold_extract($1)`, month); err != nil {
		t.Fatalf("hold extract: %v", err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO audit_legal_hold_events(hold_id, tenant_id, month, action, actor, reason)
		VALUES ('hold-it', $1, $2, 'release', 'tester', 'released')`, tenant, month); err != nil {
		t.Fatalf("release hold: %v", err)
	}
	var held int64
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM audit_legal_hold_archive WHERE hold_id='hold-it'`).Scan(&held); err != nil {
		t.Fatal(err)
	}
	if held == 0 {
		t.Fatal("hold extract archived no rows")
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
	if err := PurgeMonth(ctx, pool, obj, month, "tester", "retention policy"); err != nil {
		t.Fatalf("purge: %v", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_drop_partition($1)`, month); err == nil {
		t.Fatal("drop after purge must fail")
	}
}
